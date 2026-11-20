---
name: spc
description: 占卜家：把假說卡（自檢過或審過）操作化成 SPC（Systematic Predictions Challenge）prompt——前置 ISIN 主清單、切子清單、組 prompt、送審判官、預測試、驗證、定稿、提交登記。用法 /spc universe | /spc <card_id> | /spc submitted <card_id> --name … --weight … | /spc status
argument-hint: universe [--websearch] | <card_id> [--revise] | submitted <card_id> --name <PromptName> --weight <你實際設的權重> | checked <card_id> --name … --status ok|failed_validation | status
---

# /spc

參數：`$ARGUMENTS`。從 open machine 根目錄執行。SPC 規則與判準在 `agents/common/knowledge/spc/`（權威順序 rules > spec > lessons > examples）。
**硬規則**：提交不可逆（不能改、不能刪、只能權重歸零），所以有審判官時驗證沒全過不定稿、不提交（沒裝審判官就不檢查，每次都要提醒使用者這件事）；提交由使用者在平台執行，你只到「prompt＋表單草稿＋驗證報告」。prompt 本文英文；卡、判決書、表單草稿中文。

## A. `/spc universe`：前置——ISIN|MIC 主清單（第一次或過期時）

1. `python agents/hypothesis_seer/cli/spc_prompt.py masters` 看有沒有有效主清單（90 天）。有就跳過。
2. 生成，兩條路都支援：
   - **使用者貼回**（預設）：印出 `knowledge/spc/spec/universe_procedure.md` 的前置 prompt，**每批 ≤50 檔**（例：市值 1–50、51–100…），請使用者在乾淨視窗跑、把結果（每行 `TICKER, COMPANY NAME, ISIN|MIC`）存成一個文字檔。
   - **`--websearch`**：你自己用 WebSearch 查，同樣每批 ≤50、同格式寫成文字檔；只能用查到的 ISIN，查不到就寫 `UNKNOWN` 不猜。
3. 入庫（先看 `ls .claude/agents/expression-inquisitor.md`）：
   - **有審判官** → 交給它驗證入庫：Agent 工具 `subagent_type: expression-inquisitor`，prompt 只能是：
     「請驗證 SPC 主清單 <檔案路徑>，執行 `python agents/expression_inquisitor/cli/spc_universe.py check <檔> --expect <N> --save-master --source <user_paste|websearch>`，通過後印 `reverse-prompt` 給使用者做全量反查。」
   - **沒有審判官** → 不檢查，直接存：`python agents/hypothesis_seer/cli/spc_prompt.py master <檔> --source <user_paste|websearch>`。說一句「沒有審判官，主清單沒有檢查格式、ISIN 檢查碼、交易所代碼和反查；提交前請自己抽查幾檔」。
4. 反查（有審判官才做）：把審判官印的反查 prompt 交給使用者（或 `--websearch` 時你自己查），結果存檔後再請審判官 `reverse-check`。不符的檔單獨重查。

## B. `/spc <card_id>`：組 prompt

0. 前置：`python agents/common/card.py show <card_id>`——status 是 `self_checked`／`unreviewed`／`approved`／`conditional`（條件已滿足）或更後；frontmatter `channel` 必須是 `spc` 或 `both`（不是 → 停，說明 4.4 的 SPC 適合度沒過）。有效主清單必須存在（沒有 → 先 A）。
1. 切子清單（**跟著假說的切面走**：sector／市值帶／事件窗／波動帶，~50 檔）：
   `python agents/hypothesis_seer/cli/spc_prompt.py universe <card_id> --rank 101-150 --facet "市值帶"`（或 `--pick` / `--file`）。只能從主清單切，不手寫 ISIN。
2. 寫原稿 `agents/workspace/spc/<card_id>/sections.json`（英文；照 `knowledge/spc/examples/good_prompt_example.md` 的結構）。原稿放 agents 工作區；`render` 的產出（`prompt.json`、`prompt.txt`）才進 `DB/ResearchDB/spc/<card_id>/`：
   ```json
   {"role": "...", "web_search": "...", "workflow": "Step 1 – ... Step N – ...", "direction_rule": "...",
    "bull_bear_gate": "...", "scoring": "...", "mechanical_direction": true, "target_count": 50}
   ```
   - workflow：四關逐關轉成「每步看什麼證據、量化判準」；第 1 關 → 查什麼、第 2 關 → 排除已被定價的、第 3 關 → 排除噪音來源、第 4 關 → 方向規則與降級條件。
   - direction_rule：**方向由單一權威、格式固定的資料機械決定，模型只定幅度**（失敗樣式 #4、#5）。
   - bull_bear_gate：兩面論證 ＋ **明確的降級條件**，不是開放辯論；內部推理不印出。
   - scoring：全名單給分、無訊號給固定小分（如 ±0.005）、值域 ±0.010～0.100、3 位小數、差異化。
   - web_search：指定權威來源、禁用記憶中的數字、查不到視為「無合格活動」。
