"""GET-only HTTP client with timeouts, bounded retries, and raw capture.

There is no method that sends a request body. Callers cannot place orders
through this client.
"""

from __future__ import annotations

import hashlib
import json
import ssl
from decimal import Decimal
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from apm import SCHEMA_VERSION
from apm.models import RawCapture, isoformat_utc, utc_now
from apm.reasons import RATE_LIMITED

ALLOWED_HOSTS = frozenset(
    {
        "gamma-api.polymarket.com",
        "clob.polymarket.com",
        "external-api.kalshi.com",
    }
)

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass
class ExchangeResponse:
    capture: RawCapture
    body: bytes | None
    json_value: Any | None
    json_error: str | None


class ScriptedTransport:
    """Test double. Each script item is (status, headers, body) or an Exception."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[str] = []

    def send(self, url: str, timeout: float) -> tuple[int, dict[str, str], bytes]:
        self.calls.append(url)
        if not self.script:
            raise RuntimeError("scripted transport exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        status, headers, body = item
        if isinstance(body, str):
            body = body.encode("utf-8")
        return status, {k.lower(): v for k, v in headers.items()}, body


class UrllibTransport:
    def __init__(self) -> None:
        self._ssl = ssl.create_default_context()

    def send(self, url: str, timeout: float) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "apm-b1-readonly/0.1 (research; no-orders)",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self._ssl) as response:
                body = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                return response.status, headers, body
        except urllib.error.HTTPError as exc:
            body = exc.read()
            headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            return exc.code, headers, body


class HttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        max_retries: int = 2,
        pause_seconds: float = 0,
        transport: Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.pause_seconds = pause_seconds
        self.transport = transport or UrllibTransport()
        self.sleeper = sleeper
        self.clock = clock
        self.requests = 0
        self.successes = 0
        self.failures = 0
        self._last_started: datetime | None = None

    def get_json(self, url: str, *, venue_id: str, kind: str, market_id: str | None = None, outcome_id: str | None = None) -> ExchangeResponse:
        self._ensure_get_allowlist(url)
        self._pause()
        attempts = 0
        last_capture: RawCapture | None = None
        last_body: bytes | None = None
        while True:
            attempts += 1
            self.requests += 1
            started = self.clock()
            self._last_started = started
            status: int | None = None
            headers: dict[str, str] = {}
            body: bytes | None = None
            error: str | None = None
            failure_code: str | None = None
            try:
                status, headers, body = self.transport.send(url, self.timeout_seconds)
            except Exception as exc:  # network errors are data, not control flow from payloads
                error = f"{type(exc).__name__}: {exc}"
                failure_code = RATE_LIMITED if "429" in str(exc) else "TRANSPORT_ERROR"
            received = self.clock()
            duration_ms = int((received - started).total_seconds() * 1000)
            payload_hash = hashlib.sha256(body).hexdigest() if body is not None else None
            text = _decode_body(body) if body is not None else None
            if status == 429:
                failure_code = RATE_LIMITED
                error = error or "HTTP 429"
            elif status is not None and status >= 400:
                failure_code = failure_code or f"HTTP_{status}"
                error = error or f"HTTP {status}"
            capture = RawCapture(
                request_id=str(uuid.uuid4()),
                venue_id=venue_id,
                kind=kind,
                url=url,
                market_id=market_id,
                outcome_id=outcome_id,
                request_started_at_utc=isoformat_utc(started) or "",
                received_at_utc=isoformat_utc(received) or "",
                request_duration_ms=max(duration_ms, 0),
                http_status=status,
                source_timestamp=None,
                source_timestamp_status="UNKNOWN",
                payload_sha256=payload_hash,
                schema_version=SCHEMA_VERSION,
                sequence=None,
                error=error,
                failure_code=failure_code,
                attempt_count=attempts,
                raw_response=text,
            )
            last_capture = capture
            last_body = body
            retryable = failure_code == "TRANSPORT_ERROR" or status in _RETRY_STATUSES
            if retryable and attempts <= self.max_retries:
                self.sleeper(_retry_delay(headers, attempts))
                continue
            break
        assert last_capture is not None
        if last_capture.http_status == 200 and last_body is not None:
            self.successes += 1
        else:
            self.failures += 1
        parsed, json_error = _parse_json(last_body if last_capture.http_status == 200 else last_body)
        if last_capture.http_status != 200:
            parsed = None
        return ExchangeResponse(capture=last_capture, body=last_body, json_value=parsed, json_error=json_error)

    def _pause(self) -> None:
        if self.pause_seconds <= 0 or self._last_started is None:
            return
        elapsed = (self.clock() - self._last_started).total_seconds()
        remaining = self.pause_seconds - elapsed
        if remaining > 0:
            self.sleeper(remaining)

    @staticmethod
    def _ensure_get_allowlist(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise ValueError(f"refusing non-https URL: {url}")
        if parts.hostname not in ALLOWED_HOSTS:
            raise ValueError(f"host is not on the readonly allowlist: {parts.hostname}")
        if parts.username or parts.password:
            raise ValueError("refusing URL with userinfo")


def _retry_delay(headers: dict[str, str], attempt: int) -> float:
    raw = headers.get("retry-after")
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0
    return 0.0 if attempt else 0.0


def _decode_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _parse_json(body: bytes | None) -> tuple[Any | None, str | None]:
    if body is None:
        return None, "empty body"
    try:
        return json.loads(body.decode("utf-8"), parse_float=Decimal), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def stamp_source_time(capture: RawCapture, source: datetime | None) -> RawCapture:
    capture.source_timestamp = isoformat_utc(source)
    capture.source_timestamp_status = "KNOWN" if source is not None else "UNKNOWN"
    if capture.source_timestamp is None:
        capture.source_timestamp_status = "UNKNOWN"
    return capture
