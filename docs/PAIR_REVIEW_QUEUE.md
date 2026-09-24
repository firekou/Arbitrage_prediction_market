# Pair review queue

Work ID: APM-B1-READONLY-001

No pair in this file is APPROVED. `PRICE_GAP_ONLY` means the titles are similar enough to review and settlement equivalence is unconfirmed. `REJECTED` means a compared dimension already conflicts (threshold, date, operator, timezone, settlement source, or cancel/refund language). Text similarity is not a payout proof.

Queue size: 10

Likely-same but unconfirmed: 0. Should-reject: 10.

Zero likely-same pairs is the result of this capped sample. Bitcoin, Ether, and Fed titles overlapped, and each overlap already disagreed on a threshold, date, operator, timezone, or settlement source. No synthetic pair was added to reach 10.

## 1. `pair_0c048b8452bf` — REJECTED

- Left: polymarket_international `4641123` — Will the price of Bitcoin be above $82,000 on September 24?
- Right: kalshi `KXBTCD-26SEP2408-T94799.99` — Bitcoin price on Sep 24, 2026? [$94,800 or above]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 1.000000
- Rules SHA-256 left: `43c4bf4589be731ca6419e8b54d9f0a0874e7572a4497e617adf4ae12d6e1025`
- Rules SHA-256 right: `0b2ebbf58f198bef33d8478d832fec522a9cff3ab1e4e7a7dc10a2df3ba7dc5b`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "1.000000",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "000",
      "24",
      "82"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "800",
      "94",
      "94799.99"
    ],
    "operators": [
      ">="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance BTC/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index (BRTI) before 8 AM EDT is above 94799.99 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

## 2. `pair_a8b63e46b2eb` — REJECTED

- Left: polymarket_international `2589812` — Will there be no change in Fed interest rates after the October 2026 meeting?
- Right: kalshi `KXFED-27APR-T6.00` — Will the upper bound of the federal funds rate be above 6.00% following the Fed's Apr 28, 2027 meeting? [Above 6.00%]
- Direction mapping: UNCONFIRMED
- Differences: date
- Subject Jaccard: 0.375000
- Rules SHA-256 left: `aef6b5c5a5f96b0671c51926d2cbccdc9bb10ff82330b7b8b95d41d50ea8bf8e`
- Rules SHA-256 right: `dc3831f1bfb416759956505904aaab2ecc84b3300abf7b2eb40b10032052fad4`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "date"
  ],
  "jaccard": "0.375000",
  "left": {
    "cancel_refund": [],
    "dates": [
      "2026-10"
    ],
    "numbers": [],
    "operators": [],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "change",
      "fed",
      "interest",
      "meeting",
      "rate",
      "there"
    ],
    "timezones": []
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2027-04-28"
    ],
    "numbers": [
      "6"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bound",
      "fed",
      "meeting",
      "rate",
      "upper"
    ],
    "timezones": [
      "ET"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

The FED interest rates are defined in this market by the upper bound of the target federal funds range. The decisions on the target federal funds range are made by the Federal Open Market Committee (FOMC) meetings.

This market will resolve to the amount of basis points the upper bound of the target federal funds rate is changed by versus the level it was prior to the Federal Reserve's October 2026 meeting.

If the target federal funds rate is changed to a level not expressed in the displayed options, the change will be rounded up to the nearest 25 and will resolve to the relevant bracket. (e.g. if there's a cut/increase of 12.5 bps it will be considered to be 25 bps)

The resolution source for this market is the FOMC’s statement after its meeting scheduled for October 27-28, 2026 according to the official calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm.

The level and change of the target federal funds rate is also published at the official website of the Federal Reserve at https://www.federalreserve.gov/monetarypolicy/openmarket.htm.

This market may resolve as soon as the FOMC’s statement for their October meeting with relevant data is issued. If no statement is released by the end date of the next scheduled meeting, this market will resolve to the "No change" bracket.

### Rules text (right)

If the upper bound of the target federal funds rate published on the Federal Reserve's official website is greater than 6.00% following the Federal Reserve's Apr 28, 2027 meeting, then the market resolves to Yes.
This market will expire the first 2:05 PM ET following the release of a Federal Reserve statement for their Apr 28, 2027 meeting or one week following the last day of that meeting.

## 3. `pair_f7c63e0b0ee9` — REJECTED

- Left: polymarket_international `4641083` — Will the price of Ethereum be above $2,000 on September 24?
- Right: kalshi `KXETH-26SEP2408-T3444.99` — Ethereum price at Sep 24, 2026 at 8am EDT? [$3,445 or above]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 0.333333
- Rules SHA-256 left: `4afe33254cdf2f5149496004268de3a939a639db70ef8462346cfb2b6ec3a3a4`
- Rules SHA-256 right: `96971aad41627333404efd392718c7c9c012a75c25ea318d43c0fe835f2e757c`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "0.333333",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "000",
      "2",
      "24"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "ethereum"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "3",
      "445",
      "8",
      "99"
    ],
    "operators": [
      ">="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "8am",
      "edt",
      "ethereum"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for ETH/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the ETH/USDT "Close" prices currently available at https://www.binance.com/en/trade/ETH_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance ETH/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Ethereum Real-Time Index (ERTI) before 8 AM EDT is above 3444.99 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

## 4. `pair_dadfcf547880` — REJECTED

- Left: polymarket_international `4641128` — Will the price of Bitcoin be above $86,000 on September 24?
- Right: kalshi `KXBTCD-26SEP2408-T94699.99` — Bitcoin price on Sep 24, 2026? [$94,700 or above]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 1.000000
- Rules SHA-256 left: `43c4bf4589be731ca6419e8b54d9f0a0874e7572a4497e617adf4ae12d6e1025`
- Rules SHA-256 right: `cbf85b79600c9e7f18c1d0b5bfff3514aa4887b41aa84fd2c7f76dd970c1b0fa`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "1.000000",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "000",
      "24",
      "86"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "700",
      "94",
      "94699.99"
    ],
    "operators": [
      ">="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance BTC/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index (BRTI) before 8 AM EDT is above 94699.99 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

## 5. `pair_02bdecbfe79c` — REJECTED

- Left: polymarket_international `4641122` — Will the price of Bitcoin be above $80,000 on September 24?
- Right: kalshi `KXBTCD-26SEP2408-T94599.99` — Bitcoin price on Sep 24, 2026? [$94,600 or above]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 1.000000
- Rules SHA-256 left: `43c4bf4589be731ca6419e8b54d9f0a0874e7572a4497e617adf4ae12d6e1025`
- Rules SHA-256 right: `05f054737987ff1ac9ece90ea7fc14e8d4966f8fde11bdf73c0f1dca875f85bf`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "1.000000",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "000",
      "24",
      "80"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "600",
      "94",
      "94599.99"
    ],
    "operators": [
      ">="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance BTC/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index (BRTI) before 8 AM EDT is above 94599.99 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

## 6. `pair_bcf7f1ff091b` — REJECTED

- Left: polymarket_international `4641107` — Will the price of Bitcoin be above $66,000 on September 24?
- Right: kalshi `KXBTCD-26SEP2408-T94499.99` — Bitcoin price on Sep 24, 2026? [$94,500 or above]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 1.000000
- Rules SHA-256 left: `43c4bf4589be731ca6419e8b54d9f0a0874e7572a4497e617adf4ae12d6e1025`
- Rules SHA-256 right: `a7e1a1f48d5a06d4c0e9b89fe0ef8873cb4a96da636c658dd5b2151e6c5af60c`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "1.000000",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "000",
      "24",
      "66"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "500",
      "94",
      "94499.99"
    ],
    "operators": [
      ">="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "bitcoin"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance BTC/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index (BRTI) before 8 AM EDT is above 94499.99 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

## 7. `pair_95952792d6de` — REJECTED

- Left: polymarket_international `2589813` — Will the Fed increase interest rates by 25 bps after the October 2026 meeting?
- Right: kalshi `KXFED-27APR-T5.75` — Will the upper bound of the federal funds rate be above 5.75% following the Fed's Apr 28, 2027 meeting? [Above 5.75%]
- Direction mapping: UNCONFIRMED
- Differences: threshold, date
- Subject Jaccard: 0.375000
- Rules SHA-256 left: `aef6b5c5a5f96b0671c51926d2cbccdc9bb10ff82330b7b8b95d41d50ea8bf8e`
- Rules SHA-256 right: `5b37d5652ce6b32d5203042bf80fb4e5eb6f516845b631493e1fd8185205764f`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "date"
  ],
  "jaccard": "0.375000",
  "left": {
    "cancel_refund": [],
    "dates": [
      "2026-10"
    ],
    "numbers": [
      "25"
    ],
    "operators": [],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bps",
      "fed",
      "increase",
      "interest",
      "meeting",
      "rate"
    ],
    "timezones": []
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2027-04-28"
    ],
    "numbers": [
      "5.75"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bound",
      "fed",
      "meeting",
      "rate",
      "upper"
    ],
    "timezones": [
      "ET"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

The FED interest rates are defined in this market by the upper bound of the target federal funds range. The decisions on the target federal funds range are made by the Federal Open Market Committee (FOMC) meetings.

This market will resolve to the amount of basis points the upper bound of the target federal funds rate is changed by versus the level it was prior to the Federal Reserve's October 2026 meeting.

If the target federal funds rate is changed to a level not expressed in the displayed options, the change will be rounded up to the nearest 25 and will resolve to the relevant bracket. (e.g. if there's a cut/increase of 12.5 bps it will be considered to be 25 bps)

The resolution source for this market is the FOMC’s statement after its meeting scheduled for October 27-28, 2026 according to the official calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm.

The level and change of the target federal funds rate is also published at the official website of the Federal Reserve at https://www.federalreserve.gov/monetarypolicy/openmarket.htm.

This market may resolve as soon as the FOMC’s statement for their October meeting with relevant data is issued. If no statement is released by the end date of the next scheduled meeting, this market will resolve to the "No change" bracket.

### Rules text (right)

If the upper bound of the target federal funds rate published on the Federal Reserve's official website is greater than 5.75% following the Federal Reserve's Apr 28, 2027 meeting, then the market resolves to Yes.
This market will expire the first 2:05 PM ET following the release of a Federal Reserve statement for their Apr 28, 2027 meeting or one week following the last day of that meeting.

## 8. `pair_b884e220a1d5` — REJECTED

- Left: polymarket_international `2589814` — Will the Fed increase interest rates by 50+ bps after the October 2026 meeting?
- Right: kalshi `KXFED-27APR-T5.50` — Will the upper bound of the federal funds rate be above 5.50% following the Fed's Apr 28, 2027 meeting? [Above 5.50%]
- Direction mapping: UNCONFIRMED
- Differences: threshold, date
- Subject Jaccard: 0.375000
- Rules SHA-256 left: `aef6b5c5a5f96b0671c51926d2cbccdc9bb10ff82330b7b8b95d41d50ea8bf8e`
- Rules SHA-256 right: `1b612b37d28cfd1a6227e583952fdb91fedabedca9b03a565e491162280d8843`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "date"
  ],
  "jaccard": "0.375000",
  "left": {
    "cancel_refund": [],
    "dates": [
      "2026-10"
    ],
    "numbers": [
      "50"
    ],
    "operators": [],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bps",
      "fed",
      "increase",
      "interest",
      "meeting",
      "rate"
    ],
    "timezones": []
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2027-04-28"
    ],
    "numbers": [
      "5.5"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bound",
      "fed",
      "meeting",
      "rate",
      "upper"
    ],
    "timezones": [
      "ET"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

The FED interest rates are defined in this market by the upper bound of the target federal funds range. The decisions on the target federal funds range are made by the Federal Open Market Committee (FOMC) meetings.

This market will resolve to the amount of basis points the upper bound of the target federal funds rate is changed by versus the level it was prior to the Federal Reserve's October 2026 meeting.

If the target federal funds rate is changed to a level not expressed in the displayed options, the change will be rounded up to the nearest 25 and will resolve to the relevant bracket. (e.g. if there's a cut/increase of 12.5 bps it will be considered to be 25 bps)

The resolution source for this market is the FOMC’s statement after its meeting scheduled for October 27-28, 2026 according to the official calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm.

The level and change of the target federal funds rate is also published at the official website of the Federal Reserve at https://www.federalreserve.gov/monetarypolicy/openmarket.htm.

This market may resolve as soon as the FOMC’s statement for their October meeting with relevant data is issued. If no statement is released by the end date of the next scheduled meeting, this market will resolve to the "No change" bracket.

### Rules text (right)

If the upper bound of the target federal funds rate published on the Federal Reserve's official website is greater than 5.50% following the Federal Reserve's Apr 28, 2027 meeting, then the market resolves to Yes.
This market will expire the first 2:05 PM ET following the release of a Federal Reserve statement for their Apr 28, 2027 meeting or one week following the last day of that meeting.

## 9. `pair_5b7c81bf0747` — REJECTED

- Left: polymarket_international `2589810` — Will the Fed decrease interest rates by 50+ bps after the October 2026 meeting?
- Right: kalshi `KXFED-27APR-T5.25` — Will the upper bound of the federal funds rate be above 5.25% following the Fed's Apr 28, 2027 meeting? [Above 5.25%]
- Direction mapping: UNCONFIRMED
- Differences: threshold, date
- Subject Jaccard: 0.375000
- Rules SHA-256 left: `aef6b5c5a5f96b0671c51926d2cbccdc9bb10ff82330b7b8b95d41d50ea8bf8e`
- Rules SHA-256 right: `df9d3f7336cbf352f187ab9570e9d1109705f309c4dc4054685fec7ec5bbf6dd`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "date"
  ],
  "jaccard": "0.375000",
  "left": {
    "cancel_refund": [],
    "dates": [
      "2026-10"
    ],
    "numbers": [
      "50"
    ],
    "operators": [],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bps",
      "decrease",
      "fed",
      "interest",
      "meeting",
      "rate"
    ],
    "timezones": []
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2027-04-28"
    ],
    "numbers": [
      "5.25"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "federal_reserve"
    ],
    "subject_tokens": [
      "bound",
      "fed",
      "meeting",
      "rate",
      "upper"
    ],
    "timezones": [
      "ET"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

The FED interest rates are defined in this market by the upper bound of the target federal funds range. The decisions on the target federal funds range are made by the Federal Open Market Committee (FOMC) meetings.

This market will resolve to the amount of basis points the upper bound of the target federal funds rate is changed by versus the level it was prior to the Federal Reserve's October 2026 meeting.

If the target federal funds rate is changed to a level not expressed in the displayed options, the change will be rounded up to the nearest 25 and will resolve to the relevant bracket. (e.g. if there's a cut/increase of 12.5 bps it will be considered to be 25 bps)

The resolution source for this market is the FOMC’s statement after its meeting scheduled for October 27-28, 2026 according to the official calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm.

The level and change of the target federal funds rate is also published at the official website of the Federal Reserve at https://www.federalreserve.gov/monetarypolicy/openmarket.htm.

This market may resolve as soon as the FOMC’s statement for their October meeting with relevant data is issued. If no statement is released by the end date of the next scheduled meeting, this market will resolve to the "No change" bracket.

### Rules text (right)

If the upper bound of the target federal funds rate published on the Federal Reserve's official website is greater than 5.25% following the Federal Reserve's Apr 28, 2027 meeting, then the market resolves to Yes.
This market will expire the first 2:05 PM ET following the release of a Federal Reserve statement for their Apr 28, 2027 meeting or one week following the last day of that meeting.

## 10. `pair_d97fa9600fc9` — REJECTED

- Left: polymarket_international `4641085` — Will the price of Ethereum be above $2,100 on September 24?
- Right: kalshi `KXETH-26SEP2408-T1955` — Ethereum price at Sep 24, 2026 at 8am EDT? [$1,954.99 or below]
- Direction mapping: UNCONFIRMED
- Differences: threshold, operator, timezone, settlement_source
- Subject Jaccard: 0.333333
- Rules SHA-256 left: `4afe33254cdf2f5149496004268de3a939a639db70ef8462346cfb2b6ec3a3a4`
- Rules SHA-256 right: `0ea920741f130667490a93ec9756603e34b16c7216bc228a0a147c782f5df620`
- Approval version: none. Reviewer: none.

### Parsed comparison

```json
{
  "differences": [
    "threshold",
    "operator",
    "timezone",
    "settlement_source"
  ],
  "jaccard": "0.333333",
  "left": {
    "cancel_refund": [],
    "dates": [],
    "numbers": [
      "100",
      "2",
      "24"
    ],
    "operators": [
      ">"
    ],
    "sources": [
      "binance"
    ],
    "subject_tokens": [
      "ethereum"
    ],
    "timezones": [
      "ET"
    ]
  },
  "right": {
    "cancel_refund": [],
    "dates": [
      "2026-09-24"
    ],
    "numbers": [
      "1",
      "8",
      "954.99"
    ],
    "operators": [
      "<="
    ],
    "sources": [
      "cf_benchmarks",
      "coinbase"
    ],
    "subject_tokens": [
      "8am",
      "edt",
      "ethereum"
    ],
    "timezones": [
      "EDT"
    ]
  },
  "rules_relation": "inconsistent"
}
```

### Rules text (left)

This market will resolve to "Yes" if the Binance 1 minute candle for ETH/USDT 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".

The resolution source for this market is Binance, specifically the ETH/USDT "Close" prices currently available at https://www.binance.com/en/trade/ETH_USDT with "1m" and "Candles" selected on the top bar.

Please note that this market is about the price according to Binance ETH/USDT, not according to other exchanges or trading pairs.

Price precision is determined by the number of decimal places in the source.

### Rules text (right)

If the simple average of the sixty seconds of CF Benchmarks' Ethereum Real-Time Index (ERTI) before 8 AM EDT is below 1955 at 8 AM EDT on Sep 24, 2026, then the market resolves to Yes.
Not all cryptocurrency price data is the same. While checking a source like Google or Coinbase may help guide your decision, the price used to determine this market is based on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices.