3. 組裝：`python agents/hypothesis_seer/cli/spc_prompt.py render <card_id> --audit on --name <機制>-<universe><檔數>-v1 --frequency <依半衰期> --weight <建議權重> [--model ...]`
   - `--weight` 是**建議值**，寫進表單草稿給使用者參考；實際權重由使用者在平台上決定。
   - 建議規則 [R]：首次提交一律在 0.05～0.10（`spec/FORMAT_SPEC.md`）。沒裝審判官看信心分數：≤5 → 0.05、6～7 → 0.07、≥8 → 0.10；有裝審判官看判決：有條件通過 → 0.05、通過 → 0.08。回報時一句說明為什麼是這個數。
   看字元預算（≤10,000，留 ≥3,000 緩衝）；超限：先砍工作流冗詞 → 再縮 universe → 絕不砍尾註與 web search。
4. 自審：逐條對照 `knowledge/spc/examples/bad_prompt_example.md` 的錯誤表 [A]～[H]。
5. 送審判官（stage=spc）：Agent 工具 `subagent_type: expression-inquisitor`，prompt 只能是：
   「請審 <card_id>，stage=spc。先執行 `python agents/expression_inquisitor/cli/blind_pack.py <card_id> --stage spc` 取得盲包，依你的規則判決並寫判決書。」
   判決轉成占卜家的說法：通過／重新占卜／拒絕。重新占卜 → 依條目改 sections.json 再 render（版本 +1 用 `--bump`），問使用者要不要再送；拒絕 → 用白話轉達條目，停。沒裝審判官 → 跳過送審，直接進預測試，並說一句「prompt 沒有經過審判官，只做了格式檢查」。
6. 預測試（審判官通過後，或沒裝審判官）：Agent 工具 `subagent_type: general-purpose`（需有 WebSearch），prompt：「把下面這段 prompt 當成任務完整執行一次，照它的要求輸出；不要解釋。」＋ `spc_prompt.py show <card_id>` 的全文。只檢查**格式與覆蓋**（能 parse、key 都在清單、覆蓋 ±20%、有 ---AUDIT--- 段）；把輸出存 `DB/ResearchDB/spc/<card_id>/runs/pretest.json`，記帳 `spc_pretest`。不過 → 回第 2 步修。
7. 回報（平實）：「prompt v<n> 已放到 `DB/ResearchDB/spc/<card_id>/prompt.txt`（<字元數> 字元、<N> 檔）。請你在乾淨的 chat 視窗連續跑 3 次（同一時段），每次的**原始輸出原文**各存成 `DB/ResearchDB/spc/<card_id>/runs/run_1.json`、`run_2.json`、`run_3.json`，然後 `/judge <card_id> --stage spc`。」（沒裝審判官：最後一句改成「存好後跟我說，我們直接定稿」。）

## C. 驗證後定稿（審判官 stage=spc 對 runs 通過之後；沒裝審判官就不檢查 runs，由使用者看 3 次輸出自行決定，並提醒「沒有審判官，3 次實測沒有經過驗證」）

`python agents/hypothesis_seer/cli/spc_prompt.py finalize <card_id>` → audit 關掉、Sample Output 取 run_3 原文、產 `form_final.md`。回報表單欄位與貼法；提醒提交不可逆、表單上的權重只是建議（首次 0.05～0.10），實際設多少由他決定、提交後要告訴你、Update Frequency 要對應訊號半衰期（事件型 Daily/Weekly、重估型 Weekly/Monthly、結構型 Monthly/Quarterly）。

## D. `/spc submitted <card_id> --name … --weight …`／`checked`／`status`

- 使用者提交後告訴你 → `python agents/hypothesis_seer/cli/spc_registry.py submitted <card_id> --name <PromptName> --weight <w> [--model ..] [--frequency ..]`。`<w>` **一定用使用者說的實際權重**，不要拿表單上的建議值代填；他沒說就問「你在平台上權重設多少？」，等他回再登記。提交後這張卡只記**狀態與權重**（Submitted, Weight: n），不記 PnL；羅盤的專案管理頁會把它放到「結案」。
- 使用者回報平台狀態 → `spc_registry.py checked <card_id> --name .. --status ok|failed_validation`；持續 failed → 建議 `weight … --weight 0`（唯一下架方式）。**權重歸零時狀態自動變 Fail**。
- `/spc status` → `spc_registry.py list`（每份 prompt：Submitted, Weight: n ／ Fail）＋ `coverage`（全組合不重複標的 ≥500、同檔出現在幾份 prompt）。
- 鐵律：不依單日 PnL 建議調權重；權重分配依 Edge × Repeatability × Diversification（`knowledge/spc/rules/official_tips.md`）。

## 給新手的說明（每次回報附）

為什麼方向要機械、為什麼全名單給分、為什麼 universe 要 `TICKER = ISIN|MIC`、為什麼先低權重觀察——各一行，引用 `knowledge/spc/` 的檔名與樣式編號。
