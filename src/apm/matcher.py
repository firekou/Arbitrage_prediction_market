"""Candidate pairing. Text overlap is not settlement equivalence and cannot approve a pair."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from apm import reasons as R
from apm.models import Features, NormalizedMarket, PairCandidate

_STOP = frozenset(
    """
    a an the of to will be in on at by for and or after before following
    market price above below over under than least most this that with from
    into during than per than its if then otherwise yes no than
    """.split()
)
_ALIASES = {
    "federal": "fed",
    "btc": "bitcoin",
    "eth": "ethereum",
    "rates": "rate",
    "funds": "rate",
}
_ANCHORS = frozenset({"bitcoin", "ethereum", "fed", "cpi", "inflation", "temperature", "nasdaq", "recession"})

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_TZ = ("UTC", "GMT", "EDT", "EST", "ET", "CDT", "CST", "CT", "PDT", "PST", "PT")
_SOURCES = (
    ("chainlink", "chainlink"),
    ("twap", "twap"),
    ("federal reserve", "federal_reserve"),
    ("fomc", "federal_reserve"),
    ("bureau of labor", "bls"),
    ("bls", "bls"),
    ("coinbase", "coinbase"),
    ("binance", "binance"),
    ("cf benchmarks", "cf_benchmarks"),
    ("associated press", "associated_press"),
    ("uma", "uma"),
    ("national weather service", "nws"),
    ("noaa", "noaa"),
)
_CANCEL = (
    ("refund", "refund"),
    ("void", "void"),
    ("cancel", "cancel"),
    ("postpon", "postponed"),
    ("overtime", "overtime"),
    ("extra time", "extra_time"),
    ("push", "push"),
)


def extract_features(title: str, rules: str) -> Features:
    title_dates, title_masked = _extract_dates(title)
    rule_dates, _ = _extract_dates(rules)
    numbers = _numbers(title_masked)
    return Features(
        subject_tokens=frozenset(_tokens(title_masked)),
        numbers=frozenset(numbers),
        dates=frozenset(title_dates or rule_dates),
        operators=frozenset(_operators(title) or _operators(rules)),
        timezones=frozenset(_find_timezones(f"{title}\n{rules}")),
        sources=frozenset(_phrases(rules or title, _SOURCES)),
        cancel_refund=frozenset(_phrases(f"{title}\n{rules}", _CANCEL)),
    )


def compare_features(left: Features, right: Features) -> dict:
    differences: list[str] = []
    if left.numbers and right.numbers and left.numbers != right.numbers:
        differences.append("threshold")
    if left.dates and right.dates and left.dates.isdisjoint(right.dates):
        differences.append("date")
    if left.operators and right.operators and left.operators != right.operators:
        differences.append("operator")
    if left.timezones and right.timezones and left.timezones.isdisjoint(right.timezones):
        differences.append("timezone")
    if left.sources and right.sources and left.sources.isdisjoint(right.sources):
        differences.append("settlement_source")
    if _cancel_conflict(left.cancel_refund, right.cancel_refund):
        differences.append("cancel_refund")
    return {
        "differences": differences,
        "jaccard": format(_jaccard(left.subject_tokens, right.subject_tokens), "f"),
        "left": _feature_dict(left),
        "right": _feature_dict(right),
        "rules_relation": "inconsistent" if differences else "unconfirmed",
    }


def build_review_queue(
    left_markets: Iterable[NormalizedMarket],
    right_markets: Iterable[NormalizedMarket],
    *,
    limit: int = 10,
    min_jaccard: float = 0.34,
    reject_jaccard: float = 0.28,
    max_per_subject: int = 2,
) -> list[PairCandidate]:
    """Aim for a mix of likely-same (still PRICE_GAP_ONLY) and should-reject pairs."""
    left_rows = [(market, extract_features(_surface(market), market.rules_text)) for market in left_markets]
    right_rows = [(market, extract_features(_surface(market), market.rules_text)) for market in right_markets]
    likely: list[tuple[float, PairCandidate]] = []
    reject: list[tuple[float, PairCandidate]] = []
    for left_market, left_features in left_rows:
        for right_market, right_features in right_rows:
            compared = compare_features(left_features, right_features)
            score = float(compared["jaccard"])
            differences: list[str] = compared["differences"]
            shared_anchor = bool((left_features.subject_tokens & right_features.subject_tokens) & _ANCHORS)
            reject_floor = 0.15 if shared_anchor else reject_jaccard
            if differences and score < reject_floor:
                continue
            if not differences and score < min_jaccard:
                continue
            if not left_features.subject_tokens or not right_features.subject_tokens:
                continue
            status = R.REJECTED if differences else R.PRICE_GAP_ONLY
            pair = PairCandidate(
                pair_id=_pair_id(left_market, right_market),
                left_venue=left_market.venue_id,
                left_market_id=left_market.market_id,
                right_venue=right_market.venue_id,
                right_market_id=right_market.market_id,
                left_title=_display_title(left_market),
                right_title=_display_title(right_market),
                review_status=status,
                direction_mapping="UNCONFIRMED",
                rules_sha256_left=left_market.rules_sha256,
                rules_sha256_right=right_market.rules_sha256,
                differences=differences,
                comparison=compared,
                score=f"{score:.6f}",
            )
            bucket = reject if differences else likely
            bucket.append((score, pair))
    selected = _mix(likely, reject, limit=limit, max_per_subject=max_per_subject)
    return selected


def _mix(
    likely: list[tuple[float, PairCandidate]],
    reject: list[tuple[float, PairCandidate]],
    *,
    limit: int,
    max_per_subject: int,
) -> list[PairCandidate]:
    del max_per_subject  # anchor spread below replaces a single subject cap
    likely_sorted = sorted(likely, key=lambda item: item[0], reverse=True)
    reject_sorted = sorted(reject, key=lambda item: item[0], reverse=True)
    chosen: list[PairCandidate] = []
    seen: set[str] = set()
    per_anchor: dict[str, int] = {}

    def try_add(pair: PairCandidate, anchor_cap: int) -> bool:
        if len(chosen) >= limit or pair.pair_id in seen:
            return False
        if any(existing.left_market_id == pair.left_market_id or existing.right_market_id == pair.right_market_id for existing in chosen):
            return False
        anchor = _anchor_of(pair)
        if per_anchor.get(anchor, 0) >= anchor_cap:
            return False
        chosen.append(pair)
        seen.add(pair.pair_id)
        per_anchor[anchor] = per_anchor.get(anchor, 0) + 1
        return True

    def one_per_anchor(pool: list[tuple[float, PairCandidate]]) -> None:
        covered: set[str] = set()
        for _, pair in pool:
            anchor = _anchor_of(pair)
            if anchor in covered:
                continue
            if try_add(pair, 1):
                covered.add(anchor)

    one_per_anchor(likely_sorted)
    one_per_anchor(reject_sorted)
    for _, pair in reject_sorted:
        try_add(pair, 4)
    for _, pair in likely_sorted:
        try_add(pair, 4)
    return chosen


def _anchor_of(pair: PairCandidate) -> str:
    left = set(pair.comparison.get("left", {}).get("subject_tokens", []))
    right = set(pair.comparison.get("right", {}).get("subject_tokens", []))
    shared = sorted((left & right) & _ANCHORS)
    if shared:
        return shared[0]
    return _subject_key(pair)


def _subject_key(pair: PairCandidate) -> str:
    tokens = re.findall(r"[a-z0-9]+", pair.left_title.lower())
    kept = [token for token in tokens if token not in _STOP and len(token) > 2][:3]
    return " ".join(kept)


def _display_title(market: NormalizedMarket) -> str:
    subtitle = str((market.extra or {}).get("yes_sub_title") or "").strip()
    if subtitle and subtitle not in market.title:
        return f"{market.title} [{subtitle}]"
    return market.title


def _pair_id(left: NormalizedMarket, right: NormalizedMarket) -> str:
    digest = hashlib.sha256(f"{left.venue_id}:{left.market_id}|{right.venue_id}:{right.market_id}".encode()).hexdigest()
    return "pair_" + digest[:12]


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _feature_dict(features: Features) -> dict[str, list[str]]:
    return {
        "subject_tokens": sorted(features.subject_tokens),
        "numbers": sorted(features.numbers),
        "dates": sorted(features.dates),
        "operators": sorted(features.operators),
        "timezones": sorted(features.timezones),
        "sources": sorted(features.sources),
        "cancel_refund": sorted(features.cancel_refund),
    }


def _surface(market: NormalizedMarket) -> str:
    parts = [market.title]
    for key in ("yes_sub_title", "floor_strike"):
        value = market.extra.get(key) if market.extra else None
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _tokens(title: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    kept: list[str] = []
    for word in words:
        if word in _STOP or word.isdigit() or len(word) <= 2 or word in _MONTHS:
            continue
        word = _ALIASES.get(word, word)
        if word.endswith("s") and len(word) > 4 and not word.endswith("ss"):
            word = word[:-1]
        kept.append(word)
    return kept


def _numbers(text: str) -> list[str]:
    found = []
    for match in re.finditer(r"\d+(?:\.\d+)?", text):
        raw = match.group(0)
        value = raw[:-1] if raw.endswith(".0") else raw
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.append(value)
    return found


def _operators(text: str) -> set[str]:
    lowered = text.lower()
    masked = lowered
    found: set[str] = set()
    replacements = (
        (">=", (r">=", r"≥", r"\bat least\b", r"\bor above\b", r"\bor more\b", r"\bor higher\b")),
        ("<=", (r"<=", r"≤", r"\bat most\b", r"\bor below\b", r"\bor less\b", r"\bor lower\b")),
        (">", (r">", r"\bgreater than\b", r"\bmore than\b", r"\babove\b", r"\bover\b", r"\bhigher than\b")),
        ("<", (r"<", r"\bless than\b", r"\bbelow\b", r"\bunder\b", r"\blower than\b")),
    )
    for label, patterns in replacements:
        for pattern in patterns:
            if re.search(pattern, masked):
                found.add(label)
                masked = re.sub(pattern, " ", masked)
    return found


def _extract_dates(text: str) -> tuple[list[str], str]:
    found: list[str] = []
    masked = text

    def _sub(pattern: str, repl) -> None:
        nonlocal masked

        def _replace(match: re.Match[str]) -> str:
            found.append(repl(match))
            return " "

        masked = re.sub(pattern, _replace, masked, flags=re.IGNORECASE)

    _sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    _sub(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})\b",
        lambda m: _month_day(m.group(1), m.group(2), m.group(3)),
    )
    _sub(
        r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b",
        lambda m: _month_day(m.group(2), m.group(1), m.group(3)),
    )
    _sub(
        r"\b([A-Za-z]{3,9})\s+(\d{4})\b",
        lambda m: _month_only(m.group(1), m.group(2)),
    )
    cleaned = [item for item in found if item]
    return cleaned, masked


def _month_day(month: str, day: str, year: str) -> str:
    number = _MONTHS.get(month.lower())
    if not number:
        return ""
    return f"{int(year):04d}-{number:02d}-{int(day):02d}"


def _month_only(month: str, year: str) -> str:
    number = _MONTHS.get(month.lower())
    if not number:
        return ""
    return f"{int(year):04d}-{number:02d}"


def _find_timezones(text: str) -> list[str]:
    found = []
    for zone in _TZ:
        if re.search(rf"\b{zone}\b", text):
            found.append(zone)
    return found


def _phrases(text: str, table: tuple[tuple[str, str], ...]) -> list[str]:
    lowered = text.lower()
    found = []
    for needle, label in table:
        if needle in lowered:
            found.append(label)
    return found


def _cancel_conflict(left: frozenset[str], right: frozenset[str]) -> bool:
    if not left or not right:
        return False
    return left != right
