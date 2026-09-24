"""SQLite ledger plus JSONL raw archive. Replays insert the same keys once."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from apm.models import RawCapture, decimal_json


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = root / "raw.jsonl"
        self.db_path = root / "ledger.sqlite"
        self._db = sqlite3.connect(self.db_path)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS fills (
                run_id TEXT NOT NULL,
                fill_id TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                leg TEXT NOT NULL,
                qty TEXT NOT NULL,
                cost TEXT NOT NULL,
                success INTEGER NOT NULL,
                PRIMARY KEY (run_id, fill_id)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                run_id TEXT NOT NULL,
                opportunity_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (run_id, opportunity_id)
            )
            """
        )
        self._db.commit()

    def append_captures(self, captures: Iterable[RawCapture]) -> int:
        count = 0
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            for capture in captures:
                handle.write(json.dumps(decimal_json(capture), ensure_ascii=False, sort_keys=True))
                handle.write("\n")
                count += 1
        return count

    def apply_fills(self, fills: list[dict]) -> dict:
        before = self._db.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
        for fill in fills:
            self._db.execute(
                """
                INSERT OR IGNORE INTO fills (run_id, fill_id, strategy_id, leg, qty, cost, success)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fill["run_id"],
                    fill["fill_id"],
                    fill["strategy_id"],
                    fill["leg"],
                    str(fill["qty"]),
                    str(fill["cost"]),
                    1 if fill.get("success") else 0,
                ),
            )
        self._db.commit()
        total = self._db.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
        return {"inserted": total - before, "rows": total}

    def record_opportunities(self, run_id: str, rows: list[dict]) -> dict:
        before = self._db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        for index, row in enumerate(rows):
            opportunity_id = str(row.get("opportunity_id") or f"{run_id}:{index}")
            self._db.execute(
                "INSERT OR IGNORE INTO opportunities (run_id, opportunity_id, payload) VALUES (?, ?, ?)",
                (run_id, opportunity_id, json.dumps(decimal_json(row), sort_keys=True)),
            )
        self._db.commit()
        inserted_total = self._db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        inserted = inserted_total - before
        total = self._db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        return {"inserted": inserted, "rows": total}

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.root / name
        path.write_text(json.dumps(decimal_json(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def close(self) -> None:
        self._db.close()
