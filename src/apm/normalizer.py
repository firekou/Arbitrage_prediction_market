"""Map official public payloads into normalized markets and books.

Quote times come only from venue fields. A missing exchange timestamp stays
UNKNOWN; local receive time is stored separately and is never copied over it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from apm import reasons as R
from apm.fees import polymarket_fee_spec
from apm.models import FeeSpec, Level, NormalizedBook, NormalizedMarket, isoformat_utc

POLYMARKET_US = "polymarket_us"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise ValueError("price and size must be strings or integers, not floats")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("not a decimal") from exc
    return parsed


def normalize_polymarket_market(payload: dict[str, Any], *, request_id: str, venue_id: str) -> NormalizedMarket:
    if venue_id == POLYMARKET_US:
        raise ValueError("polymarket_us is out of scope and must not be mixed into the international venue")
    if not isinstance(payload, dict) or not payload.get("id") or not payload.get("question"):
        raise ValueError("SCHEMA_CHANGED")
    description = str(payload.get("description") or "")
    resolution = str(payload.get("resolutionSource") or "")
    rules = description if not resolution else f"{description}\n\nResolution source: {resolution}"
    names = _json_list(payload.get("outcomes"))
    tokens = _json_list(payload.get("clobTokenIds"))
    outcomes: dict[str, str] = {}
    if names and tokens and len(names) == len(tokens):
        for name, token in zip(names, tokens, strict=True):
            label = str(name).strip().upper()
            if label in {"YES", "NO"}:
                outcomes[label] = str(token)
    schedule = payload.get("feeSchedule") if isinstance(payload.get("feeSchedule"), dict) else {}
    rate = _optional_decimal(schedule.get("rate")) if schedule else None
    exponent = _optional_decimal(schedule.get("exponent")) if schedule else None
    fee = polymarket_fee_spec(
        fees_enabled=payload.get("feesEnabled") if isinstance(payload.get("feesEnabled"), bool) else None,
        fee_type=_optional_str(payload.get("feeType")),
        rate=rate,
        exponent=exponent,
        taker_only=schedule.get("takerOnly") if isinstance(schedule.get("takerOnly"), bool) else None,
        rebate_rate=_optional_decimal(schedule.get("rebateRate")) if schedule else None,
    )
    closed = bool(payload.get("closed"))
    active_flag = bool(payload.get("active")) and not closed
    status = "closed" if closed else ("active" if active_flag else "unknown")
    return NormalizedMarket(
        venue_id=venue_id,
        market_id=str(payload["id"]),
        event_id=_event_id(payload),
        series_id=None,
        title=str(payload["question"]),
        rules_text=rules,
        rules_sha256=sha256_text(rules),
        status=status,
        result=None,
        close_time_utc=_optional_str(payload.get("endDate")),
        expiration_time_utc=_optional_str(payload.get("endDate")),
        outcomes=outcomes,
        currency="USDC",
        notional="1",
        fee=fee,
        raw_request_id=request_id,
        active=active_flag and bool(payload.get("acceptingOrders", True)),
        orderbook_enabled=bool(payload.get("enableOrderBook", True)) and "YES" in outcomes and "NO" in outcomes,
        extra={
            "slug": payload.get("slug"),
            "condition_id": payload.get("conditionId"),
            "fee_type": payload.get("feeType"),
        },
    )


def normalize_kalshi_market(payload: dict[str, Any], *, request_id: str, venue_id: str, fee: FeeSpec | None = None) -> NormalizedMarket:
    if not isinstance(payload, dict) or not payload.get("ticker") or not payload.get("title"):
        raise ValueError("SCHEMA_CHANGED")
    if payload.get("mve_collection_ticker") or payload.get("market_type") not in (None, "binary"):
        raise ValueError("non_binary_skipped")
    ticker = str(payload["ticker"])
    parts = [str(payload.get("rules_primary") or "").strip(), str(payload.get("rules_secondary") or "").strip()]
    early = str(payload.get("early_close_condition") or "").strip()
    if early:
        parts.append("Early close condition: " + early)
    rules = "\n".join(part for part in parts if part)
    result = payload.get("result")
    if result is not None:
        result = str(result).strip() or None
    status = str(payload.get("status") or "unknown")
    return NormalizedMarket(
        venue_id=venue_id,
        market_id=ticker,
        event_id=_optional_str(payload.get("event_ticker")),
        series_id=ticker.split("-", 1)[0],
        title=str(payload["title"]),
        rules_text=rules,
        rules_sha256=sha256_text(rules),
        status=status,
        result=result,
        close_time_utc=_optional_str(payload.get("close_time")),
        expiration_time_utc=_optional_str(payload.get("expiration_time")),
        outcomes={"YES": f"{ticker}:YES", "NO": f"{ticker}:NO"},
        currency="USD",
        notional=_optional_str(payload.get("notional_value_dollars")),
        fee=fee or FeeSpec.unknown("kalshi series fee not loaded yet", source="kalshi.series"),
        raw_request_id=request_id,
        active=status in {"active", "open"},
        orderbook_enabled=status in {"active", "open"},
        extra={
            "strike_type": payload.get("strike_type"),
            "yes_sub_title": payload.get("yes_sub_title"),
            "no_sub_title": payload.get("no_sub_title"),
            "floor_strike": _json_safe(payload.get("floor_strike")),
        },
    )


def normalize_polymarket_book(
    payload: Any,
    *,
    venue_id: str,
    market_id: str,
    outcome_id: str,
    side: str,
    request_id: str,
    received_at: datetime,
    payload_sha256: str | None,
) -> NormalizedBook:
    reason_codes: list[str] = []
    parse_ok = True
    bids: list[Level] = []
    asks: list[Level] = []
    quote_time = None
    if not isinstance(payload, dict) or "bids" not in payload or "asks" not in payload:
        parse_ok = False
        reason_codes.append(R.SCHEMA_CHANGED)
    else:
        try:
            bids = [_polymarket_level(row) for row in payload.get("bids") or []]
            asks = [_polymarket_level(row) for row in payload.get("asks") or []]
            quote_time = parse_clob_timestamp(payload.get("timestamp"))
        except ValueError:
            parse_ok = False
            reason_codes.append(R.SCHEMA_CHANGED)
            bids, asks = [], []
    if parse_ok and not bids and not asks:
        reason_codes.append(R.EMPTY_BOOK)
    elif parse_ok and not asks:
        reason_codes.append(R.MISSING_SIDE)
    return NormalizedBook(
        venue_id=venue_id,
        market_id=market_id,
        outcome_id=outcome_id,
        side=side,
        bids=_sort_bids(bids),
        asks=_sort_asks(asks),
        quote_time_utc=isoformat_utc(quote_time),
        quote_time_status="KNOWN" if quote_time is not None else "UNKNOWN",
        received_at_utc=isoformat_utc(received_at) or "",
        request_id=request_id,
        payload_sha256=payload_sha256,
        parse_ok=parse_ok,
        reason_codes=reason_codes,
    )


def normalize_kalshi_book(
    payload: Any,
    *,
    venue_id: str,
    market_id: str,
    request_id: str,
    received_at: datetime,
    payload_sha256: str | None,
) -> dict[str, NormalizedBook]:
    """Return YES and NO books. Asks are implied from the opposite bids. Empty side is missing, not zero."""
    failure: list[str] = []
    yes_asks: list[Level] = []
    no_asks: list[Level] = []
    yes_bids: list[Level] = []
    no_bids: list[Level] = []
    parse_ok = True
    if not isinstance(payload, dict) or not isinstance(payload.get("orderbook_fp"), dict):
        parse_ok = False
        failure.append(R.SCHEMA_CHANGED)
    else:
        book = payload["orderbook_fp"]
        if "yes_dollars" not in book or "no_dollars" not in book:
            parse_ok = False
            failure.append(R.SCHEMA_CHANGED)
        else:
            try:
                yes_bid_levels = _kalshi_bid_levels(book.get("yes_dollars") or [])
                no_bid_levels = _kalshi_bid_levels(book.get("no_dollars") or [])
                yes_bids = yes_bid_levels
                no_bids = no_bid_levels
                yes_asks = [Level(price=Decimal("1") - level.price, size=level.size) for level in no_bid_levels]
                no_asks = [Level(price=Decimal("1") - level.price, size=level.size) for level in yes_bid_levels]
            except ValueError:
                parse_ok = False
                failure = [R.SCHEMA_CHANGED]
                yes_asks, no_asks, yes_bids, no_bids = [], [], [], []
    # Kalshi public orderbook payloads observed in B1 do not carry an exchange timestamp.
    source_keys = ("timestamp", "ts", "as_of", "updated_time")
    quote_time = None
    if isinstance(payload, dict):
        for key in source_keys:
            if payload.get(key):
                quote_time = _optional_datetime(payload.get(key))
                break
        nested = payload.get("orderbook_fp") if isinstance(payload.get("orderbook_fp"), dict) else {}
        if quote_time is None:
            for key in source_keys:
                if nested.get(key):
                    quote_time = _optional_datetime(nested.get(key))
                    break
    books = {}
    for side, bids, asks in (("YES", yes_bids, yes_asks), ("NO", no_bids, no_asks)):
        codes = list(failure)
        if parse_ok and not asks and not bids:
            codes.append(R.EMPTY_BOOK)
        elif parse_ok and not asks:
            codes.append(R.MISSING_SIDE)
        books[side] = NormalizedBook(
            venue_id=venue_id,
            market_id=market_id,
            outcome_id=f"{market_id}:{side}",
            side=side,
            bids=_sort_bids(bids),
            asks=_sort_asks(asks),
            quote_time_utc=isoformat_utc(quote_time),
            quote_time_status="KNOWN" if quote_time is not None else "UNKNOWN",
            received_at_utc=isoformat_utc(received_at) or "",
            request_id=request_id,
            payload_sha256=payload_sha256,
            parse_ok=parse_ok,
            reason_codes=_dedupe(codes),
        )
    return books


def parse_clob_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if number > Decimal("100000000000"):
        seconds = int(number // Decimal(1000))
    elif number > Decimal("1000000000"):
        seconds = int(number)
    else:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _polymarket_level(row: Any) -> Level:
    if not isinstance(row, dict) or "price" not in row or "size" not in row:
        raise ValueError("SCHEMA_CHANGED")
    price = require_decimal(row["price"])
    size = require_decimal(row["size"])
    if price < 0 or price > 1 or size < 0:
        raise ValueError("SCHEMA_CHANGED")
    return Level(price=price, size=size)


def _kalshi_bid_levels(rows: Any) -> list[Level]:
    if not isinstance(rows, list):
        raise ValueError("SCHEMA_CHANGED")
    levels: list[Level] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            raise ValueError("SCHEMA_CHANGED")
        price = require_decimal(row[0])
        size = require_decimal(row[1])
        if price < 0 or price > 1 or size < 0:
            raise ValueError("SCHEMA_CHANGED")
        if size == 0:
            continue
        levels.append(Level(price=price, size=size))
    return levels


def _sort_asks(levels: list[Level]) -> list[Level]:
    return sorted(levels, key=lambda level: (level.price, -level.size))


def _sort_bids(levels: list[Level]) -> list[Level]:
    return sorted(levels, key=lambda level: (-level.price, -level.size))


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _optional_decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if value is None or isinstance(value, bool) or isinstance(value, float):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return parse_clob_timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_id(payload: dict[str, Any]) -> str | None:
    events = payload.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return _optional_str(events[0].get("id") or events[0].get("slug"))
    return _optional_str(payload.get("eventId") or payload.get("groupItemTitle"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _dedupe(codes: list[str]) -> list[str]:
    seen: list[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen
