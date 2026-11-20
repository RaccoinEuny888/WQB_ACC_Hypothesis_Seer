---
name: hypothesis
description: 占卜家：第一站把你的直覺、文章或 dataset 整理成最多 3 個市場命題（附本機可用的 dataset／欄位與 channel 建議）讓你選；第二站對你選的命題找文獻、寫四關、自檢信心分數後建假說卡。不自動送審判官（有裝才問你）。用法 /hypothesis <輸入>；沒有輸入就請你說直覺。
argument-hint: <直覺一句話 | 文章連結或貼文 | dataset id | datafield id | 空>
---

# /hypothesis

輸入：`$ARGUMENTS`。全部指令從 open machine 根目錄執行。語氣平實（見 SEER.md）。

## 0. 前置

- 沒有輸入 → 只回一句：「告訴我一個直覺、貼一篇文章、或給一個 dataset，我先整理成幾個命題讓你選。」然後停。
- 判斷輸入型態：直覺／文章（連結或貼文；連結就抓來讀，讀不到就請他貼內文）／dataset id／datafield id／羅盤建議。
- 目標戰場：預設 `USA / TOP3000 / 1`；使用者有指定就用他的。看本機有沒有同步：`ls DB/ResearchDB/data/latest/`。**沒同步不停**——第一站照做，dataset 建議改用你知道的 category 並標 `[?]`，並說「要建卡前請先同步（`python run_data_sync.py`）」。

## 第一站：命題（只整理，不搜文獻、不建卡、不送審）

1. 讀完輸入。文章型：先用一張表講它說了什麼（資料／主張／你的評估：哪些是故事、哪些可當證據）。
2. 抽出 **最多 3 個市場命題**。命題是**素材方向**，不是假說——格式：
   「**現象**：…；**可能的機制方向**：…；**還不知道的**：…」
   不用在這裡寫誰做錯、對手是誰。單一公司／單一事件要先推廣成「很多股票之間可比較」的命題，推不出來就說。
3. 每個命題附三件事：
   - **量得到嗎**：`python agents/hypothesis_seer/cli/pick_fields.py --region .. --universe .. --delay .. --query "<關鍵字>"` 找本機存在的候選欄位（最多 3 個，附 description、coverage、alphaCount）；找不到就說找不到，不補造。
   - **channel 建議**：`regular alpha`（量的是 BRAIN 欄位）／`SPC`（量的是公開權威資料且方向能寫成機械規則）／`both`，一句理由（判準：`four_gates.md` 4.4）。建議含 SPC、而 `ls DB/ResearchDB/spc/universe/master_*.json` 找不到主清單時，補一句：「走 SPC 要先建立並驗證 ISIN|MIC 主清單（`/spc universe`），建卡不受影響，組 prompt 前做好就行。」
   - **難度一句**：例如「事件型、樣本少」「跟既有卡 H-… 很近，要說清楚差在哪」（`python agents/common/card.py list` 看一眼）。
4. 讓使用者選：哪些命題（可多選）、channel 用建議的還是改。**有 AskUserQuestion 工具就用它**（一題選命題、一題選 channel）；**沒有這個工具（或呼叫失敗）就退成文字**：把命題編號 1～3 列出來，問「回我編號（可複選）和 channel，例如 `1,3 alpha`」，然後**停下來等他回**，不要替他選。沒有合適的 → 請他換一個方向或補材料；命題**不落檔**，選了才進第二站。

## 第二站：假說＋四關＋自檢（對每個選定的命題）

