"""Polymarket international public reads via Gamma and CLOB.

The official py-sdk PublicClient (research pin 1f5ca055) returns typed models and
also exposes trading-adjacent methods. B1 needs the raw HTTP body, request time,
and receive time, and it must not grow an order path. This module therefore
uses a narrow GET allowlist against gamma-api.polymarket.com and
clob.polymarket.com. polymarket_us is never requested.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from apm import reasons as R
from apm.adapters.base import FetchBatch
from apm.config import ResearchConfig
from apm.http_client import HttpClient, stamp_source_time
from apm.models import NormalizedMarket, RawCapture, parse_iso_utc
from apm.normalizer import normalize_polymarket_book, normalize_polymarket_market, parse_clob_timestamp


class PolymarketAdapter:
    def __init__(self, client: HttpClient, config: ResearchConfig) -> None:
        self.client = client
        self.config = config
        self.venue_id = config.polymarket_venue_id
        self.consecutive_failures = 0

    def discover(self) -> FetchBatch:
        batch = FetchBatch()
        seen: set[str] = set()
        self._collect_list(
            batch,
            seen,
            f"{self.config.polymarket_gamma_base}/markets?closed=false&active=true&limit=50"
            "&order=volume24hr&ascending=false",
            kind="polymarket_markets",
        )
        for topic in self.config.polymarket_topics:
            if self._stop(batch):
                break
            self._collect_search(batch, seen, topic)
        if not self._stop(batch) and len(batch.markets) < self.config.max_active_markets_per_venue:
            self._collect_list(
                batch,
                seen,
                f"{self.config.polymarket_gamma_base}/markets?closed=false&active=true&limit="
                f"{self.config.max_active_markets_per_venue}",
                kind="polymarket_markets",
            )
        batch.capped = len(batch.markets) >= self.config.max_active_markets_per_venue
        batch.notes.append("catalog is a capped public sample, not the full venue")
        return batch

    def snapshot_books(self, markets: list[NormalizedMarket]) -> FetchBatch:
        batch = FetchBatch(markets=list(markets))
        for market in markets:
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                batch.full_success = False
                batch.reason_codes.append(R.RATE_LIMITED)
                batch.notes.append("stopped polymarket book reads after consecutive failures")
                break
            if not market.orderbook_enabled:
                continue
            for side in ("YES", "NO"):
                token = market.outcomes.get(side)
                if not token:
                    continue
                url = f"{self.config.polymarket_clob_base}/book?token_id={quote_plus(token)}"
                response = self.client.get_json(
                    url,
                    venue_id=self.venue_id,
                    kind="polymarket_book",
                    market_id=market.market_id,
                    outcome_id=token,
                )
                received = parse_iso_utc(response.capture.received_at_utc)
                assert received is not None
                book = normalize_polymarket_book(
                    response.json_value,
                    venue_id=self.venue_id,
                    market_id=market.market_id,
                    outcome_id=token,
                    side=side,
                    request_id=response.capture.request_id,
                    received_at=received,
                    payload_sha256=response.capture.payload_sha256,
                )
                quote = parse_clob_timestamp(response.json_value.get("timestamp")) if isinstance(response.json_value, dict) else None
                stamp_source_time(response.capture, quote)
                batch.captures.append(response.capture)
                batch.books.append(book)
                self._count(
                    batch,
                    ok=response.capture.http_status == 200 and book.parse_ok,
                    schema=response.capture.http_status == 200 and not book.parse_ok,
                    failure_code=response.capture.failure_code,
                )
        return batch

    def _collect_list(self, batch: FetchBatch, seen: set[str], url: str, kind: str) -> None:
        if self._stop(batch):
            return
        response = self.client.get_json(url, venue_id=self.venue_id, kind=kind)
        batch.captures.append(response.capture)
        if response.capture.http_status != 200 or not isinstance(response.json_value, list):
            self._count(
                batch,
                ok=False,
                schema=response.capture.http_status == 200,
                failure_code=response.capture.failure_code,
            )
            return
        self._count(batch, ok=True)
        added = absorb_gamma_markets(
            response.json_value,
            request_id=response.capture.request_id,
            venue_id=self.venue_id,
            seen=seen,
            remaining=self.config.max_active_markets_per_venue - len(batch.markets),
        )
        batch.markets.extend(added)

    def _collect_search(self, batch: FetchBatch, seen: set[str], topic: str) -> None:
        url = (
            f"{self.config.polymarket_gamma_base}/public-search?q={quote_plus(topic)}"
            "&limit_per_type=3"
        )
        response = self.client.get_json(url, venue_id=self.venue_id, kind="polymarket_search")
        batch.captures.append(response.capture)
        payload = response.json_value
        if response.capture.http_status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            self._count(
                batch,
                ok=False,
                schema=response.capture.http_status == 200,
                failure_code=response.capture.failure_code,
            )
            return
        self._count(batch, ok=True)
        rows: list[dict[str, Any]] = []
        for event in payload["events"]:
            if isinstance(event, dict):
                for market in event.get("markets") or []:
                    if isinstance(market, dict):
                        rows.append(market)
        added = absorb_gamma_markets(
            rows,
            request_id=response.capture.request_id,
            venue_id=self.venue_id,
            seen=seen,
            remaining=self.config.max_active_markets_per_venue - len(batch.markets),
        )
        batch.markets.extend(added)

    def _stop(self, batch: FetchBatch) -> bool:
        if len(batch.markets) >= self.config.max_active_markets_per_venue:
            return True
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            batch.full_success = False
            if R.RATE_LIMITED not in batch.reason_codes:
                batch.reason_codes.append(R.RATE_LIMITED)
            batch.notes.append("stopped polymarket discovery after consecutive failures")
            return True
        return False

    def _count(self, batch: FetchBatch, *, ok: bool, schema: bool = False, failure_code: str | None = None) -> None:
        if ok:
            batch.pages_ok += 1
            self.consecutive_failures = 0
            return
        batch.pages_failed += 1
        batch.full_success = False
        self.consecutive_failures += 1
        code = R.SCHEMA_CHANGED if schema else (failure_code or "TRANSPORT_ERROR")
        if code not in batch.reason_codes:
            batch.reason_codes.append(code)


def absorb_gamma_markets(
    rows: list[Any],
    *,
    request_id: str,
    venue_id: str,
    seen: set[str],
    remaining: int,
) -> list[NormalizedMarket]:
    added: list[NormalizedMarket] = []
    for row in rows:
        if remaining <= 0:
            break
        if not isinstance(row, dict):
            continue
        if row.get("closed") is True or row.get("active") is False:
            continue
        market_id = str(row.get("id") or "")
        if not market_id or market_id in seen:
            continue
        try:
            market = normalize_polymarket_market(row, request_id=request_id, venue_id=venue_id)
        except ValueError:
            continue
        seen.add(market.market_id)
        added.append(market)
        remaining -= 1
    return added


def captures_by_kind(captures: list[RawCapture], kind: str) -> list[RawCapture]:
    return [capture for capture in captures if capture.kind == kind]


def received(capture: RawCapture) -> datetime:
    parsed = parse_iso_utc(capture.received_at_utc)
    if parsed is None:
        raise ValueError("capture missing received_at")
    return parsed
