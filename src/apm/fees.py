"""Fee models. Unknown inputs stay unknown; rebates are never booked as income."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from apm.models import FeeSpec

POLYMARKET_TICK = Decimal("0.00001")
KALSHI_TRADE_TICK = Decimal("0.000001")
KALSHI_CENT = Decimal("0.01")

QUADRATIC_TAKER_TYPES = frozenset(
    {
        "quadratic",
        "quadratic_with_maker_fees",
        "quadratic_with_combo_maker_fees",
    }
)


@dataclass(frozen=True)
class ScheduledFee:
    change_id: str
    fee_type: str
    multiplier: Decimal
    scheduled_at: datetime


def ceil_to(value: Decimal, quantum: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("fee rounding input must be non-negative")
    if value == 0:
        return Decimal("0")
    units = (value / quantum).to_integral_value(rounding=ROUND_CEILING)
    return units * quantum


def polymarket_fee_spec(
    *,
    fees_enabled: bool | None,
    fee_type: str | None,
    rate: Decimal | None,
    exponent: Decimal | None,
    taker_only: bool | None,
    rebate_rate: Decimal | None,
) -> FeeSpec:
    del rebate_rate  # rebates are not assumed income
    source = "polymarket.market.feeSchedule"
    if fees_enabled is False:
        return FeeSpec(
            known=True,
            model="zero",
            rate=Decimal("0"),
            exponent=Decimal("1"),
            currency="USDC",
            source=source,
            version=fee_type or "fees_disabled",
            rounding_rule="polymarket_5dp_half_up",
            taker_only=taker_only,
            fee_bound="exact",
            detail="market.feesEnabled is false",
        )
    if fees_enabled is not True or rate is None or exponent is None:
        return FeeSpec.unknown("polymarket feeSchedule rate or exponent missing", source=source)
    if exponent != Decimal("1"):
        return FeeSpec.unknown(
            f"polymarket fee exponent {exponent} is outside the documented p*(1-p) formula",
            source=source,
        )
    return FeeSpec(
        known=True,
        model="polymarket_quadratic",
        rate=rate,
        exponent=exponent,
        currency="USDC",
        source=source,
        version=fee_type or "feeSchedule",
        rounding_rule="polymarket_5dp_half_up",
        taker_only=taker_only,
        fee_bound="exact",
        detail="fee = C * rate * p * (1-p), half-up to 0.00001 USDC; rebate not included",
    )


def kalshi_fee_spec(
    *,
    fee_type: str | None,
    multiplier: Decimal | None,
    coefficient: Decimal | None,
    schedule_version: str,
    rounding_rule: str,
    version_id: str,
    effective_at_utc: str | None,
    source: str,
) -> FeeSpec:
    if fee_type is None or multiplier is None or coefficient is None:
        return FeeSpec.unknown("kalshi series fee_type or fee_multiplier missing", source=source)
    if fee_type not in QUADRATIC_TAKER_TYPES:
        return FeeSpec.unknown(
            f"kalshi fee_type {fee_type} has no encoded taker formula",
            source=source,
        )
    if rounding_rule != "non_direct_cent_upper_bound":
        return FeeSpec.unknown(f"unsupported kalshi rounding rule {rounding_rule}", source=source)
    return FeeSpec(
        known=True,
        model="kalshi_quadratic",
        rate=coefficient,
        multiplier=multiplier,
        currency="USD",
        source=source,
        version=f"{schedule_version}:{version_id}",
        effective_at_utc=effective_at_utc,
        rounding_rule=rounding_rule,
        taker_only=True,
        fee_bound="upper_non_direct_cent",
        detail=(
            "model = M * coefficient * C * P * (1-P); trade fee ceil to 0.000001; "
            "then cost+fee ceil to 0.01 (non-direct member upper bound). "
            "Direct members can pay less. Maker rebates are not income."
        ),
    )


def select_scheduled_fee(
    *,
    series_fee_type: str | None,
    series_multiplier: Decimal | None,
    changes: list[ScheduledFee],
    as_of: datetime | None,
) -> tuple[str | None, Decimal | None, str]:
    """Return the fee in force at as_of. Future scheduled changes do not apply."""
    if as_of is None or series_fee_type is None or series_multiplier is None:
        return None, None, "unknown"
    applicable = [change for change in changes if change.scheduled_at <= as_of]
    if not applicable:
        return series_fee_type, series_multiplier, "series_current"
    latest = max(applicable, key=lambda change: (change.scheduled_at, change.change_id))
    return latest.fee_type, latest.multiplier, latest.change_id


def fee_for_fills(fills: list[tuple[Decimal, Decimal]], spec: FeeSpec) -> Decimal | None:
    """fills are (size, price) at each walked level. None means the fee is unknown."""
    if spec.model == "fixed_total":
        if spec.fixed_total is None:
            return None
        return spec.fixed_total
    if not spec.known:
        return None
    total = Decimal("0")
    for size, price in fills:
        part = _level_fee(size, price, spec)
        if part is None:
            return None
        total += part
    return total


def _level_fee(size: Decimal, price: Decimal, spec: FeeSpec) -> Decimal | None:
    if size < 0 or price < 0:
        return None
    if spec.model == "zero":
        return Decimal("0")
    if spec.model == "polymarket_quadratic":
        if spec.rate is None or spec.exponent is None:
            return None
        complement = Decimal("1") - price
        raw = size * spec.rate * (price**spec.exponent) * (complement**spec.exponent)
        if raw < 0:
            return None
        return raw.quantize(POLYMARKET_TICK, rounding=ROUND_HALF_UP)
    if spec.model == "kalshi_quadratic":
        if spec.rate is None or spec.multiplier is None:
            return None
        model = spec.multiplier * spec.rate * size * price * (Decimal("1") - price)
        if model < 0:
            return None
        trade_fee = ceil_to(model, KALSHI_TRADE_TICK)
        if spec.rounding_rule == "ceil_6dp":
            return trade_fee
        if spec.rounding_rule == "non_direct_cent_upper_bound":
            total = size * price + trade_fee
            return ceil_to(total, KALSHI_CENT) - (size * price)
        return None
    return None
