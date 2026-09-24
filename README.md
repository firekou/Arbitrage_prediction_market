# 預測市場套利研究

本專案研究不同預測市場的題目、結算規則與可成交報價，建立可重播的套利候選分析。

目前階段：規劃與資料唯讀 PoC。尚未驗證獲利，尚未啟用真實交易或 Grok 自動喚醒。

研究與 Grok 執行工作包見 `docs/RESEARCH_AND_GROK_PLAN_20260923.md`。

第一批目標：Polymarket 與 Kalshi 公開資料、規則配對、扣除成本的套利公式、模擬成交與證據報告。

## Readonly screen

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m apm scan \
  --config configs/research.yaml \
  --evidence evidence/APM-B1-READONLY-001 \
  --report reports/APM-B1-READONLY-001.md \
  --pairs docs/PAIR_REVIEW_QUEUE.md \
  --base-sha 6df184d7c331ff525fb3bb2b09df3628b16c0611
PYTHONPATH=src python3 -m apm replay --evidence evidence/APM-B1-READONLY-001
```

`discover` and `snapshot` are separate steps. `scan` runs the capped catalog, books, pair queue, and formula screen. The process only sends HTTPS GET requests to the official Polymarket international and Kalshi hosts. It does not place orders. A zero-opportunity scan is a valid result. Unconfirmed settlement stays `PRICE_GAP_ONLY` and is never `APPROVED`.
