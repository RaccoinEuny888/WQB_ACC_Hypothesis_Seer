---
name: express
description: 占卜家：為一張假說卡（自檢過或審過都可以）依四個模組寫 expression（main／naive／反向證偽三條，每層一句白話），通過語法檢查後寫 setting 與 idea 檔，印出使用者要執行的模擬指令。用法 /express <card_id> [--revise]
argument-hint: <card_id> [--revise]
---

# /express

參數：`$ARGUMENTS`（卡號；`--revise` 表示依判決修訂既有 idea）。從 open machine 根目錄執行。

## 0. 前置

- `python agents/common/card.py show <card_id>`：status 是 `self_checked`／`approved`／`conditional`／`needs_work`／`unreviewed`／`expr_ready`／`simulating`／`expr_self_checked`／`expr_approved`（修訂時）都可以。`rejected`（機制被證偽）→ 停，說明原因。`needs_work` → 先把審判官的條目唸一遍，問他要先改卡還是先寫式子。信心 ≤4 的卡 → 提醒一句「這張卡自檢分數低，式子跑出來也要小心解讀」，然後照做。
- 讀卡片 `DB/ResearchDB/hypothesis/<card_id>.md` 的第 4 關（對照組、候選欄位、生死線）與「操作化方向」。
- 修訂模式：先讀最新判決書 `DB/ResearchDB/hypothesis/reviews/<card_id>_expr_v*.md`，只改被點名的地方。

## 1. 欄位

`python agents/hypothesis_seer/cli/pick_fields.py --region <R> --universe <U> --delay <D> --check <卡上 4.4 的欄位>`
- 全部 `[OK]` 才往下；`[缺]` → 用 `--query` 找替代並回卡片更新 4.4（`card.py bump-version`）。
- VECTOR 型別一定要先過 `vec_avg`／`vec_sum`／`vec_max`，並說明為什麼選那個聚合。

## 2. 三條 expression（四個可管理模組）

每條都照這個順序寫，一行一個模組，expression 本身不放註解（平台不吃），每層的白話寫在 design_notes 與回報：

```
Raw Data → 1 資料清洗 Data Cleaning → 2 訊號提取 Signal Extraction → 3 時序平滑 Signal Smoothing → 4 組內處理 Group Operation → Final Alpha
data   = <清洗>(<欄位>)          # 原始值哪裡髒：backfill／winsorize／vec_*／除以規模
signal = <訊號>(data, <d>)       # 機制對應的量：變化／差距／比值／新鮮度
smooth = <平滑>(signal, <d2>)    # 持有多久：decay／mean
<組內>(smooth, <group>)         # 跟誰比：rank／zscore／neutralize
```
某一層假說裡用不到就省略，但要在 notes 說為什麼省。operator 要從同一個功能小群挑（`agents/common/knowledge/operator_subgroups.json`）。

**為什麼要三條（給新手的說明一定要講）**：main 是你的假說；naive 是「最直覺的做法」，用來證明你多剝掉的那一步有用（卡上 K1）；反向證偽組跟 main 只差一個變數、套在機制不該成立的資料上，用來抓歸因錯誤（卡上 K2）。少了後兩條，跑出好成績也不知道是不是你以為的那個原因。

- `main`：主構造，對應第 4 關 4.3「多剝掉的那一步」。
- `naive`：卡上定義的 naive 版本。
- `falsify`：反向證偽組，**與 main 只差一個變數**（資料源、子集或 group），寫清楚差在哪。
- 先逐條自查 `agents/common/knowledge/expression_doctrine.md`（trade_when、四則拼接、多視窗堆疊、魔術數字、順序、VECTOR、divide、lookback 必須常數、最後一行賦值）。
- 語法檢查說 operator 不存在 → 先查 `agents/common/knowledge/operator_recipes.md`（vector_neut、regression_neut、group_sum、ts_min/max、hump 的替代配方），用了配方要在 design_notes 與卡上註明。
- lookback 與持有期用卡上 4.4 的 signal horizon，不要另外猜數字。
- 語法：`python agents/common/syntax_check.py -e "<expr>" -s <card_id>`（setting 還沒建時先用 `-s default_setting.json` 或 `--region` 對應的既有 setting）；不過就改到 PASS。可用 `--fix` 看規則式修復建議。

## 3. 寫 setting + idea

```
python agents/hypothesis_seer/cli/build_idea.py --card <card_id> \
  --region <R> --universe <U> --delay <D> --neutralization <N> \
  --main "<expr>" --naive "<expr>" --falsify "<expr>" --falsify-differs "<只差的那個變數>" \
  [--revise]
```
- 多行 expression 用 `;` 接在一行，或先存成 `.expr` 檔再傳路徑。
- design_notes（每層為什麼、欄位為什麼）可用 `--notes <json>` 附上；審判官看不到它。
- 指令會自己跑 `syntax_check -i`；FAIL 就修到 PASS。
- 成功後：`python agents/common/card.py set-status <card_id> expr_ready --actor seer --reason "idea v<n> 語法通過"`。

## 4. 回報（平實）

「三條式子已寫進 `DB/ResearchDB/idea/<card_id>.json`（setting：`DB/ResearchDB/setting/<card_id>.json`）。
接下來請你執行：
```
python -m src.idea --idea <card_id>
```
worker 跑完後執行 `python -m src.idea --status <card_id>` 看成績，再 `/judge <card_id>` 讓審判官審式子與結果。」（沒裝審判官：改說「再 `python agents/hypothesis_seer/cli/self_check.py <card_id>` 自檢結果」。）

附「給新手的說明」：每一層 operator 一行為什麼＋來源編號（`knowledge/sources.md`）；哪一條是 naive、哪一條是反向證偽、為什麼只差一個變數。

## 不做

- 不寫 payload、不碰 `DB/AlphaDB/`。
- 不改卡片的四關內容（欄位替換除外，且要 bump-version）。
