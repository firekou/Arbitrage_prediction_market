"""Readonly CLI: discover, snapshot, scan, replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apm.config import load_config
from apm.pipeline import discover_catalogs, replay, scan, snapshot_books


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apm", description="Readonly prediction-market research screen")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Fetch capped public market catalogs")
    _add_evidence_args(discover)

    snapshot = sub.add_parser("snapshot", help="Fetch order books for a prior discover directory")
    _add_evidence_args(snapshot)

    scan_parser = sub.add_parser("scan", help="Catalog, books, pairs, and the conservative screen")
    _add_evidence_args(scan_parser)
    scan_parser.add_argument("--report", default="reports/APM-B1-READONLY-001.md")
    scan_parser.add_argument("--pairs", default="docs/PAIR_REVIEW_QUEUE.md")

    replay_parser = sub.add_parser("replay", help="Recompute a stored scan without the network")
    replay_parser.add_argument("--evidence", required=True)

    args = parser.parse_args(argv)
    if args.command == "replay":
        result = replay(Path(args.evidence))
        print(json.dumps(result, indent=2, sort_keys=True))
        if result["mismatches"] or result["opportunity_replay_inserted"] != 0 or not result["manifest_ok"]:
            return 1
        return 0
    config = load_config(args.config)
    evidence = Path(args.evidence)
    if args.command == "discover":
        discover_catalogs(config, evidence_dir=evidence, base_sha=args.base_sha)
        return 0
    if args.command == "snapshot":
        snapshot_books(config, evidence_dir=evidence)
        return 0
    report = scan(
        config,
        evidence_dir=evidence,
        report_path=Path(args.report),
        pair_queue_path=Path(args.pairs),
        base_sha=args.base_sha,
    )
    print(json.dumps({"status": report["status"], "pairs": report["pair_count"], "executable": report["executable_count"]}, indent=2))
    return 0


def _add_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="configs/research.yaml")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--base-sha", default="UNKNOWN")
