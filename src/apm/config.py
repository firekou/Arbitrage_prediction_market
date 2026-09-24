"""Load configs/research.yaml. The file uses a small YAML subset (no anchors)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> ResearchConfig:
    text = Path(path).read_text(encoding="utf-8")
    data = parse_yaml_subset(text)
    if data.get("readonly") is not True:
        raise ValueError("configs/research.yaml must set readonly: true")
    pm = data["polymarket"]
    ka = data["kalshi"]
    return ResearchConfig(
        schema_version=str(data["schema_version"]),
        readonly=True,
        max_active_markets_per_venue=int(data["max_active_markets_per_venue"]),
        max_markets_per_event=int(data["max_markets_per_event"]),
        max_catalog_pages=int(data["max_catalog_pages"]),
        max_books_per_venue=int(data["max_books_per_venue"]),
        min_books_target=int(data["min_books_target"]),
        request_timeout_seconds=float(data["request_timeout_seconds"]),
        max_retries=int(data["max_retries"]),
        max_consecutive_failures=int(data["max_consecutive_failures"]),
        pause_seconds=float(data["pause_seconds"]),
        max_quote_age_seconds=Decimal(str(data["max_quote_age_seconds"])),
        max_leg_skew_seconds=Decimal(str(data["max_leg_skew_seconds"])),
        clock_ahead_tolerance_seconds=Decimal(str(data["clock_ahead_tolerance_seconds"])),
        research_quantity=Decimal(str(data["research_quantity"])),
        buffer=Decimal(str(data["buffer"])),
        other_cost=Decimal(str(data["other_cost"])),
        min_net_edge=Decimal(str(data["min_net_edge"])),
        polymarket_venue_id=str(pm["venue_id"]),
        polymarket_gamma_base=str(pm["gamma_base"]).rstrip("/"),
        polymarket_clob_base=str(pm["clob_base"]).rstrip("/"),
        polymarket_topics=tuple(str(x) for x in pm.get("topic_queries", [])),
        kalshi_venue_id=str(ka["venue_id"]),
        kalshi_rest_base=str(ka["rest_base"]).rstrip("/"),
        kalshi_fee_coefficient=Decimal(str(ka["fee_base_coefficient"])),
        kalshi_fee_schedule_version=str(ka["fee_schedule_version"]),
        kalshi_fee_rounding=str(ka["fee_rounding"]),
    )


@dataclass(frozen=True)
class ResearchConfig:
    schema_version: str
    readonly: bool
    max_active_markets_per_venue: int
    max_markets_per_event: int
    max_catalog_pages: int
    max_books_per_venue: int
    min_books_target: int
    request_timeout_seconds: float
    max_retries: int
    max_consecutive_failures: int
    pause_seconds: float
    max_quote_age_seconds: Decimal
    max_leg_skew_seconds: Decimal
    clock_ahead_tolerance_seconds: Decimal
    research_quantity: Decimal
    buffer: Decimal
    other_cost: Decimal
    min_net_edge: Decimal
    polymarket_venue_id: str
    polymarket_gamma_base: str
    polymarket_clob_base: str
    polymarket_topics: tuple[str, ...]
    kalshi_venue_id: str
    kalshi_rest_base: str
    kalshi_fee_coefficient: Decimal
    kalshi_fee_schedule_version: str
    kalshi_fee_rounding: str


def parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse indentation-based maps and lists. Strings, bools, nulls, and numbers."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"yaml indent must be multiples of 2: {raw!r}")
        lines.append((indent, raw.strip()))
    value, index = _parse_block(lines, 0, 0)
    if index != len(lines):
        raise ValueError("yaml parser did not consume the document")
    if not isinstance(value, dict):
        raise ValueError("yaml root must be a mapping")
    return value


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    kind_line = lines[index][1]
    if kind_line.startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_map(lines, index, indent)


def _parse_map(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        level, text = lines[index]
        if level < indent:
            break
        if level > indent:
            raise ValueError(f"unexpected indent: {text}")
        if text.startswith("- "):
            break
        key, _, rest = text.partition(":")
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest == "":
            if index < len(lines) and lines[index][0] > level:
                child, index = _parse_block(lines, index, lines[index][0])
                result[key] = child
            else:
                result[key] = {}
        else:
            result[key] = _scalar(rest)
    return result, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        level, text = lines[index]
        if level < indent:
            break
        if level != indent or not text.startswith("- "):
            break
        item = text[2:].strip()
        index += 1
        if item == "":
            child, index = _parse_block(lines, index, lines[index][0])
            result.append(child)
        else:
            result.append(_scalar(item))
    return result, index


def _scalar(text: str) -> Any:
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    try:
        if "." in text:
            return float(text)
    except ValueError:
        pass
    return text
