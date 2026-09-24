# 預測市場套利研究

本專案研究不同預測市場的題目、結算規則與可成交報價，建立可重播的套利候選分析。

目前階段：資料唯讀 PoC。PR #1 已提交實作與掃描證據，仍待獨立覆核；尚未驗證獲利，尚未啟用真實交易或 Grok 自動喚醒。

## 執行入口

1. [成果與信心驗證要求、下一輪 Grok 指令](docs/CONFIDENCE_VALIDATION_AND_EXECUTION_20260924.md)：首個使用者、一種策略的連續觀察、DeFi 運作驗收與經濟成果證據。
2. [開源研究、套利公式與第一批工作包](docs/RESEARCH_AND_GROK_PLAN_20260923.md)。
3. [PR #1：唯讀實作與掃描證據](https://github.com/firekou/Arbitrage_prediction_market/pull/1)。

第一批目標：Polymarket 與 Kalshi 公開資料、規則配對、扣除成本的套利公式、模擬成交與證據報告。

完成標準以實際運作、可重播資料與可核對結果為準；運作成功、模擬收益和已實現獲利分開驗收。
