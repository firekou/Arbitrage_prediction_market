from __future__ import annotations

from dataclasses import dataclass, field

from apm.models import NormalizedBook, NormalizedMarket, RawCapture


@dataclass
class FetchBatch:
    markets: list[NormalizedMarket] = field(default_factory=list)
    books: list[NormalizedBook] = field(default_factory=list)
    captures: list[RawCapture] = field(default_factory=list)
    full_success: bool = True
    reason_codes: list[str] = field(default_factory=list)
    pages_ok: int = 0
    pages_failed: int = 0
    capped: bool = False
    notes: list[str] = field(default_factory=list)
