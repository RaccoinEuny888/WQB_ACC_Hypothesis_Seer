---
name: papers
description: 占卜家：只做文獻檢索（上限 5 篇），列支持與反面證據，不建卡。用法 /papers <主題>
argument-hint: <主題或關鍵字>
---

# /papers

主題：`$ARGUMENTS`

1. 有 WebSearch：去 WQ 化的查詢（學術關鍵字＋anomaly／mispricing／limits to arbitrage／institutional），最多 5 篇。沒有 WebSearch：說明「本環境沒有檢索工具，只能用你提供的來源」，然後停。
2. 每篇一列：來源、年份、主張、支持／反面、可對應的四關（1 現象與機制／2 對手／3 持續／4 證偽）。
3. 支持必列；反面盡量找，找不到寫「未找到反面證據 `[?]`」。
4. 只列檢索結果裡真的出現的文獻；你「記得」但沒搜到的一律標 `[?]` 並分開列。
5. 結尾一句：「要不要我依這些文獻整理成命題、再寫假說卡？（`/hypothesis <主題>`）」
6. 記帳：`python agents/common/ledger.py append --actor seer --event literature_collected --payload '{"topic":"...","n_support":N,"n_contra":M,"search_used":true}'`
