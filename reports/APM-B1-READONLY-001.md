# APM-B1-READONLY-001

Status: **READY_FOR_GPT_REVIEW**

This is a readonly public-data screen. It is not a live profit result, not a trading approval, and not a GPT review.

## Identity

- work_id: `APM-B1-READONLY-001`
- base_sha: `6df184d7c331ff525fb3bb2b09df3628b16c0611`
- implementation_head_at_scan: `41bc3b3d9da1b3ccbdd16ddbb3b9218d0858eec0`
- The scan ran at that commit. This report and `evidence/APM-B1-READONLY-001/` are added in the child commit. Review the branch tip; it contains both.
- evaluated_at_utc: `2026-09-24T11:24:03.004469Z`
- schema_version: `apm.b1.1`

## Commands

Exit codes below are the process results recorded by the operator after the run. The scanner itself writes `scanner_completed` when it finishes and returns 0.

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → exit `0` (15 tests, OK)
- `PYTHONPATH=src python3 -m apm scan --config configs/research.yaml --evidence evidence/APM-B1-READONLY-001 --report reports/APM-B1-READONLY-001.md --pairs docs/PAIR_REVIEW_QUEUE.md --base-sha 6df184d7c331ff525fb3bb2b09df3628b16c0611` → exit `0`
- `PYTHONPATH=src python3 -m apm replay --evidence evidence/APM-B1-READONLY-001` → exit `0` (68 computations, 0 mismatches, 0 new opportunity rows, manifest ok)

## API counts

- HTTP requests (including retries): 139; final successes: 139; final failures: 0
- polymarket_international: markets 100, catalog_full_success True, catalog_pages_ok 3, catalog_pages_failed 0, books_requested_markets 24, markets_with_parseable_book 24, book_full_success True, book_pages_ok 48, book_pages_failed 0, reason_codes []
- kalshi: markets 100, catalog_full_success True, catalog_pages_ok 64, catalog_pages_failed 0, books_requested_markets 24, markets_with_parseable_book 24, book_full_success True, book_pages_ok 24, book_pages_failed 0, reason_codes []

## What was computed

- Pair candidates: 10. All 10 are REJECTED should-reject cases (Bitcoin, Ether, and Fed). Likely-same count is 0: every high-overlap pair disagreed on threshold, date, operator, timezone, or settlement source. That is the sample, not a hidden approved pair.
- Same-market screens: 48
- Cross-market screens: 20
- Executable locked-payout rows: 0
- PRICE_GAP_ONLY rows: 48
- Rejected rows: 20

Executable means every mechanical gate passed, including a rules flag the live scan does not set. Live rows stay `PRICE_GAP_ONLY` or `REJECTED`. None are `APPROVED`.

### Reason code counts

- `COMPLEMENTARITY_UNCONFIRMED`: 68
- `CURRENCY_UNKNOWN`: 20
- `EMPTY_BOOK`: 3
- `MISSING_SIDE`: 25
- `RULES_INCONSISTENT`: 20
- `RULES_UNKNOWN`: 48
- `STALE_QUOTE`: 13
- `TIMESTAMP_UNKNOWN`: 44

### Screen sample

- `same_market_yes_no` ['2589812'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['2589813'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['3215074'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['2772194'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['2589814'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['4464920'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['4466475'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.20 net_edge=None
- `same_market_yes_no` ['2589810'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['629040'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['4641064'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['4052418'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['665374'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['629030'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['2176270'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['4641123'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.090 net_edge=None
- `same_market_yes_no` ['3128888'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['601819'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.10 net_edge=None
- `same_market_yes_no` ['2046990'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.080 net_edge=None
- `same_market_yes_no` ['559672'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['4641128'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.030 net_edge=None
- `same_market_yes_no` ['4641122'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=-0.010 net_edge=None
- `same_market_yes_no` ['4641107'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['4641083'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['4641085'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'STALE_QUOTE', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-T94799.99'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-T76200'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-B94750'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-B94650'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-B94550'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None
- `same_market_yes_no` ['KXBTC-26SEP2408-B94450'] q=10 approval=PRICE_GAP_ONLY executable=False reasons=['MISSING_SIDE', 'TIMESTAMP_UNKNOWN', 'RULES_UNKNOWN', 'COMPLEMENTARITY_UNCONFIRMED'] hypothetical_price_gap=None net_edge=None

## Raw manifest and replay

- Evidence directory: `evidence/APM-B1-READONLY-001`
- Raw JSONL: `evidence/APM-B1-READONLY-001/raw.jsonl` (139 records)
- Manifest: `evidence/APM-B1-READONLY-001/manifest.json`

Replay the stored engine inputs (no network) with:

```bash
PYTHONPATH=src python3 -m apm replay --evidence evidence/APM-B1-READONLY-001
```

Replay re-reads `computations.json`, runs the same Decimal engine, and checks exact equality. It also inserts the stored opportunity ids into SQLite a second time; the primary key `(run_id, opportunity_id)` keeps the row count unchanged.

A missing exchange timestamp is stored as `UNKNOWN`. Receive time is never written into the source-timestamp field.

## Done

- Readonly Polymarket international Gamma/CLOB and Kalshi REST adapters with a GET host allowlist
- Raw captures store URL, request time, receive time, body, and payload SHA-256; missing quote times stay UNKNOWN
- Pair queue can emit PRICE_GAP_ONLY or REJECTED and never writes APPROVED. This scan's 10 pairs are all REJECTED should-reject cases; likely-same count is 0
- Decimal engine walks ask levels for same-market and both cross directions
- Unit tests cover fee wipeout, second-level depth, Kalshi bid inversion, empty books, stale and missing times, unknown fees, inconsistent rules, single-leg fills, and replay idempotency

## Not done

- No pair is settlement-APPROVED; live payout is not fixed at 1
- Polymarket US is not queried
- PMXT is not attached
- No WebSocket, no 24h observation, no order path
- Kalshi public order books in this batch have no exchange timestamp, so those legs fail TIMESTAMP_UNKNOWN
- Cross-venue USD vs USDC is CURRENCY_UNKNOWN until a reviewed conversion exists
- Kalshi taker fee uses the July 2026 quadratic coefficient with a non-direct cent upper bound, not a direct-member exact fee

## Blockers

- None that stop the readonly screen from being reviewed.

## Next (for GPT, not a self-approval)

- GPT reviews this head and the raw manifest before any rule is marked settlement-equivalent
- Keep the 5-second age and 2-second skew gates; do not relax them to manufacture an executable row
- B2 can add a human rule review on docs/PAIR_REVIEW_QUEUE.md and a PMXT capability probe

