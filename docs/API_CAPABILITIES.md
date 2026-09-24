# API capabilities (B1)

Checked against public docs and unauthenticated responses on 2026-09-24. This is a capability note for the readonly screen, not a trading certification.

## Decision on Polymarket py-sdk

The research pin `Polymarket/py-sdk@1f5ca055d31a29a4fa0ad7955ee4a8bf8aaab3e6` contains `PublicClient`. That client returns typed models. It does not hand back the raw HTTP body, the local request start time, or the receive time. The same package also exposes secure/trading workflows. B1 has to store the raw response and must not grow an order path, so the Polymarket adapter is a narrow GET client for two hosts:

- `https://gamma-api.polymarket.com` (catalog, search)
- `https://clob.polymarket.com` (order book)

No other Polymarket host is called. `polymarket_us` is a separate venue id and is rejected if passed into the normalizer. The py-sdk was not installed and was not copied.

## Polymarket international

| Need | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| Active markets | `GET /markets?closed=false&active=true` | No | Full `description`, outcomes, `clobTokenIds`, `feeSchedule` observed |
| Topic sample | `GET /public-search?q=` | No | Events include nested markets. Used only to diversify a capped sample |
| Order book | `GET /book?token_id=` | No | `bids` and `asks` are price/size strings. `timestamp` is unix milliseconds when present. `last_trade_price` is stored in the raw body and is not an executable ask |

`feeSchedule.rate` with `exponent == 1` uses the documented taker formula `C × rate × p × (1−p)`, half-up to 0.00001 USDC. Rebates are not booked as income. A missing rate or an exponent other than 1 is `FEE_UNKNOWN`. Currency is recorded as USDC.

The catalog is capped at 100 active markets. That is a sample, not the whole venue.

## Kalshi

Base URL: `https://external-api.kalshi.com/trade-api/v2`. No API key.

| Need | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| Open binary markets | `GET /markets?status=open&mve_filter=exclude` | No | Multivariate combos are excluded. At most 8 markets per event, 100 markets total |
| Series fee | `GET /series/{series_ticker}` | No | `fee_type`, `fee_multiplier` |
| Event fee changes | `GET /events/fee_changes?event_ticker=&show_historical=true` | No | A change applies only when `scheduled_ts` is at or before the book receive time |
| Order book | `GET /markets/{ticker}/orderbook` | No | `orderbook_fp.yes_dollars` and `no_dollars` are bid ladders. Asks are implied: YES ask = 1 − NO bid, size copied. An empty side is missing, not a zero price |

Rules text is `rules_primary`, `rules_secondary`, and `early_close_condition` when present. `result` of `""` stays unset. It is not filled in.

Quadratic taker fees use coefficient `0.07` from the Kalshi fee schedule PDF updated 2026-07-07 (`M × 0.07 × C × P × (1−P)`), then the non-direct member cent upper bound from the fee-rounding docs. That is an upper bound. Direct members can pay less. `flat` and other fee types are `FEE_UNKNOWN`. The public order book observed in this batch has no exchange timestamp, so quote time is `UNKNOWN` and those legs cannot be executable.

## Not in this batch

- Polymarket US
- PMXT hosted or sidecar (`PmxtAdapter` raises `NotImplementedError`)
- Authenticated websockets
- Orders, cancels, wallets, approvals, transfers, or position merges
- Any path that would treat USD and USDC as the same unit

## Failure behavior

Timeout is 10 seconds. Temporary errors and HTTP 429 are retried at most twice. `Retry-After` is honored when it is a number of seconds. Three consecutive failures stop that adapter. A bad payload shape is `SCHEMA_CHANGED`. A later catalog page failure after a good page is `PAGINATION_INTERRUPTED`, and earlier rows are kept without being reported as a complete catalog.
