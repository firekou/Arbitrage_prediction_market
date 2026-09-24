"""Deterministic complementary-payout screen. Decimal only. Never emits APPROVED."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from apm import reasons as R
from apm.fees import fee_for_fills
from apm.models import FeeSpec, Level, decimal_json


@dataclass(frozen=True)
class AskBook:
    asks: tuple[Level, ...]
    quote_time: datetime | None
    received_at: datetime
    open_for_trading: bool = True


@dataclass
class EvalResult:
    strategy: str
    executable: bool
    approval_status: str
    reason_codes: list[str]
    q: Decimal | None
    gross_edge: Decimal | None
    net_edge: Decimal | None
    fee_total: Decimal | None
    other_cost: Decimal
    buffer: Decimal
    costs: dict[str, str]
    vwaps: dict[str, str]
    hypothetical_price_gap: Decimal | None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        payload = {
            "strategy": self.strategy,
            "executable": self.executable,
            "approval_status": self.approval_status,
            "reason_codes": list(self.reason_codes),
            "q": self.q,
            "gross_edge": self.gross_edge,
            "net_edge": self.net_edge,
            "fee_total": self.fee_total,
            "other_cost": self.other_cost,
            "buffer": self.buffer,
            "costs": self.costs,
            "vwaps": self.vwaps,
            "hypothetical_price_gap": self.hypothetical_price_gap,
            "notes": list(self.notes),
        }
        if payload["approval_status"] == "APPROVED":
            raise ValueError("engine must not emit APPROVED")
        return decimal_json(payload)


@dataclass
class Walk:
    filled: Decimal
    cost: Decimal
    complete: bool
    levels: list[tuple[Decimal, Decimal]]
    vwap: Decimal | None


def walk_asks(asks: tuple[Level, ...] | list[Level], quantity: Decimal) -> Walk:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    remaining = quantity
    cost = Decimal("0")
    filled = Decimal("0")
    used: list[tuple[Decimal, Decimal]] = []
    for level in asks:
        if remaining <= 0:
            break
        if level.size <= 0:
            continue
        take = level.size if level.size < remaining else remaining
        cost += take * level.price
        filled += take
        remaining -= take
        used.append((take, level.price))
    vwap = (cost / filled) if filled > 0 else None
    return Walk(filled=filled, cost=cost, complete=remaining == 0, levels=used, vwap=vwap)


def evaluate_complement(
    *,
    strategy: str,
    books: list[tuple[str, AskBook]],
    fees: list[FeeSpec],
    currencies: list[str | None],
    quantity: Decimal,
    other_cost: Decimal,
    buffer: Decimal,
    payout_per_share: Decimal | None,
    rules_status: str,
    max_quote_age: timedelta,
    max_leg_skew: timedelta,
    clock_ahead_tolerance: timedelta,
    min_net_edge: Decimal = Decimal("0"),
) -> EvalResult:
    """Buy one ask book per leg. payout_per_share is the locked payout for the whole set.

    For a binary YES+NO, payout_per_share is 1 only when rules confirm that every
    included settlement state pays exactly 1 per pair. None keeps the row at
    PRICE_GAP_ONLY (or REJECTED when the rules already conflict).
    """
    if len(books) != len(fees) or len(books) != len(currencies):
        raise ValueError("books, fees, and currencies must align")
    if rules_status not in {"confirmed", "unknown", "inconsistent"}:
        raise ValueError("rules_status must be confirmed, unknown, or inconsistent")

    reason_codes: list[str] = []
    notes: list[str] = []
    walks: list[Walk | None] = []
    empty_legs = 0
    for name, book in books:
        if not book.open_for_trading:
            reason_codes.append(R.MARKET_CLOSED)
        if not book.asks:
            empty_legs += 1
            walks.append(None)
            notes.append(f"{name}:no_asks")
            continue
        walks.append(walk_asks(book.asks, quantity))

    if empty_legs == len(books) and books:
        reason_codes.append(R.EMPTY_BOOK)
    elif empty_legs:
        reason_codes.append(R.MISSING_SIDE)

    for walk in walks:
        if walk is not None and not walk.complete:
            reason_codes.append(R.INSUFFICIENT_DEPTH)
            break

    quote_times: list[datetime | None] = []
    received: list[datetime] = []
    for _, book in books:
        quote_times.append(book.quote_time)
        received.append(book.received_at)
    if any(stamp is None for stamp in quote_times):
        reason_codes.append(R.TIMESTAMP_UNKNOWN)
    else:
        stale = False
        for stamp, recv in zip(quote_times, received, strict=True):
            assert stamp is not None
            age = recv - stamp
            if age > max_quote_age or age < -clock_ahead_tolerance:
                stale = True
        known_times = [stamp for stamp in quote_times if stamp is not None]
        ages = []
        for stamp, recv in zip(quote_times, received, strict=True):
            if stamp is not None:
                ages.append(f"{(recv - stamp).total_seconds():.3f}")
        if ages:
            notes.append("age_seconds=" + ",".join(ages))
        if len(known_times) >= 2:
            skew = max(known_times) - min(known_times)
            notes.append(f"leg_skew_seconds={skew.total_seconds():.3f}")
            if skew > max_leg_skew:
                stale = True
        if stale:
            reason_codes.append(R.STALE_QUOTE)

    if any(not spec.known and spec.model != "fixed_total" for spec in fees):
        reason_codes.append(R.FEE_UNKNOWN)
    if any(spec.model == "fixed_total" and spec.fixed_total is None for spec in fees):
        reason_codes.append(R.FEE_UNKNOWN)

    if any(code is None or code == "" for code in currencies):
        reason_codes.append(R.CURRENCY_UNKNOWN)
    elif len(set(currencies)) != 1:
        reason_codes.append(R.CURRENCY_UNKNOWN)
        notes.append("currency_mismatch")

    if rules_status == "inconsistent":
        reason_codes.append(R.RULES_INCONSISTENT)
    elif rules_status != "confirmed":
        reason_codes.append(R.RULES_UNKNOWN)
    if payout_per_share is None:
        reason_codes.append(R.COMPLEMENTARITY_UNCONFIRMED)

    costs: dict[str, str] = {}
    vwaps: dict[str, str] = {}
    fee_total: Decimal | None = Decimal("0")
    all_filled = all(walk is not None and walk.complete for walk in walks) and bool(walks)
    if fee_total is not None:
        for (name, _), walk, spec in zip(books, walks, fees, strict=True):
            if walk is None:
                fee_total = None
                break
            costs[name] = format(walk.cost, "f")
            vwaps[name] = format(walk.vwap, "f") if walk.vwap is not None else ""
            if not walk.complete:
                fee_total = None
                break
            part = fee_for_fills(walk.levels, spec)
            if part is None:
                fee_total = None
                if R.FEE_UNKNOWN not in reason_codes:
                    reason_codes.append(R.FEE_UNKNOWN)
                break
            fee_total += part

    hypothetical: Decimal | None = None
    if all_filled:
        spent = sum((walk.cost for walk in walks if walk is not None), Decimal("0"))
        hypothetical = quantity - spent

    gross: Decimal | None = None
    net: Decimal | None = None
    if all_filled and payout_per_share is not None and fee_total is not None:
        spent = sum((walk.cost for walk in walks if walk is not None), Decimal("0"))
        gross = (payout_per_share * quantity) - spent
        net = gross - fee_total - other_cost - buffer
        if net <= min_net_edge:
            reason_codes.append(R.NET_EDGE_NONPOSITIVE)

    reason_codes = _unique(reason_codes)
    executable = not reason_codes and net is not None and net > min_net_edge
    if rules_status == "inconsistent":
        approval = R.REJECTED
    elif payout_per_share is None:
        approval = R.PRICE_GAP_ONLY
    elif executable:
        approval = R.UNREVIEWED
    else:
        approval = R.REJECTED
    return EvalResult(
        strategy=strategy,
        executable=executable,
        approval_status=approval,
        reason_codes=reason_codes,
        q=quantity,
        gross_edge=gross,
        net_edge=net if executable or R.NET_EDGE_NONPOSITIVE in reason_codes else None,
        fee_total=fee_total,
        other_cost=other_cost,
        buffer=buffer,
        costs=costs,
        vwaps=vwaps,
        hypothetical_price_gap=hypothetical,
        notes=notes,
    )


def evaluate_n_outcome(
    *,
    side: str,
    books: list[tuple[str, AskBook]],
    fees: list[FeeSpec],
    currencies: list[str | None],
    quantity: Decimal,
    other_cost: Decimal,
    buffer: Decimal,
    event_complete: bool,
    rules_status: str,
    max_quote_age: timedelta,
    max_leg_skew: timedelta,
    clock_ahead_tolerance: timedelta,
    min_net_edge: Decimal = Decimal("0"),
) -> EvalResult:
    if side not in {"YES", "NO"}:
        raise ValueError("side must be YES or NO")
    n = len(books)
    if not event_complete or n < 2:
        return EvalResult(
            strategy=f"n_outcome_all_{side.lower()}",
            executable=False,
            approval_status=R.REJECTED,
            reason_codes=[R.INCOMPLETE_EVENT, R.RULES_UNKNOWN, R.COMPLEMENTARITY_UNCONFIRMED],
            q=quantity,
            gross_edge=None,
            net_edge=None,
            fee_total=None,
            other_cost=other_cost,
            buffer=buffer,
            costs={},
            vwaps={},
            hypothetical_price_gap=None,
            notes=["event is not a proven complete mutually exclusive set"],
        )
    payout = Decimal(1) if side == "YES" else Decimal(n - 1)
    if rules_status != "confirmed":
        payout_value = None
    else:
        payout_value = payout
    return evaluate_complement(
        strategy=f"n_outcome_all_{side.lower()}",
        books=books,
        fees=fees,
        currencies=currencies,
        quantity=quantity,
        other_cost=other_cost,
        buffer=buffer,
        payout_per_share=payout_value,
        rules_status=rules_status,
        max_quote_age=max_quote_age,
        max_leg_skew=max_leg_skew,
        clock_ahead_tolerance=clock_ahead_tolerance,
        min_net_edge=min_net_edge,
    )


def best_executable_quantity(
    *,
    strategy: str,
    books: list[tuple[str, AskBook]],
    fees: list[FeeSpec],
    currencies: list[str | None],
    other_cost_per_share: Decimal,
    buffer_per_share: Decimal,
    payout_per_share: Decimal | None,
    rules_status: str,
    max_quote_age: timedelta,
    max_leg_skew: timedelta,
    clock_ahead_tolerance: timedelta,
    extra_quantities: tuple[Decimal, ...] = (),
) -> EvalResult:
    """Pick the depth kink with the largest conservative net. Other/buffer scale with q."""
    sizes: set[Decimal] = set(extra_quantities)
    for _, book in books:
        running = Decimal("0")
        for level in book.asks:
            running += level.size
            if running > 0:
                sizes.add(running)
    if not sizes:
        sizes.add(Decimal("1"))
    results = [
        evaluate_complement(
            strategy=strategy,
            books=books,
            fees=fees,
            currencies=currencies,
            quantity=quantity,
            other_cost=other_cost_per_share * quantity,
            buffer=buffer_per_share * quantity,
            payout_per_share=payout_per_share,
            rules_status=rules_status,
            max_quote_age=max_quote_age,
            max_leg_skew=max_leg_skew,
            clock_ahead_tolerance=clock_ahead_tolerance,
        )
        for quantity in sorted(sizes)
    ]
    winners = [result for result in results if result.executable and result.net_edge is not None]
    if winners:
        return max(winners, key=lambda result: (result.net_edge or Decimal("0"), -(result.q or Decimal("0"))))
    return results[0]


def _unique(codes: list[str]) -> list[str]:
    seen: list[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen
