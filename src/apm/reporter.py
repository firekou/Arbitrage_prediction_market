"""Markdown report and pair-review queue. These files describe a screen, not profit."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_pair_queue(path: Path, pairs: list[dict], *, markets_by_id: dict[tuple[str, str], dict]) -> None:
    lines = [
        "# Pair review queue",
        "",
        "Work ID: APM-B1-READONLY-001",
        "",
        "No pair in this file is APPROVED. `PRICE_GAP_ONLY` means the titles are similar enough to review and settlement equivalence is unconfirmed. `REJECTED` means a compared dimension already conflicts (threshold, date, operator, timezone, settlement source, or cancel/refund language). Text similarity is not a payout proof.",
        "",
        f"Queue size: {len(pairs)}",
        "",
    ]
    if len(pairs) < 10:
        lines.append(
            f"Fewer than 10 review pairs were produced from this capped sample ({len(pairs)}). "
            "That count is the sample result, not a target that was filled with synthetic pairs."
        )
        lines.append("")
    likely = sum(1 for pair in pairs if pair["review_status"] == "PRICE_GAP_ONLY")
    rejected = sum(1 for pair in pairs if pair["review_status"] == "REJECTED")
    lines.append(f"Likely-same but unconfirmed: {likely}. Should-reject: {rejected}.")
    lines.append("")
    for index, pair in enumerate(pairs, start=1):
        left = markets_by_id.get((pair["left_venue"], pair["left_market_id"]), {})
        right = markets_by_id.get((pair["right_venue"], pair["right_market_id"]), {})
        lines.extend(
            [
                f"## {index}. `{pair['pair_id']}` — {pair['review_status']}",
                "",
                f"- Left: {pair['left_venue']} `{pair['left_market_id']}` — {pair['left_title']}",
                f"- Right: {pair['right_venue']} `{pair['right_market_id']}` — {pair['right_title']}",
                f"- Direction mapping: {pair['direction_mapping']}",
                f"- Differences: {', '.join(pair['differences']) if pair['differences'] else 'none detected in the parsed dimensions'}",
                f"- Subject Jaccard: {pair['score']}",
                f"- Rules SHA-256 left: `{pair['rules_sha256_left']}`",
                f"- Rules SHA-256 right: `{pair['rules_sha256_right']}`",
                f"- Approval version: none. Reviewer: none.",
                "",
                "### Parsed comparison",
                "",
                "```json",
                _pretty(pair.get("comparison")),
                "```",
                "",
                "### Rules text (left)",
                "",
                left.get("rules_text") or "_missing_",
                "",
                "### Rules text (right)",
                "",
                right.get("rules_text") or "_missing_",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_scan_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# APM-B1-READONLY-001",
        "",
        f"Status: **{report['status']}**",
        "",
        "This is a readonly public-data screen. It is not a live profit result, not a trading approval, and not a GPT review.",
        "",
        "## Identity",
        "",
        f"- work_id: `{report['work_id']}`",
        f"- base_sha: `{report['base_sha']}`",
        f"- implementation_head_at_scan: `{report['implementation_head_at_scan']}`",
        f"- evaluated_at_utc: `{report['evaluated_at_utc']}`",
        f"- schema_version: `{report['schema_version']}`",
        "",
        "## Commands",
        "",
        "Exit codes below are the process results recorded by the operator after the run. The scanner itself writes `scanner_completed` when it finishes and returns 0.",
        "",
    ]
    for command in report.get("commands", []):
        lines.append(
            f"- `{command['command']}` → exit `{command.get('exit_code', 'pending')}`"
        )
    lines.extend(["", "## API counts", ""])
    http = report["http"]
    lines.append(
        f"- HTTP requests (including retries): {http['requests']}; final successes: {http['successes']}; final failures: {http['failures']}"
    )
    for venue, stats in report["venues"].items():
        lines.append(
            f"- {venue}: markets {stats['markets']}, catalog_full_success {stats['catalog_full_success']}, "
            f"catalog_pages_ok {stats['catalog_pages_ok']}, catalog_pages_failed {stats['catalog_pages_failed']}, "
            f"books_requested_markets {stats['book_markets']}, markets_with_parseable_book {stats['markets_with_parseable_book']}, "
            f"book_full_success {stats['book_full_success']}, book_pages_ok {stats['book_pages_ok']}, "
            f"book_pages_failed {stats['book_pages_failed']}, reason_codes {stats['reason_codes']}"
        )
    lines.extend(
        [
            "",
            "## What was computed",
            "",
            f"- Pair candidates: {report['pair_count']} (target was 10; shortfall is reported as-is)",
            f"- Same-market screens: {report['same_market_screens']}",
            f"- Cross-market screens: {report['cross_market_screens']}",
            f"- Executable locked-payout rows: {report['executable_count']}",
            f"- PRICE_GAP_ONLY rows: {report['price_gap_only_count']}",
            f"- Rejected rows: {report['rejected_count']}",
            "",
            "Executable means every mechanical gate passed, including a rules flag the live scan does not set. Live rows stay `PRICE_GAP_ONLY` or `REJECTED`. None are `APPROVED`.",
            "",
            "### Reason code counts",
            "",
        ]
    )
    for code, count in sorted(report["reason_counts"].items()):
        lines.append(f"- `{code}`: {count}")
    lines.extend(["", "### Screen sample", ""])
    for row in report["screen_sample"]:
        lines.append(
            f"- `{row['strategy']}` {row.get('market_ids')} q={row.get('q')} "
            f"approval={row['approval_status']} executable={row['executable']} "
            f"reasons={row['reason_codes']} hypothetical_price_gap={row.get('hypothetical_price_gap')} "
            f"net_edge={row.get('net_edge')}"
        )
    lines.extend(
        [
            "",
            "## Raw manifest and replay",
            "",
            f"- Evidence directory: `{report['evidence_dir']}`",
            f"- Raw JSONL: `{report['raw_jsonl']}` ({report['raw_records']} records)",
            f"- Manifest: `{report['manifest_path']}`",
            "",
            "Replay the stored engine inputs (no network) with:",
            "",
            "```bash",
            "PYTHONPATH=src python3 -m apm replay --evidence evidence/APM-B1-READONLY-001",
            "```",
            "",
            "Replay re-reads `computations.json`, runs the same Decimal engine, and checks exact equality. It also inserts the stored opportunity ids into SQLite a second time; the primary key `(run_id, opportunity_id)` keeps the row count unchanged.",
            "",
            "A missing exchange timestamp is stored as `UNKNOWN`. Receive time is never written into the source-timestamp field.",
            "",
            "## Done",
            "",
        ]
    )
    for item in report["done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Not done", ""])
    for item in report["not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Blockers", ""])
    if report["blockers"]:
        for item in report["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- None that stop the readonly screen from being reviewed.")
    lines.extend(["", "## Next (for GPT, not a self-approval)", ""])
    for item in report["next_steps"]:
        lines.append(f"- {item}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pretty(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
