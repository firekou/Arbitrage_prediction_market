"""Dataclasses for normalized research records. Decimals stay strings at the boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from apm import SCHEMA_VERSION


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_utc(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def decimal_json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return isoformat_utc(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {k: decimal_json(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): decimal_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [decimal_json(v) for v in value]
    return value


@dataclass
class Level:
    price: Decimal
    size: Decimal

    def as_pair(self) -> tuple[str, str]:
        return (format(self.price, "f"), format(self.size, "f"))


@dataclass
class FeeSpec:
    """A fee is known only when the model, rate inputs, and rounding rule are all set."""

    known: bool
    model: str
    rate: Decimal | None = None
    multiplier: Decimal | None = None
    exponent: Decimal | None = None
    fixed_total: Decimal | None = None
    currency: str | None = None
    source: str | None = None
    version: str | None = None
    effective_at_utc: str | None = None
    rounding_rule: str | None = None
    taker_only: bool | None = None
    fee_bound: str | None = None
    detail: str | None = None

    @staticmethod
    def unknown(detail: str, source: str | None = None) -> FeeSpec:
        return FeeSpec(known=False, model="unknown", source=source, detail=detail)


@dataclass
class NormalizedMarket:
    venue_id: str
    market_id: str
    event_id: str | None
    series_id: str | None
    title: str
    rules_text: str
    rules_sha256: str
    status: str
    result: str | None
    close_time_utc: str | None
    expiration_time_utc: str | None
    outcomes: dict[str, str]
    currency: str | None
    notional: str | None
    fee: FeeSpec
    raw_request_id: str
    active: bool
    orderbook_enabled: bool
    schema_version: str = SCHEMA_VERSION
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedBook:
    venue_id: str
    market_id: str
    outcome_id: str
    side: str
    bids: list[Level]
    asks: list[Level]
    quote_time_utc: str | None
    quote_time_status: str
    received_at_utc: str
    request_id: str
    payload_sha256: str | None
    parse_ok: bool
    reason_codes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


@dataclass
class RawCapture:
    request_id: str
    venue_id: str
    kind: str
    url: str
    market_id: str | None
    outcome_id: str | None
    request_started_at_utc: str
    received_at_utc: str
    request_duration_ms: int
    http_status: int | None
    source_timestamp: str | None
    source_timestamp_status: str
    payload_sha256: str | None
    schema_version: str
    sequence: int | None
    error: str | None
    failure_code: str | None
    attempt_count: int
    raw_response: str | None


@dataclass
class Features:
    subject_tokens: frozenset[str]
    numbers: frozenset[str]
    dates: frozenset[str]
    operators: frozenset[str]
    timezones: frozenset[str]
    sources: frozenset[str]
    cancel_refund: frozenset[str]


@dataclass
class PairCandidate:
    pair_id: str
    left_venue: str
    left_market_id: str
    right_venue: str
    right_market_id: str
    left_title: str
    right_title: str
    review_status: str
    direction_mapping: str
    rules_sha256_left: str
    rules_sha256_right: str
    differences: list[str]
    comparison: dict[str, Any]
    approval_version: None = None
    reviewer: None = None
    score: str = "0"

    def __post_init__(self) -> None:
        if self.review_status == "APPROVED" or self.approval_version is not None:
            raise ValueError("B1 cannot mark a pair APPROVED")
        if self.direction_mapping != "UNCONFIRMED":
            raise ValueError("direction mapping stays UNCONFIRMED until human review")