1. **文獻 ≤5 篇**：有 WebSearch 就去 WQ 化地查（學術關鍵字＋anomaly／mispricing／limits to arbitrage），每篇記來源、年份、主張、支持／反面；反面找不到寫「未找到反面證據 `[?]`」。沒有 WebSearch → 只用使用者給的來源，全標 `[?]`。記帳 `literature_collected`。
2. **一句話假說**：「**誰**在**什麼情境**下**系統性做錯什麼**，所以**做多／做空什麼**。」
3. **查重**（有羅盤才做）：`ls agents/research_compass/cli/dedup.py` 存在 → `python agents/research_compass/cli/dedup.py --text "<假說>" --dataset <ds> --tag <tag>`；撞 `rejected`（機制被證偽）→ 告訴使用者並問要不要繼續；撞其他 → 第 4 關寫差異。沒有羅盤 → 跳過並說一句。
4. **寫卡**：`python agents/common/card.py new-id` 取卡號；欄位用 `pick_fields.py --check a,b` 核對，只用印出存在的 id；用下面模板寫到 `DB/ResearchDB/hypothesis/<card_id>.md`。先看 `ls .claude/agents/expression-inquisitor.md`：**有審判官** → status `unreviewed`、不寫 `confidence`、「# 自檢」段只寫一行「由審判官審，不自檢」；**沒有** → 做第 5 步自檢，status `self_checked`。
5. **自檢（只在沒裝審判官時做**；定義 `four_gates.md`，樣式 `vague_logic_patterns.md`）：四關各給 1～10 分＋一句理由，寫進卡的「# 自檢」段；**總分＝四關平均四捨五入**，寫進 frontmatter `confidence`。寫不出具體內容的那關給 ≤3 分並寫「寫不出來的是什麼」——**照樣建卡**，由使用者決定要不要往下。唯一不建卡的情況：使用者明說放棄。
6. `python agents/common/card.py validate <card_id>` 必須 PASS；記帳 `card_created`（payload：origin、hypothesis、mechanism_tag、dataset、channel、confidence）。
7. **審判官（只問，不自動送）**：
   - 有裝 → 問一句（有 AskUserQuestion 就用，沒有就用文字問、等他回）：「要送審判官看嗎？它很嚴，被拒絕不代表假說錯，只代表要寫得更具體。」要 → 照 `/judge <card_id>` 的流程（判決轉成通過／重新占卜／拒絕）；不要 → 停在 `unreviewed`。
   - 沒裝 → 一句「沒有裝審判官，先以自檢為準；之後想要第二意見再裝」。

### 卡片模板（段落標題 `card.py validate` 會檢查）

```markdown
---
id: H-YYMMDD-NNN
hypothesis: 一句話（誰、情境、做錯什麼、做多／做空）
direction: long | short | both
status: self_checked               # 有審判官時 unreviewed
confidence: 6                      # 四關平均，1～10；有審判官時不寫這行
version: 1
created: YYYY-MM-DD
origin: direction | dataset | datafield | paper | compass | intuition
dataset: <dataset id>
region: USA
universe: TOP3000
delay: 1
mechanism_tag: <短標籤，查重用>
channel: alpha | spc | both
sources: [S1, S2]
related: []
---
# 命題
（第一站選定的那個命題，原文一段）

# 文獻
| 編號 | 來源 | 年份 | 主張 | 支持／反面 |
|---|---|---|---|---|
| S1 | … | … | … | 支持 |

# 第 1 關：現象與機制
… [L]/[H]/[?]

# 第 2 關：對手與為何不修正
…

# 第 3 關：為何持續
…（誠實標強度）

# 第 4 關：證偽設計
4.1 可反駁預測：…
4.2 失效條件：強＝…；弱但正常＝…；真的壞掉＝…
4.3 對照組：naive 版本＝…；反向證偽組＝…（機制若成立這組應明顯變弱）
4.4 量測設計：observable variable＝`field_id`（型別、coverage、alphaCount）；signal horizon＝…；transformation＝…；channel 提議＝alpha｜spc｜both（含 spc 另寫 (a)(b)(c)，見 four_gates.md）
4.5 生死線：K1 naive 對照 …；K2 反向證偽 …；K3 形狀 …；K4 換戰場 …（門檻 [R]）

# 自檢
（有審判官時這段只寫：由審判官審，不自檢）
| 關 | 分數 | 一句理由（最弱的地方寫清楚） |
|---|---|---|
| 1 | 7 | … |
| 2 | 5 | … |
| 3 | 4 | 為何持續只有推測，沒有文獻 |
| 4 | 6 | … |
總分 6/10。

# 操作化方向
（四模組思路：清洗→訊號→平滑→組內，不含 expression）

# 版本紀錄
- v1（YYYY-MM-DD）：建卡

# 戰場足跡／驗證紀錄
| 日期 | 階段 | 結果 | 一句結論 |
|---|---|---|---|
```

## 回報（平實；事實不變）

「這次建了 m 張卡：
- H-…：<假說一句話>（dataset、方向、channel；沒審判官時加「信心 N/10」，**只有某關 ≤4 分才點出來**：「第 k 關偏低：一句」，分數高的不用講；有審判官時寫判決：通過／重新占卜／拒絕）
…
接下來你可以：alpha 通道 `/express <card>` 寫 expression；spc 通道 `/spc <card>` 寫 prompt（還沒有主清單就先 `/spc universe`）；想要第二意見 `/judge <card>`。你也可以自己寫式子，放進 `DB/ResearchDB/idea/<card>.json` 後 `/judge <card>`。」

附「給新手的說明」：為什麼先拆成命題再寫假說、四關各擋什麼（引用 `four_gates.md`、`vague_logic_patterns.md` 樣式編號）、偏低的那關要補什麼才會變高。
