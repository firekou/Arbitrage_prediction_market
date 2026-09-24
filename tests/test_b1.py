"""B1 formula, book, fee, reject, and replay tests.

Synthetic cases live in this module and tests/fixtures/synthetic.
The one trimmed public book is tests/fixtures/live and is labeled live_recorded.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from apm import reasons as R
from apm.adapters.kalshi import KalshiAdapter
from apm.adapters.pmxt import PmxtAdapter
from apm.adapters.polymarket import PolymarketAdapter
from apm.config import ResearchConfig, load_config
from apm.engine import AskBook, evaluate_complement, evaluate_n_outcome, walk_asks
from apm.fees import ScheduledFee, fee_for_fills, kalshi_fee_spec, polymarket_fee_spec, select_scheduled_fee
from apm.http_client import HttpClient, ScriptedTransport
from apm.matcher import compare_features, extract_features
from apm.models import FeeSpec, Level
from apm.normalizer import normalize_kalshi_book, normalize_polymarket_book, normalize_polymarket_market
from apm.simulator import Ledger
from apm.store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
GATES = dict(
    max_quote_age=timedelta(seconds=5),
    max_leg_skew=timedelta(seconds=2),
    clock_ahead_tolerance=timedelta(seconds=2),
)


def book(levels: list[tuple[str, str]], *, quote_delta: int = 1, received_delta: int = 0) -> AskBook:
    return AskBook(
        asks=tuple(Level(Decimal(price), Decimal(size)) for price, size in levels),
        quote_time=NOW - timedelta(seconds=quote_delta),
        received_at=NOW + timedelta(seconds=received_delta),
    )


def zero_fee() -> FeeSpec:
    return FeeSpec(known=True, model="zero", rate=Decimal("0"), currency="USD", rounding_rule="test_zero", fee_bound="exact")


def fixed_fee(amount: str) -> FeeSpec:
    return FeeSpec(
        known=True,
        model="fixed_total",
        fixed_total=Decimal(amount),
        currency="USD",
        rounding_rule="test_fixed",
        fee_bound="exact",
    )


def config(**overrides) -> ResearchConfig:
    base = load_config(ROOT / "configs" / "research.yaml")
    values = base.__dict__.copy()
    values.update(overrides)
    return ResearchConfig(**values)


class FormulaTests(unittest.TestCase):
    def test_gross_five_and_net_one_point_five_and_fee_wipe(self) -> None:
        books = [("YES", book([("0.43", "100")])), ("NO", book([("0.52", "100")]))]
        gross = evaluate_complement(
            strategy="same_market_yes_no",
            books=books,
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("100"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertEqual(gross.gross_edge, Decimal("5"))
        self.assertEqual(gross.net_edge, Decimal("5"))
        self.assertTrue(gross.executable)
        self.assertEqual(gross.approval_status, R.UNREVIEWED)
        self.assertNotEqual(gross.approval_status, "APPROVED")

        net = evaluate_complement(
            strategy="same_market_yes_no",
            books=books,
            fees=[fixed_fee("2"), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("100"),
            other_cost=Decimal("0.5"),
            buffer=Decimal("1"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertEqual(net.fee_total, Decimal("2"))
        self.assertEqual(net.net_edge, Decimal("1.5"))
        self.assertTrue(net.executable)

        wiped = evaluate_complement(
            strategy="same_market_yes_no",
            books=books,
            fees=[fixed_fee("6"), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("100"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.NET_EDGE_NONPOSITIVE, wiped.reason_codes)
        self.assertFalse(wiped.executable)
        self.assertEqual(wiped.net_edge, Decimal("-1"))

    def test_second_level_and_insufficient_depth(self) -> None:
        yes = book([("0.40", "50"), ("0.90", "50")])
        no = book([("0.50", "100")])
        top = evaluate_complement(
            strategy="same_market_yes_no",
            books=[("YES", yes), ("NO", no)],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("50"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertEqual(top.net_edge, Decimal("5"))
        killed = evaluate_complement(
            strategy="same_market_yes_no",
            books=[("YES", yes), ("NO", no)],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("100"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertEqual(killed.costs["YES"], "65.00")
        self.assertIn(R.NET_EDGE_NONPOSITIVE, killed.reason_codes)
        self.assertFalse(killed.executable)

        thin = evaluate_complement(
            strategy="same_market_yes_no",
            books=[("YES", book([("0.40", "10")])), ("NO", book([("0.40", "10")]))],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("100"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.INSUFFICIENT_DEPTH, thin.reason_codes)
        self.assertFalse(thin.executable)

    def test_walk_uses_decimal_fractions_not_floats(self) -> None:
        walked = walk_asks((Level(Decimal("0.10"), Decimal("2.5")),), Decimal("2.5"))
        self.assertEqual(walked.cost, Decimal("0.250"))
        self.assertIsInstance(walked.cost, Decimal)

    def test_times_fees_currency_and_rules_reject(self) -> None:
        fresh = [("YES", book([("0.40", "10")])), ("NO", book([("0.40", "10")]))]
        stale = evaluate_complement(
            strategy="same_market_yes_no",
            books=[("YES", book([("0.40", "10")], quote_delta=30)), ("NO", book([("0.40", "10")]))],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.STALE_QUOTE, stale.reason_codes)

        missing = evaluate_complement(
            strategy="same_market_yes_no",
            books=[
                ("YES", AskBook(asks=(Level(Decimal("0.4"), Decimal("10")),), quote_time=None, received_at=NOW)),
                ("NO", book([("0.4", "10")])),
            ],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.TIMESTAMP_UNKNOWN, missing.reason_codes)
        self.assertIsNone(missing.net_edge)

        skewed = evaluate_complement(
            strategy="same_market_yes_no",
            books=[
                ("YES", book([("0.40", "10")], quote_delta=1)),
                ("NO", book([("0.40", "10")], quote_delta=4)),
            ],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.STALE_QUOTE, skewed.reason_codes)
        self.assertTrue(any(note.startswith("leg_skew_seconds=") for note in skewed.notes))

        unknown_fee = evaluate_complement(
            strategy="same_market_yes_no",
            books=fresh,
            fees=[FeeSpec.unknown("missing"), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.FEE_UNKNOWN, unknown_fee.reason_codes)
        self.assertFalse(unknown_fee.executable)

        unconfirmed = evaluate_complement(
            strategy="cross_a_yes_b_no",
            books=fresh,
            fees=[zero_fee(), zero_fee()],
            currencies=["USDC", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=None,
            rules_status="unknown",
            **GATES,
        )
        self.assertEqual(unconfirmed.approval_status, R.PRICE_GAP_ONLY)
        self.assertIn(R.COMPLEMENTARITY_UNCONFIRMED, unconfirmed.reason_codes)
        self.assertIn(R.CURRENCY_UNKNOWN, unconfirmed.reason_codes)
        self.assertFalse(unconfirmed.executable)
        self.assertIsNotNone(unconfirmed.hypothetical_price_gap)

        inconsistent = evaluate_complement(
            strategy="cross_a_yes_b_no",
            books=fresh,
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=None,
            rules_status="inconsistent",
            **GATES,
        )
        self.assertEqual(inconsistent.approval_status, R.REJECTED)
        self.assertIn(R.RULES_INCONSISTENT, inconsistent.reason_codes)

    def test_empty_book_and_closed_market(self) -> None:
        empty = evaluate_complement(
            strategy="same_market_yes_no",
            books=[
                ("YES", AskBook(asks=(), quote_time=NOW, received_at=NOW)),
                ("NO", AskBook(asks=(), quote_time=NOW, received_at=NOW)),
            ],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("1"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.EMPTY_BOOK, empty.reason_codes)
        closed = evaluate_complement(
            strategy="same_market_yes_no",
            books=[
                ("YES", AskBook(asks=(Level(Decimal("0.4"), Decimal("5")),), quote_time=NOW, received_at=NOW, open_for_trading=False)),
                ("NO", book([("0.4", "5")])),
            ],
            fees=[zero_fee(), zero_fee()],
            currencies=["USD", "USD"],
            quantity=Decimal("1"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            payout_per_share=Decimal("1"),
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.MARKET_CLOSED, closed.reason_codes)

    def test_three_outcome_complete_and_incomplete(self) -> None:
        books = [
            ("A", book([("0.20", "10")])),
            ("B", book([("0.30", "10")])),
            ("C", book([("0.40", "10")])),
        ]
        fees = [zero_fee(), zero_fee(), zero_fee()]
        currencies = ["USD", "USD", "USD"]
        yes = evaluate_n_outcome(
            side="YES",
            books=books,
            fees=fees,
            currencies=currencies,
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            event_complete=True,
            rules_status="confirmed",
            **GATES,
        )
        self.assertEqual(yes.net_edge, Decimal("1.0"))
        no = evaluate_n_outcome(
            side="NO",
            books=books,
            fees=fees,
            currencies=currencies,
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            event_complete=True,
            rules_status="confirmed",
            **GATES,
        )
        # payout (3-1)*10 - (2+3+4) = 20 - 9 = 11
        self.assertEqual(no.net_edge, Decimal("11.0"))
        incomplete = evaluate_n_outcome(
            side="YES",
            books=books,
            fees=fees,
            currencies=currencies,
            quantity=Decimal("10"),
            other_cost=Decimal("0"),
            buffer=Decimal("0"),
            event_complete=False,
            rules_status="confirmed",
            **GATES,
        )
        self.assertIn(R.INCOMPLETE_EVENT, incomplete.reason_codes)
        self.assertFalse(incomplete.executable)
        self.assertIsNone(incomplete.net_edge)


class BookAndFeeTests(unittest.TestCase):
    def test_kalshi_bids_become_opposite_asks_and_empty_book(self) -> None:
        payload = json.loads((ROOT / "tests/fixtures/synthetic/kalshi_orderbook.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["fixture_class"], "synthetic_from_docs")
        books = normalize_kalshi_book(
            payload,
            venue_id="kalshi",
            market_id="EXAMPLE",
            request_id="req",
            received_at=NOW,
            payload_sha256="abc",
        )
        self.assertEqual(books["YES"].asks[0].price, Decimal("0.4400"))
        self.assertEqual(books["YES"].asks[0].size, Decimal("17.00"))
        self.assertEqual(books["NO"].asks[0].price, Decimal("0.5800"))
        self.assertEqual(books["NO"].asks[0].size, Decimal("13.00"))
        self.assertEqual(books["YES"].quote_time_status, "UNKNOWN")
        empty = normalize_kalshi_book(
            {"orderbook_fp": {"yes_dollars": [], "no_dollars": []}},
            venue_id="kalshi",
            market_id="EXAMPLE",
            request_id="req",
            received_at=NOW,
            payload_sha256=None,
        )
        self.assertIn(R.EMPTY_BOOK, empty["YES"].reason_codes)
        self.assertIn(R.EMPTY_BOOK, empty["NO"].reason_codes)
        one_side = normalize_kalshi_book(
            {"orderbook_fp": {"yes_dollars": [["0.4000", "2.5"]], "no_dollars": []}},
            venue_id="kalshi",
            market_id="EXAMPLE",
            request_id="req",
            received_at=NOW,
            payload_sha256=None,
        )
        self.assertIn(R.MISSING_SIDE, one_side["YES"].reason_codes)
        self.assertEqual(one_side["NO"].asks[0].price, Decimal("0.6000"))
        self.assertEqual(one_side["NO"].asks[0].size, Decimal("2.5"))

    def test_live_polymarket_book_sorts_asks_and_ignores_last_trade(self) -> None:
        payload = json.loads((ROOT / "tests/fixtures/live/polymarket_book_trimmed.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["fixture_class"], "live_recorded")
        book_row = normalize_polymarket_book(
            payload,
            venue_id="polymarket_international",
            market_id="1",
            outcome_id=payload["asset_id"],
            side="YES",
            request_id="req",
            received_at=NOW,
            payload_sha256="hash",
        )
        self.assertEqual(book_row.asks[0].price, Decimal("0.043"))
        self.assertNotEqual(book_row.asks[0].price, Decimal(payload["last_trade_price"]))
        self.assertEqual(book_row.quote_time_status, "KNOWN")
        self.assertEqual(book_row.bids[0].price, Decimal("0.041"))

    def test_polymarket_and_kalshi_fees_and_override(self) -> None:
        spec = polymarket_fee_spec(
            fees_enabled=True,
            fee_type="crypto_fees",
            rate=Decimal("0.07"),
            exponent=Decimal("1"),
            taker_only=True,
            rebate_rate=Decimal("0.20"),
        )
        self.assertEqual(fee_for_fills([(Decimal("100"), Decimal("0.50"))], spec), Decimal("1.75000"))
        unknown = polymarket_fee_spec(
            fees_enabled=True,
            fee_type=None,
            rate=None,
            exponent=None,
            taker_only=None,
            rebate_rate=None,
        )
        self.assertFalse(unknown.known)
        kalshi = kalshi_fee_spec(
            fee_type="quadratic",
            multiplier=Decimal("1"),
            coefficient=Decimal("0.07"),
            schedule_version="kalshi-fee-schedule-2026-07-07",
            rounding_rule="non_direct_cent_upper_bound",
            version_id="series_current",
            effective_at_utc="2026-09-24T12:00:00Z",
            source="test",
        )
        self.assertEqual(fee_for_fills([(Decimal("100"), Decimal("0.50"))], kalshi), Decimal("1.75"))
        self.assertEqual(fee_for_fills([(Decimal("100"), Decimal("0.01"))], kalshi), Decimal("0.07"))
        flat = kalshi_fee_spec(
            fee_type="flat",
            multiplier=Decimal("1"),
            coefficient=Decimal("0.07"),
            schedule_version="kalshi-fee-schedule-2026-07-07",
            rounding_rule="non_direct_cent_upper_bound",
            version_id="series_current",
            effective_at_utc=None,
            source="test",
        )
        self.assertFalse(flat.known)
        as_of = NOW
        future = ScheduledFee("later", "quadratic", Decimal("3"), as_of + timedelta(days=1))
        active = ScheduledFee("now", "quadratic", Decimal("2"), as_of - timedelta(seconds=1))
        fee_type, multiplier, version = select_scheduled_fee(
            series_fee_type="quadratic",
            series_multiplier=Decimal("1"),
            changes=[future, active],
            as_of=as_of,
        )
        self.assertEqual((fee_type, multiplier, version), ("quadratic", Decimal("2"), "now"))
        unchanged = select_scheduled_fee(
            series_fee_type="quadratic",
            series_multiplier=Decimal("1"),
            changes=[future],
            as_of=as_of,
        )
        self.assertEqual(unchanged, ("quadratic", Decimal("1"), "series_current"))
        missing_clock = select_scheduled_fee(
            series_fee_type="quadratic",
            series_multiplier=Decimal("1"),
            changes=[active],
            as_of=None,
        )
        self.assertEqual(missing_clock[2], "unknown")

    def test_rules_date_operator_and_cancel_conflict(self) -> None:
        left = extract_features(
            "Will CPI be above 3.0% in October 2026?",
            "Settles on Bureau of Labor Statistics data at 8:30am ET. Refund if the release is cancelled.",
        )
        right = extract_features(
            "Will CPI be at least 3.0% in October 2026?",
            "Settles on Bureau of Labor Statistics data at 8:30am ET. Resolves No if the release is cancelled.",
        )
        compared = compare_features(left, right)
        self.assertIn("operator", compared["differences"])
        self.assertIn("cancel_refund", compared["differences"])
        self.assertNotIn("date", compared["differences"])
        dated = compare_features(
            extract_features("Bitcoin above 100000 on Sep 24, 2026?", "Uses Chainlink."),
            extract_features("Bitcoin above 100000 on Sep 25, 2026?", "Uses Coinbase."),
        )
        self.assertIn("date", dated["differences"])
        self.assertIn("settlement_source", dated["differences"])
        zones = compare_features(
            extract_features("Game ends by 8pm ET", ""),
            extract_features("Game ends by 8pm PT", ""),
        )
        self.assertIn("timezone", zones["differences"])

    def test_queue_keeps_threshold_reject_for_shared_anchor(self) -> None:
        from apm.matcher import build_review_queue
        from apm.models import NormalizedMarket

        def market(venue: str, market_id: str, title: str, rules: str) -> NormalizedMarket:
            return NormalizedMarket(
                venue_id=venue,
                market_id=market_id,
                event_id=None,
                series_id=None,
                title=title,
                rules_text=rules,
                rules_sha256="0",
                status="active",
                result=None,
                close_time_utc=None,
                expiration_time_utc=None,
                outcomes={"YES": "y", "NO": "n"},
                currency="USD",
                notional="1",
                fee=FeeSpec.unknown("test"),
                raw_request_id="r",
                active=True,
                orderbook_enabled=True,
            )

        pairs = build_review_queue(
            [market("polymarket_international", "pm", "Will Bitcoin be above $82,000 on September 24, 2026?", "Chainlink.")],
            [market("kalshi", "ka", "Bitcoin price above $70,000 on Sep 24, 2026?", "CF Benchmarks.")],
            limit=10,
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].review_status, R.REJECTED)
        self.assertIn("threshold", pairs[0].differences)
        self.assertNotEqual(pairs[0].review_status, "APPROVED")
        mixed = build_review_queue(
            [
                market("polymarket_international", "pm-btc", "Will Bitcoin be above $82,000 on September 24, 2026?", "Chainlink."),
                market("polymarket_international", "pm-fed", "Will the Fed decrease interest rates by 25 bps after the October 2026 meeting?", "Federal Reserve."),
            ],
            [
                market("kalshi", "ka-btc", "Bitcoin price above $70,000 on Sep 24, 2026?", "CF Benchmarks."),
                market("kalshi", "ka-fed", "Will the upper bound of the federal funds rate be above 6.00% following the Fed Apr 28, 2027 meeting?", "Federal Reserve."),
            ],
            limit=10,
        )
        anchors = " ".join(pair.left_title + " " + pair.right_title for pair in mixed).lower()
        self.assertIn("bitcoin", anchors)
        self.assertIn("fed", anchors)


class ReplayAndTransportTests(unittest.TestCase):
    def test_single_leg_is_not_locked_and_replay_does_not_double_count(self) -> None:
        ledger = Ledger()
        fills = [
            {"run_id": "run-1", "fill_id": "a", "strategy_id": "pair", "leg": "YES", "qty": "10", "cost": "4", "success": True},
            {"run_id": "run-1", "fill_id": "b", "strategy_id": "pair", "leg": "NO", "qty": "10", "cost": "5", "success": False},
        ]
        first = ledger.apply(fills)
        second = ledger.apply(fills)
        self.assertEqual(first["inserted"], 2)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(ledger.summary("run-1")["fills"], 2)
        locked = ledger.locked_profit("run-1", "pair", Decimal("1"))
        self.assertFalse(locked["locked"])
        self.assertEqual(locked["locked_profit"], "0")
        self.assertEqual(locked["reason"], R.SINGLE_LEG_NOT_LOCKED)
        both = [
            {"run_id": "run-2", "fill_id": "a", "strategy_id": "pair", "leg": "YES", "qty": "10", "cost": "4", "success": True},
            {"run_id": "run-2", "fill_id": "b", "strategy_id": "pair", "leg": "NO", "qty": "10", "cost": "5", "success": True},
        ]
        ledger.apply(both)
        locked_both = ledger.locked_profit("run-2", "pair", Decimal("1"))
        self.assertTrue(locked_both["locked"])
        self.assertEqual(locked_both["locked_profit"], "1")

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(Path(tmp))
            again = store.apply_fills(fills)
            repeated = store.apply_fills(fills)
            store.close()
        self.assertEqual(again["inserted"], 2)
        self.assertEqual(repeated["inserted"], 0)
        self.assertEqual(repeated["rows"], 2)

    def test_retry_after_429_schema_change_and_pagination_interrupt(self) -> None:
        sleeps: list[float] = []
        transport = ScriptedTransport(
            [
                (429, {"Retry-After": "0"}, "{}"),
                (200, {}, json.dumps([_pm_market("m1")])),
            ]
        )
        client = HttpClient(timeout_seconds=1, max_retries=2, pause_seconds=0, transport=transport, sleeper=sleeps.append)
        page = client.get_json("https://gamma-api.polymarket.com/markets", venue_id="polymarket_international", kind="polymarket_markets")
        self.assertEqual(page.capture.http_status, 200)
        self.assertEqual(page.capture.attempt_count, 2)
        self.assertEqual(sleeps, [0.0])

        blocked = ScriptedTransport([(429, {"Retry-After": "0"}, "{}")] * 3)
        failing = HttpClient(timeout_seconds=1, max_retries=2, pause_seconds=0, transport=blocked, sleeper=lambda _s: None)
        denied = failing.get_json("https://gamma-api.polymarket.com/markets", venue_id="polymarket_international", kind="polymarket_markets")
        self.assertEqual(denied.capture.failure_code, R.RATE_LIMITED)
        self.assertEqual(denied.capture.attempt_count, 3)
        self.assertIsNone(denied.json_value)

        schema_transport = ScriptedTransport([(200, {}, json.dumps({"not": "a list"}))])
        schema_client = HttpClient(timeout_seconds=1, max_retries=0, pause_seconds=0, transport=schema_transport, sleeper=lambda _s: None)
        adapter = PolymarketAdapter(
            schema_client,
            config(max_active_markets_per_venue=1, polymarket_topics=(), max_consecutive_failures=1),
        )
        batch = adapter.discover()
        self.assertFalse(batch.full_success)
        self.assertEqual(batch.markets, [])
        self.assertIn(R.SCHEMA_CHANGED, batch.reason_codes)

        market = {
            "ticker": "KXFED-27APR-T6.00",
            "title": "Will the upper bound be above 6.00%?",
            "market_type": "binary",
            "status": "active",
            "event_ticker": "KXFED-27APR",
            "rules_primary": "Greater than 6.00% resolves Yes.",
            "rules_secondary": "",
            "result": "",
            "notional_value_dollars": "1.0000",
        }
        kalshi_transport = ScriptedTransport(
            [
                (200, {}, json.dumps({"markets": [market], "cursor": "next"})),
                (500, {}, "{}"),
                (200, {}, json.dumps({"series": {"ticker": "KXFED", "fee_type": "quadratic", "fee_multiplier": 1}})),
                (200, {}, json.dumps({"event_fee_changes": [], "cursor": ""})),
            ]
        )
        kalshi_client = HttpClient(timeout_seconds=1, max_retries=0, pause_seconds=0, transport=kalshi_transport, sleeper=lambda _s: None)
        kalshi = KalshiAdapter(kalshi_client, config(kalshi_series_tickers=()))
        kalshi_batch = kalshi.discover()
        self.assertFalse(kalshi_batch.full_success)
        self.assertIn(R.PAGINATION_INTERRUPTED, kalshi_batch.reason_codes)
        self.assertEqual(len(kalshi_batch.markets), 1)
        self.assertGreater(kalshi_batch.pages_failed, 0)
        self.assertGreater(kalshi_batch.pages_ok, 0)

    def test_pmxt_is_not_implemented_and_source_has_no_order_paths(self) -> None:
        with self.assertRaises(NotImplementedError):
            PmxtAdapter().discover()
        with self.assertRaises(ValueError):
            normalize_polymarket_market({"id": "1", "question": "q"}, request_id="r", venue_id="polymarket_us")
        banned = ("def place_order", "def cancel_order", "private_key", "def transfer", "def merge_position", "SecureClient")
        offenders = []
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                if token in text:
                    offenders.append(f"{path.name}:{token}")
        self.assertEqual(offenders, [])

    def test_config_is_readonly(self) -> None:
        loaded = load_config(ROOT / "configs" / "research.yaml")
        self.assertTrue(loaded.readonly)
        self.assertEqual(loaded.polymarket_venue_id, "polymarket_international")
        self.assertEqual(loaded.kalshi_fee_coefficient, Decimal("0.07"))
        self.assertEqual(loaded.max_active_markets_per_venue, 100)


def _pm_market(market_id: str) -> dict:
    return {
        "id": market_id,
        "question": "Will it rain?",
        "description": "Resolves Yes on the stated date.",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "outcomes": "[\"Yes\", \"No\"]",
        "clobTokenIds": "[\"yes-token\", \"no-token\"]",
        "feesEnabled": True,
        "feeType": "weather_fees",
        "feeSchedule": {"exponent": 1, "rate": "0.05", "takerOnly": True, "rebateRate": "0.25"},
        "endDate": "2026-10-01T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
