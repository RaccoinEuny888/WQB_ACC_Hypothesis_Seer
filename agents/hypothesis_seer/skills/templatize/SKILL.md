---
name: templatize
description: 占卜家：expression 的模擬結果過了審判官或自檢（self_check.py：main Sharpe>1、turnover<0.5、K1、K2）後，依四個模組把主構造泛化成 GA template（同 subgroup 才互換、每個基因位寫理由），有審判官就送審，寫入 DB/ResearchDB/template/ 並印出 GA 指令。用法 /templatize <card_id>
argument-hint: <card_id>
---

# /templatize

卡號：`$ARGUMENTS`。從 open machine 根目錄執行。

## 0. 前置

- `python agents/common/card.py show <card_id>`：status 要是 `expr_approved`（審判官審過）**或** `expr_self_checked`。兩者都不是 →
  - 有裝審判官（`ls .claude/agents/expression-inquisitor.md`）→ 不自檢，問使用者要不要先 `/judge <card_id>` 審式子與結果；通過才往下。
  - 沒裝 → 跑 `python agents/hypothesis_seer/cli/self_check.py <card_id>`：它讀本機模擬結果，規則是 main Sharpe > 1 且 turnover < 0.5、K1（main 贏 naive）、K2（反向組比 main 弱）[R]；PASS 會自動設 `expr_self_checked`，就往下；FAIL 就把它印的表轉達，停。
- 讀卡片第 4 關與 `DB/ResearchDB/idea/<card_id>.json` 的 main。

## 1. 產生 template 骨架

```
python agents/common/templatize.py --from-idea <card_id> --role main -o <card_id>_<slug>
```
輸出 `DB/ResearchDB/template/<card_id>_<slug>.json` 與 `<card_id>_<slug>.notes.json`（骨架）。

## 2. 剪枝與填理由（`agents/common/knowledge/template_doctrine.md`）

- 打開 `.notes.json`，每個基因位填一行 `why`（為什麼這個槽位要開、為什麼是這些選項）。填不出來的選項從 template 的 `gene_pool` 刪掉，刪掉的寫進 `pruned`。
- 每個槽位再問一次：選項之間是「同一個想法的不同算法」還是「不同的想法」？後者刪掉（例：剝離用 neut，就不要留 proj；template_doctrine #7）。
- 看 `templatize.py` 印出的 operator 數；用了替代配方（`operator_recipes.md`）會變多，超過你的上限就回頭精簡。
- 檢查：同 subgroup 才互換（骨架已保證）；universe／region／delay／neutralization 不在 gene_pool；欄位基因位只放同 dataset、同語意的欄位（Template Capacity）；組合數印出，大於 10,000 要在 notes 寫剪枝理由。
- 填 `doctrine_check` 三個布林。
- `python agents/common/syntax_check.py -t <card_id>_<slug> -s <card_id>` 必須 PASS。

## 3. 送審判官

Agent 工具，`subagent_type: expression-inquisitor`，prompt 只能是：
「請審 <card_id>，stage=template。先執行 `python agents/expression_inquisitor/cli/blind_pack.py <card_id> --stage template` 取得盲包，依你的規則判決並寫判決書。」

- 有裝審判官（`ls .claude/agents/expression-inquisitor.md`）才送；沒裝就跳過送審，直接記帳 `template_built`（payload：n_slots、n_combinations、pruned、reviewed=false），狀態維持 `expr_self_checked`，並說一句「沒有審判官，template 只過了機械檢查（同 subgroup、語法、組合數）」。
- 判決轉成占卜家的說法：通過／重新占卜／拒絕。
- 通過 → `card.py set-status <card_id> template_approved --actor seer --reason "stage=template 通過"`，記帳 `template_built`。
- 重新占卜 → 依條目改 template／notes，問使用者要不要再送一次。
- 拒絕 → 停，用白話轉達條目。

## 4. 回報（平實）

「template 已放到 `DB/ResearchDB/template/<card_id>_<slug>.json`（基因位 n 個、組合數 m）。要跑 GA 請你執行：
```
python sample_code/sample_ga.py --research_name <card_id>_<slug> --template_file <card_id>_<slug>.json --setting_file <card_id>.json --ga_config_file default_ga_config.json
```
研究名稱請保留 `<card_id>_` 前綴，羅盤才能把研究線連回這張卡。」
再附兩句 GA 設定提醒（`agents/common/knowledge/ga_tips.md`）：`ga_config` 的 `bcorr_threshold` 是每代的 correlation reduction，越低越保多樣性；若某個基因位的選項從第 2 代起就消失，可把它固定住另開一條 `<card_id>_<slug2>` 研究線。
記帳 `ga_command_issued`（payload.command）。

附「給新手的說明」：每個基因位一行為什麼、哪些被剪掉、為什麼 hyperparameter 不進 gene_pool（引用 template_doctrine 條目）。
