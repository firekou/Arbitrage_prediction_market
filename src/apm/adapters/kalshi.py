"""Kalshi official public REST. No SDK. Multivariate combos are excluded."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote, quote_plus

from apm import reasons as R
from apm.adapters.base import FetchBatch
from apm.config import ResearchConfig
from apm.fees import ScheduledFee, kalshi_fee_spec, select_scheduled_fee
from apm.http_client import HttpClient, stamp_source_time
from apm.models import FeeSpec, NormalizedMarket, parse_iso_utc
from apm.normalizer import normalize_kalshi_book, normalize_kalshi_market


class KalshiAdapter:
    def __init__(self, client: HttpClient, config: ResearchConfig) -> None:
        self.client = client
        self.config = config
        self.venue_id = config.kalshi_venue_id
        self.consecutive_failures = 0

    def discover(self) -> FetchBatch:
        batch = FetchBatch()
        seen: set[str] = set()
        per_event: dict[str, int] = {}
        cursor: str | None = None
        pages = 0
        while pages < self.config.max_catalog_pages and len(batch.markets) < self.config.max_active_markets_per_venue:
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                batch.full_success = False
                batch.reason_codes.append(R.RATE_LIMITED)
                batch.notes.append("stopped kalshi discovery after consecutive failures")
                break
            url = (
                f"{self.config.kalshi_rest_base}/markets?status=open&limit=100&mve_filter=exclude"
            )
            if cursor:
                url += "&cursor=" + quote(cursor, safe="")
            response = self.client.get_json(url, venue_id=self.venue_id, kind="kalshi_markets")
            batch.captures.append(response.capture)
            pages += 1
            payload = response.json_value
            if response.capture.http_status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
                self._fail(batch, schema=response.capture.http_status == 200, failure_code=response.capture.failure_code)
                if batch.pages_ok:
                    if R.PAGINATION_INTERRUPTED not in batch.reason_codes:
                        batch.reason_codes.append(R.PAGINATION_INTERRUPTED)
                break
            self._ok(batch)
            for row in payload["markets"]:
                if len(batch.markets) >= self.config.max_active_markets_per_venue:
                    break
                if not isinstance(row, dict):
                    continue
                event_id = str(row.get("event_ticker") or "")
                if per_event.get(event_id, 0) >= self.config.max_markets_per_event:
                    continue
                ticker = str(row.get("ticker") or "")
                if not ticker or ticker in seen:
                    continue
                try:
                    market = normalize_kalshi_market(row, request_id=response.capture.request_id, venue_id=self.venue_id)
                except ValueError:
                    continue
                market.extra["fee_inputs"] = {
                    "series_fee_type": None,
                    "series_multiplier": None,
                    "changes": [],
                    "series_loaded": False,
                    "event_fees_loaded": False,
                }
                seen.add(ticker)
                per_event[event_id] = per_event.get(event_id, 0) + 1
                batch.markets.append(market)
            next_cursor = payload.get("cursor") or ""
            if not next_cursor or next_cursor == cursor:
                cursor = None
                break
            cursor = str(next_cursor)
        batch.capped = len(batch.markets) >= self.config.max_active_markets_per_venue or cursor is not None
        batch.notes.append("open binary markets only; mve_filter=exclude; capped stratified sample")
        self._load_fees(batch)
        return batch

    def snapshot_books(self, markets: list[NormalizedMarket]) -> FetchBatch:
        batch = FetchBatch(markets=list(markets))
        for market in markets:
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                batch.full_success = False
                batch.reason_codes.append(R.RATE_LIMITED)
                batch.notes.append("stopped kalshi book reads after consecutive failures")
                break
            if not market.orderbook_enabled:
                continue
            url = f"{self.config.kalshi_rest_base}/markets/{quote(market.market_id, safe='')}/orderbook"
            response = self.client.get_json(
                url,
                venue_id=self.venue_id,
                kind="kalshi_book",
                market_id=market.market_id,
            )
            received = parse_iso_utc(response.capture.received_at_utc)
            assert received is not None
            parsed = normalize_kalshi_book(
                response.json_value,
                venue_id=self.venue_id,
                market_id=market.market_id,
                request_id=response.capture.request_id,
                received_at=received,
                payload_sha256=response.capture.payload_sha256,
            )
            stamp_source_time(response.capture, None)
            batch.captures.append(response.capture)
            batch.books.extend(parsed.values())
            ok = response.capture.http_status == 200 and all(book.parse_ok for book in parsed.values())
            if ok:
                self._ok(batch)
            else:
                self._fail(batch, schema=response.capture.http_status == 200, failure_code=response.capture.failure_code)
        return batch

    def _load_fees(self, batch: FetchBatch) -> None:
        series_ids = sorted({market.series_id for market in batch.markets if market.series_id})
        series_payloads: dict[str, tuple[dict[str, Any], str]] = {}
        for series_id in series_ids:
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                batch.full_success = False
                batch.notes.append("stopped kalshi series fee reads after consecutive failures")
                break
            url = f"{self.config.kalshi_rest_base}/series/{quote(series_id, safe='')}"
            response = self.client.get_json(url, venue_id=self.venue_id, kind="kalshi_series", market_id=series_id)
            batch.captures.append(response.capture)
            payload = response.json_value
            series = payload.get("series") if isinstance(payload, dict) else None
            if response.capture.http_status != 200 or not isinstance(series, dict):
                self._fail(batch, schema=response.capture.http_status == 200, failure_code=response.capture.failure_code)
                continue
            self._ok(batch)
            series_payloads[series_id] = (series, response.capture.received_at_utc)
        event_ids = sorted({market.event_id for market in batch.markets if market.event_id})
        event_changes: dict[str, list[dict[str, Any]]] = {}
        for event_id in event_ids:
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                batch.full_success = False
                batch.notes.append("stopped kalshi event fee reads after consecutive failures")
                break
            url = (
                f"{self.config.kalshi_rest_base}/events/fee_changes?event_ticker={quote_plus(event_id)}"
                "&show_historical=true"
            )
            response = self.client.get_json(url, venue_id=self.venue_id, kind="kalshi_event_fees", market_id=event_id)
            batch.captures.append(response.capture)
            payload = response.json_value
            changes = payload.get("event_fee_changes") if isinstance(payload, dict) else None
            if response.capture.http_status != 200 or not isinstance(changes, list):
                self._fail(batch, schema=response.capture.http_status == 200, failure_code=response.capture.failure_code)
                continue
            self._ok(batch)
            event_changes[event_id] = [row for row in changes if isinstance(row, dict)]
        for market in batch.markets:
            series_row = series_payloads.get(market.series_id or "")
            inputs = market.extra.setdefault("fee_inputs", {})
            if series_row:
                series, received_at = series_row
                inputs["series_fee_type"] = series.get("fee_type")
                multiplier = series.get("fee_multiplier")
                inputs["series_multiplier"] = format(Decimal(str(multiplier)), "f") if multiplier is not None and not isinstance(multiplier, bool) else None
                inputs["series_loaded"] = True
                inputs["series_received_at_utc"] = received_at
            if market.event_id in event_changes:
                inputs["event_fees_loaded"] = True
                inputs["changes"] = [_change_dict(row) for row in event_changes[market.event_id]]
            as_of = parse_iso_utc(inputs.get("series_received_at_utc")) if inputs.get("series_loaded") else None
            market.fee = resolve_kalshi_fee(market, as_of=as_of, config=self.config)

    def _ok(self, batch: FetchBatch) -> None:
        batch.pages_ok += 1
        self.consecutive_failures = 0

    def _fail(self, batch: FetchBatch, *, schema: bool, failure_code: str | None) -> None:
        batch.pages_failed += 1
        batch.full_success = False
        self.consecutive_failures += 1
        code = R.SCHEMA_CHANGED if schema else (failure_code or "TRANSPORT_ERROR")
        if code not in batch.reason_codes:
            batch.reason_codes.append(code)


def resolve_kalshi_fee(market: NormalizedMarket, *, as_of: datetime | None, config: ResearchConfig) -> FeeSpec:
    inputs = market.extra.get("fee_inputs") or {}
    if not inputs.get("series_loaded") or not inputs.get("event_fees_loaded"):
        return FeeSpec.unknown("kalshi series fee or event fee schedule was not loaded", source="kalshi.series")
    series_type = inputs.get("series_fee_type")
    series_multiplier = _decimal_or_none(inputs.get("series_multiplier"))
    changes: list[ScheduledFee] = []
    for row in inputs.get("changes") or []:
        scheduled = parse_iso_utc(row.get("scheduled_ts"))
        multiplier = _decimal_or_none(row.get("multiplier"))
        fee_type = row.get("fee_type")
        change_id = row.get("id")
        if scheduled is None or multiplier is None or not fee_type or not change_id:
            return FeeSpec.unknown("kalshi event fee change row is incomplete", source="kalshi.events.fee_changes")
        changes.append(
            ScheduledFee(
                change_id=str(change_id),
                fee_type=str(fee_type),
                multiplier=multiplier,
                scheduled_at=scheduled,
            )
        )
    fee_type, multiplier, version_id = select_scheduled_fee(
        series_fee_type=str(series_type) if series_type else None,
        series_multiplier=series_multiplier,
        changes=changes,
        as_of=as_of,
    )
    return kalshi_fee_spec(
        fee_type=fee_type,
        multiplier=multiplier,
        coefficient=config.kalshi_fee_coefficient,
        schedule_version=config.kalshi_fee_schedule_version,
        rounding_rule=config.kalshi_fee_rounding,
        version_id=version_id,
        effective_at_utc=as_of.isoformat().replace("+00:00", "Z") if as_of else None,
        source="kalshi.series+events.fee_changes",
    )


def _change_dict(row: dict[str, Any]) -> dict[str, str | None]:
    multiplier = row.get("fee_multiplier_override")
    return {
        "id": str(row.get("id") or ""),
        "fee_type": str(row.get("fee_type_override") or ""),
        "multiplier": format(Decimal(str(multiplier)), "f") if multiplier is not None and not isinstance(multiplier, bool) else None,
        "scheduled_ts": str(row.get("scheduled_ts") or ""),
    }


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
