"""Discover, snapshot, screen, and replay. Live scans never set a confirmed payout."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from apm import SCHEMA_VERSION, reasons as R
from apm.adapters.kalshi import KalshiAdapter, resolve_kalshi_fee
from apm.adapters.polymarket import PolymarketAdapter
from apm.config import ResearchConfig
from apm.engine import AskBook, evaluate_complement
from apm.http_client import HttpClient
from apm.matcher import build_review_queue
from apm.models import FeeSpec, NormalizedBook, NormalizedMarket, decimal_json, parse_iso_utc
from apm.reporter import write_pair_queue, write_scan_report
from apm.store import EvidenceStore

WORK_ID = "APM-B1-READONLY-001"


def discover_catalogs(config: ResearchConfig, *, evidence_dir: Path, base_sha: str) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if any(evidence_dir.iterdir()):
        raise SystemExit(f"evidence directory is not empty: {evidence_dir}")
    client = HttpClient(
        timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        pause_seconds=config.pause_seconds,
    )
    store = EvidenceStore(evidence_dir)
    polymarket = PolymarketAdapter(client, config)
    kalshi = KalshiAdapter(client, config)
    pm_catalog = polymarket.discover()
    ka_catalog = kalshi.discover()
    store.append_captures(pm_catalog.captures)
    store.append_captures(ka_catalog.captures)
    store.write_json("normalized_markets.json", {"polymarket": pm_catalog.markets, "kalshi": ka_catalog.markets})
    summary = {
        "polymarket_markets": len(pm_catalog.markets),
        "kalshi_markets": len(ka_catalog.markets),
        "polymarket_full_success": pm_catalog.full_success,
        "kalshi_full_success": ka_catalog.full_success,
        "polymarket_reasons": pm_catalog.reason_codes,
        "kalshi_reasons": ka_catalog.reason_codes,
        "http": {"requests": client.requests, "successes": client.successes, "failures": client.failures},
        "base_sha": base_sha,
    }
    store.write_json("discover_summary.json", summary)
    store.close()
    return summary


def snapshot_books(config: ResearchConfig, *, evidence_dir: Path) -> dict[str, Any]:
    markets_path = evidence_dir / "normalized_markets.json"
    if not markets_path.exists():
        raise SystemExit("snapshot requires discover output normalized_markets.json")
    if (evidence_dir / "books.json").exists():
        raise SystemExit("books.json already exists; refusing to append a second snapshot")
    payload = json.loads(markets_path.read_text(encoding="utf-8"))
    pm_markets = [_market_from_dict(row) for row in payload["polymarket"]]
    ka_markets = [_market_from_dict(row) for row in payload["kalshi"]]
    client = HttpClient(
        timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        pause_seconds=config.pause_seconds,
    )
    store = EvidenceStore(evidence_dir)
    polymarket = PolymarketAdapter(client, config)
    kalshi = KalshiAdapter(client, config)
    pm_chosen = _select_for_books(pm_markets, [market.market_id for market in pm_markets], config.max_books_per_venue)
    ka_chosen = _select_for_books(ka_markets, [market.market_id for market in ka_markets], config.max_books_per_venue)
    pm_books = polymarket.snapshot_books(pm_chosen)
    ka_books = kalshi.snapshot_books(ka_chosen)
    store.append_captures(pm_books.captures)
    store.append_captures(ka_books.captures)
    store.write_json("books.json", {"polymarket": pm_books.books, "kalshi": ka_books.books})
    summary = {
        "polymarket_markets_with_parseable_book": _venue_stats(type("C", (), {"markets": pm_markets, "full_success": True, "pages_ok": 0, "pages_failed": 0, "reason_codes": [], "notes": [], "capped": True})(), pm_books, len(pm_chosen))["markets_with_parseable_book"],
        "kalshi_markets_with_parseable_book": _venue_stats(type("C", (), {"markets": ka_markets, "full_success": True, "pages_ok": 0, "pages_failed": 0, "reason_codes": [], "notes": [], "capped": True})(), ka_books, len(ka_chosen))["markets_with_parseable_book"],
        "http": {"requests": client.requests, "successes": client.successes, "failures": client.failures},
    }
    store.write_json("snapshot_summary.json", summary)
    store.close()
    return summary


def _market_from_dict(payload: dict) -> NormalizedMarket:
    fee_payload = payload["fee"]
    market = NormalizedMarket(
        venue_id=payload["venue_id"],
        market_id=payload["market_id"],
        event_id=payload.get("event_id"),
        series_id=payload.get("series_id"),
        title=payload["title"],
        rules_text=payload.get("rules_text") or "",
        rules_sha256=payload.get("rules_sha256") or "",
        status=payload.get("status") or "unknown",
        result=payload.get("result"),
        close_time_utc=payload.get("close_time_utc"),
        expiration_time_utc=payload.get("expiration_time_utc"),
        outcomes=dict(payload.get("outcomes") or {}),
        currency=payload.get("currency"),
        notional=payload.get("notional"),
        fee=_fee_from_dict(fee_payload),
        raw_request_id=payload.get("raw_request_id") or "",
        active=bool(payload.get("active")),
        orderbook_enabled=bool(payload.get("orderbook_enabled")),
        schema_version=payload.get("schema_version") or SCHEMA_VERSION,
        extra=dict(payload.get("extra") or {}),
    )
    return market


def scan(config: ResearchConfig, *, evidence_dir: Path, report_path: Path, pair_queue_path: Path, base_sha: str) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if any(evidence_dir.iterdir()):
        raise SystemExit(f"evidence directory is not empty: {evidence_dir}")
    client = HttpClient(
        timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        pause_seconds=config.pause_seconds,
    )
    store = EvidenceStore(evidence_dir)
    polymarket = PolymarketAdapter(client, config)
    kalshi = KalshiAdapter(client, config)
    pm_catalog = polymarket.discover()
    ka_catalog = kalshi.discover()
    store.append_captures(pm_catalog.captures)
    store.append_captures(ka_catalog.captures)

    pairs = build_review_queue(pm_catalog.markets, ka_catalog.markets, limit=10)
    pm_books_for = _select_for_books(pm_catalog.markets, [pair.left_market_id for pair in pairs], config.max_books_per_venue)
    ka_books_for = _select_for_books(ka_catalog.markets, [pair.right_market_id for pair in pairs], config.max_books_per_venue)
    pm_books = polymarket.snapshot_books(pm_books_for)
    ka_books = kalshi.snapshot_books(ka_books_for)
    store.append_captures(pm_books.captures)
    store.append_captures(ka_books.captures)

    _refresh_kalshi_fees(ka_catalog.markets, ka_books.books, config)
    screens = _screens(config, pm_catalog.markets, ka_catalog.markets, pm_books.books, ka_books.books, pairs)
    run_id = WORK_ID
    opportunity_rows = []
    for index, screen in enumerate(screens):
        screen["opportunity_id"] = f"{run_id}:{index}"
        opportunity_rows.append(screen)
    first_insert = store.record_opportunities(run_id, opportunity_rows)
    computations = [_computation_input(config, screen) for screen in screens if screen.get("stored_input")]

    head = _git_head()
    venues = {
        config.polymarket_venue_id: _venue_stats(pm_catalog, pm_books, len(pm_books_for)),
        config.kalshi_venue_id: _venue_stats(ka_catalog, ka_books, len(ka_books_for)),
    }
    reason_counts = Counter(code for screen in screens for code in screen["result"]["reason_codes"])
    executable = sum(1 for screen in screens if screen["result"]["executable"])
    price_gap = sum(1 for screen in screens if screen["result"]["approval_status"] == R.PRICE_GAP_ONLY)
    rejected = sum(1 for screen in screens if screen["result"]["approval_status"] == R.REJECTED)
    pm_depth = venues[config.polymarket_venue_id]["markets_with_parseable_book"]
    ka_depth = venues[config.kalshi_venue_id]["markets_with_parseable_book"]
    blockers = []
    if pm_depth < 5:
        blockers.append(f"polymarket parseable books cover {pm_depth} markets; B1 asked for at least 5")
    if ka_depth < 5:
        blockers.append(f"kalshi parseable books cover {ka_depth} markets; B1 asked for at least 5")
    status = "READY_FOR_GPT_REVIEW" if not blockers else "BLOCKED_WITH_EVIDENCE"
    evaluated_at = max(
        [screen["result_received_at"] for screen in screens if screen.get("result_received_at")],
        default=head["now"],
    )
    report = {
        "work_id": WORK_ID,
        "status": status,
        "base_sha": base_sha,
        "implementation_head_at_scan": head["sha"],
        "evaluated_at_utc": evaluated_at,
        "schema_version": SCHEMA_VERSION,
        "commands": [
            {
                "command": "PYTHONPATH=src python3 -m unittest discover -s tests -v",
                "exit_code": "see report footer after the operator run",
            },
            {
                "command": "PYTHONPATH=src python3 -m apm scan --config configs/research.yaml --evidence evidence/APM-B1-READONLY-001 --report reports/APM-B1-READONLY-001.md --pairs docs/PAIR_REVIEW_QUEUE.md --base-sha "
                + base_sha,
                "exit_code": "see report footer after the operator run",
            },
        ],
        "http": {"requests": client.requests, "successes": client.successes, "failures": client.failures},
        "venues": venues,
        "pair_count": len(pairs),
        "same_market_screens": sum(1 for screen in screens if screen["strategy"] == "same_market_yes_no"),
        "cross_market_screens": sum(1 for screen in screens if screen["strategy"].startswith("cross_")),
        "executable_count": executable,
        "price_gap_only_count": price_gap,
        "rejected_count": rejected,
        "reason_counts": dict(reason_counts),
        "screen_sample": [
            {
                "strategy": screen["strategy"],
                "market_ids": screen["market_ids"],
                "q": screen["result"]["q"],
                "approval_status": screen["result"]["approval_status"],
                "executable": screen["result"]["executable"],
                "reason_codes": screen["result"]["reason_codes"],
                "hypothetical_price_gap": screen["result"]["hypothetical_price_gap"],
                "net_edge": screen["result"]["net_edge"],
            }
            for screen in screens[:30]
        ],
        "evidence_dir": str(evidence_dir),
        "raw_jsonl": str(store.jsonl_path),
        "raw_records": _count_lines(store.jsonl_path),
        "manifest_path": str(evidence_dir / "manifest.json"),
        "done": [
            "Readonly Polymarket international Gamma/CLOB and Kalshi REST adapters with a GET host allowlist",
            "Raw captures store URL, request time, receive time, body, and payload SHA-256; missing quote times stay UNKNOWN",
            "Pair queue mixes parsed likely-same and should-reject cases and never writes APPROVED",
            "Decimal engine walks ask levels for same-market and both cross directions",
            "Unit tests cover fee wipeout, second-level depth, Kalshi bid inversion, empty books, stale and missing times, unknown fees, inconsistent rules, single-leg fills, and replay idempotency",
        ],
        "not_done": [
            "No pair is settlement-APPROVED; live payout is not fixed at 1",
            "Polymarket US is not queried",
            "PMXT is not attached",
            "No WebSocket, no 24h observation, no order path",
            "Kalshi public order books in this batch have no exchange timestamp, so those legs fail TIMESTAMP_UNKNOWN",
            "Cross-venue USD vs USDC is CURRENCY_UNKNOWN until a reviewed conversion exists",
            "Kalshi taker fee uses the July 2026 quadratic coefficient with a non-direct cent upper bound, not a direct-member exact fee",
        ],
        "blockers": blockers,
        "next_steps": [
            "GPT reviews this head and the raw manifest before any rule is marked settlement-equivalent",
            "Keep the 5-second age and 2-second skew gates; do not relax them to manufacture an executable row",
            "B2 can add a human rule review on docs/PAIR_REVIEW_QUEUE.md and a PMXT capability probe",
        ],
        "opportunity_insert": first_insert,
        "scanner_completed": True,
    }
    if any(row["result"]["approval_status"] == "APPROVED" for row in screens):
        raise RuntimeError("scan produced APPROVED")

    store.write_json("normalized_markets.json", {"polymarket": pm_catalog.markets, "kalshi": ka_catalog.markets})
    store.write_json("books.json", {"polymarket": pm_books.books, "kalshi": ka_books.books})
    store.write_json("pairs.json", pairs)
    store.write_json("screens.json", screens)
    store.write_json("computations.json", computations)
    store.write_json("scan_result.json", report)
    manifest = _manifest(evidence_dir, base_sha=base_sha, head=head["sha"])
    store.write_json("manifest.json", manifest)
    markets_by_id = {
        (market.venue_id, market.market_id): decimal_json(market)
        for market in [*pm_catalog.markets, *ka_catalog.markets]
    }
    write_pair_queue(pair_queue_path, [decimal_json(pair) for pair in pairs], markets_by_id=markets_by_id)
    write_scan_report(report_path, report)
    store.close()
    return report


def replay(evidence_dir: Path) -> dict[str, Any]:
    computations_path = evidence_dir / "computations.json"
    computations = json.loads(computations_path.read_text(encoding="utf-8"))
    mismatches = []
    for row in computations:
        result = _evaluate_stored(row)
        if result.as_dict() != row["expected"]:
            mismatches.append(row["opportunity_id"])
    store = EvidenceStore(evidence_dir)
    screens = json.loads((evidence_dir / "screens.json").read_text(encoding="utf-8"))
    run_id = WORK_ID
    inserted = store.record_opportunities(run_id, screens)
    store.close()
    manifest_ok, manifest_errors = _verify_manifest(evidence_dir)
    return {
        "computations": len(computations),
        "mismatches": mismatches,
        "opportunity_replay_inserted": inserted["inserted"],
        "opportunity_rows": inserted["rows"],
        "manifest_ok": manifest_ok,
        "manifest_errors": manifest_errors,
    }


def _screens(config, pm_markets, ka_markets, pm_books, ka_books, pairs) -> list[dict]:
    pm_market = {market.market_id: market for market in pm_markets}
    ka_market = {market.market_id: market for market in ka_markets}
    pm_side = _index_books(pm_books)
    ka_side = _index_books(ka_books)
    age = timedelta(seconds=float(config.max_quote_age_seconds))
    skew = timedelta(seconds=float(config.max_leg_skew_seconds))
    ahead = timedelta(seconds=float(config.clock_ahead_tolerance_seconds))
    rows: list[dict] = []
    for market in [*pm_markets, *ka_markets]:
        sides = pm_side if market.venue_id == config.polymarket_venue_id else ka_side
        yes = sides.get((market.market_id, "YES"))
        no = sides.get((market.market_id, "NO"))
        if yes is None or no is None:
            continue
        result = evaluate_complement(
            strategy="same_market_yes_no",
            books=[("YES", _ask(yes)), ("NO", _ask(no))],
            fees=[market.fee, market.fee],
            currencies=[market.currency, market.currency],
            quantity=config.research_quantity,
            other_cost=config.other_cost,
            buffer=config.buffer,
            payout_per_share=None,
            rules_status="unknown",
            max_quote_age=age,
            max_leg_skew=skew,
            clock_ahead_tolerance=ahead,
            min_net_edge=config.min_net_edge,
        )
        rows.append(
            _screen_row(
                "same_market_yes_no",
                [market.market_id],
                result,
                [("YES", yes), ("NO", no)],
                [market.fee, market.fee],
                [market.currency, market.currency],
                config,
                "unknown",
            )
        )
    for pair in pairs:
        left = pm_market.get(pair.left_market_id)
        right = ka_market.get(pair.right_market_id)
        if left is None or right is None:
            continue
        rules_status = "inconsistent" if pair.differences else "unknown"
        for strategy, left_side, right_side in (
            ("cross_a_yes_b_no", "YES", "NO"),
            ("cross_b_yes_a_no", "NO", "YES"),
        ):
            book_left = pm_side.get((left.market_id, left_side))
            book_right = ka_side.get((right.market_id, right_side))
            if book_left is None or book_right is None:
                rows.append(
                    {
                        "strategy": strategy,
                        "market_ids": [left.market_id, right.market_id],
                        "pair_id": pair.pair_id,
                        "result": {
                            "strategy": strategy,
                            "executable": False,
                            "approval_status": R.REJECTED if pair.differences else R.PRICE_GAP_ONLY,
                            "reason_codes": [R.MISSING_SIDE],
                            "q": format(config.research_quantity, "f"),
                            "gross_edge": None,
                            "net_edge": None,
                            "fee_total": None,
                            "hypothetical_price_gap": None,
                            "notes": ["book not in the capped snapshot"],
                        },
                        "result_received_at": None,
                        "stored_input": None,
                    }
                )
                continue
            result = evaluate_complement(
                strategy=strategy,
                books=[(left_side, _ask(book_left)), (right_side, _ask(book_right))],
                fees=[left.fee, right.fee],
                currencies=[left.currency, right.currency],
                quantity=config.research_quantity,
                other_cost=config.other_cost,
                buffer=config.buffer,
                payout_per_share=None,
                rules_status=rules_status,
                max_quote_age=age,
                max_leg_skew=skew,
                clock_ahead_tolerance=ahead,
                min_net_edge=config.min_net_edge,
            )
            row = _screen_row(
                strategy,
                [left.market_id, right.market_id],
                result,
                [(left_side, book_left), (right_side, book_right)],
                [left.fee, right.fee],
                [left.currency, right.currency],
                config,
                rules_status,
            )
            row["pair_id"] = pair.pair_id
            row["rules_status"] = rules_status
            rows.append(row)
    return rows


def _screen_row(strategy, market_ids, result, named_books, fees, currencies, config, rules_status: str) -> dict:
    received = [book.received_at_utc for _, book in named_books]
    return {
        "strategy": strategy,
        "market_ids": market_ids,
        "result": result.as_dict(),
        "result_received_at": max(received) if received else None,
        "stored_input": {
            "strategy": strategy,
            "books": [
                {
                    "name": name,
                    "asks": [level.as_pair() for level in book.asks],
                    "quote_time_utc": book.quote_time_utc if book.quote_time_status == "KNOWN" else None,
                    "received_at_utc": book.received_at_utc,
                    "open_for_trading": True,
                }
                for name, book in named_books
            ],
            "fees": [decimal_json(fee) for fee in fees],
            "currencies": currencies,
            "quantity": format(config.research_quantity, "f"),
            "other_cost": format(config.other_cost, "f"),
            "buffer": format(config.buffer, "f"),
            "payout_per_share": None,
            "rules_status": rules_status,
            "max_quote_age_seconds": format(config.max_quote_age_seconds, "f"),
            "max_leg_skew_seconds": format(config.max_leg_skew_seconds, "f"),
            "clock_ahead_tolerance_seconds": format(config.clock_ahead_tolerance_seconds, "f"),
            "min_net_edge": format(config.min_net_edge, "f"),
        },
    }


def _computation_input(config: ResearchConfig, screen: dict) -> dict:
    return {
        "opportunity_id": screen["opportunity_id"],
        "input": screen["stored_input"],
        "expected": screen["result"],
    }


def _evaluate_stored(row: dict):
    stored = row["input"]
    if stored is None:
        raise ValueError("missing stored input")
    from decimal import Decimal

    books = []
    for book in stored["books"]:
        from apm.models import Level

        books.append(
            (
                book["name"],
                AskBook(
                    asks=tuple(Level(price=Decimal(price), size=Decimal(size)) for price, size in book["asks"]),
                    quote_time=parse_iso_utc(book["quote_time_utc"]),
                    received_at=parse_iso_utc(book["received_at_utc"]),
                    open_for_trading=book["open_for_trading"],
                ),
            )
        )
    fees = [_fee_from_dict(fee) for fee in stored["fees"]]
    return evaluate_complement(
        strategy=stored["strategy"],
        books=books,
        fees=fees,
        currencies=stored["currencies"],
        quantity=Decimal(stored["quantity"]),
        other_cost=Decimal(stored["other_cost"]),
        buffer=Decimal(stored["buffer"]),
        payout_per_share=Decimal(stored["payout_per_share"]) if stored["payout_per_share"] is not None else None,
        rules_status=stored["rules_status"],
        max_quote_age=timedelta(seconds=float(stored["max_quote_age_seconds"])),
        max_leg_skew=timedelta(seconds=float(stored["max_leg_skew_seconds"])),
        clock_ahead_tolerance=timedelta(seconds=float(stored["clock_ahead_tolerance_seconds"])),
        min_net_edge=Decimal(stored["min_net_edge"]),
    )


def _fee_from_dict(payload: dict) -> FeeSpec:
    from decimal import Decimal

    def dec(value: Any):
        if value is None:
            return None
        return Decimal(str(value))

    return FeeSpec(
        known=bool(payload["known"]),
        model=payload["model"],
        rate=dec(payload.get("rate")),
        multiplier=dec(payload.get("multiplier")),
        exponent=dec(payload.get("exponent")),
        fixed_total=dec(payload.get("fixed_total")),
        currency=payload.get("currency"),
        source=payload.get("source"),
        version=payload.get("version"),
        effective_at_utc=payload.get("effective_at_utc"),
        rounding_rule=payload.get("rounding_rule"),
        taker_only=payload.get("taker_only"),
        fee_bound=payload.get("fee_bound"),
        detail=payload.get("detail"),
    )


def _refresh_kalshi_fees(markets: list[NormalizedMarket], books: list[NormalizedBook], config: ResearchConfig) -> None:
    received_by_market: dict[str, str] = {}
    for book in books:
        current = received_by_market.get(book.market_id)
        if current is None or book.received_at_utc > current:
            received_by_market[book.market_id] = book.received_at_utc
    for market in markets:
        if market.venue_id != config.kalshi_venue_id:
            continue
        if market.market_id not in received_by_market:
            continue
        market.fee = resolve_kalshi_fee(
            market,
            as_of=parse_iso_utc(received_by_market[market.market_id]),
            config=config,
        )


def _select_for_books(markets: list[NormalizedMarket], preferred_ids: list[str], limit: int) -> list[NormalizedMarket]:
    by_id = {market.market_id: market for market in markets}
    chosen: list[NormalizedMarket] = []
    seen: set[str] = set()
    for market_id in preferred_ids:
        market = by_id.get(market_id)
        if market is None or market.market_id in seen or not market.orderbook_enabled:
            continue
        chosen.append(market)
        seen.add(market.market_id)
        if len(chosen) >= limit:
            return chosen
    for market in markets:
        if len(chosen) >= limit:
            break
        if market.market_id in seen or not market.orderbook_enabled or not market.active:
            continue
        chosen.append(market)
        seen.add(market.market_id)
    return chosen


def _index_books(books: list[NormalizedBook]) -> dict[tuple[str, str], NormalizedBook]:
    return {(book.market_id, book.side): book for book in books}


def _ask(book: NormalizedBook) -> AskBook:
    quote = parse_iso_utc(book.quote_time_utc) if book.quote_time_status == "KNOWN" else None
    received = parse_iso_utc(book.received_at_utc)
    if received is None:
        raise ValueError("book missing received_at")
    return AskBook(asks=tuple(book.asks), quote_time=quote, received_at=received, open_for_trading=True)


def _venue_stats(catalog, books, book_markets: int) -> dict[str, Any]:
    parseable: set[str] = set()
    for book in books.books:
        if book.parse_ok and (book.asks or book.bids):
            parseable.add(book.market_id)
    return {
        "markets": len(catalog.markets),
        "catalog_full_success": catalog.full_success,
        "catalog_pages_ok": catalog.pages_ok,
        "catalog_pages_failed": catalog.pages_failed,
        "catalog_reason_codes": catalog.reason_codes,
        "book_markets": book_markets,
        "markets_with_parseable_book": len(parseable),
        "book_full_success": books.full_success,
        "book_pages_ok": books.pages_ok,
        "book_pages_failed": books.pages_failed,
        "reason_codes": sorted(set(catalog.reason_codes + books.reason_codes)),
        "notes": catalog.notes + books.notes,
        "capped": catalog.capped,
    }


def _manifest(root: Path, *, base_sha: str, head: str) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json" or path.suffix == ".sqlite":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": str(path.relative_to(root)), "sha256": digest, "bytes": path.stat().st_size})
    return {
        "work_id": WORK_ID,
        "base_sha": base_sha,
        "implementation_head_at_scan": head,
        "schema_version": SCHEMA_VERSION,
        "files": files,
    }


def _verify_manifest(root: Path) -> tuple[bool, list[str]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.exists():
            errors.append(f"missing {row['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            errors.append(f"hash mismatch {row['path']}")
    return not errors, errors


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _git_head() -> dict[str, str]:
    from datetime import datetime, timezone

    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha = "UNKNOWN"
    return {"sha": sha, "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
