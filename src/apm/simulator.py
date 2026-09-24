"""Fill ledger used to prove a single leg is not locked profit.

Nothing here submits an order. Rows are local research records.
"""

from __future__ import annotations

from decimal import Decimal

from apm.reasons import SINGLE_LEG_NOT_LOCKED


class Ledger:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    def apply(self, fills: list[dict]) -> dict:
        inserted = 0
        for fill in fills:
            key = (str(fill["run_id"]), str(fill["fill_id"]))
            if key in self.rows:
                continue
            self.rows[key] = dict(fill)
            inserted += 1
        return {"inserted": inserted, "rows": len(self.rows)}

    def summary(self, run_id: str) -> dict:
        rows = [row for row in self.rows.values() if row["run_id"] == run_id]
        successful = [row for row in rows if row.get("success")]
        cost = sum((Decimal(str(row["cost"])) for row in successful), Decimal("0"))
        return {
            "run_id": run_id,
            "fills": len(rows),
            "successful_fills": len(successful),
            "cost": format(cost, "f"),
        }

    def locked_profit(self, run_id: str, strategy_id: str, payout_per_share: Decimal) -> dict:
        successful = [
            row
            for row in self.rows.values()
            if row["run_id"] == run_id and row["strategy_id"] == strategy_id and row.get("success")
        ]
        legs = {row["leg"] for row in successful}
        if len(legs) < 2:
            return {
                "locked": False,
                "locked_profit": "0",
                "reason": SINGLE_LEG_NOT_LOCKED,
                "legs": sorted(legs),
            }
        quantities: dict[str, Decimal] = {}
        cost = Decimal("0")
        for row in successful:
            quantities[row["leg"]] = quantities.get(row["leg"], Decimal("0")) + Decimal(str(row["qty"]))
            cost += Decimal(str(row["cost"]))
        if len(set(quantities.values())) != 1:
            return {
                "locked": False,
                "locked_profit": "0",
                "reason": SINGLE_LEG_NOT_LOCKED,
                "legs": sorted(legs),
            }
        quantity = next(iter(quantities.values()))
        profit = payout_per_share * quantity - cost
        return {"locked": True, "locked_profit": format(profit, "f"), "reason": None, "legs": sorted(legs)}
