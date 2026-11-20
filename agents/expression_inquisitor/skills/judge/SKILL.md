---
name: judge
description: 呼叫審判官（expression-inquisitor subagent）審一張卡：自動判斷該審假說卡、expression＋結果、還是 template；可把使用者自己寫的 expression 一起送審。用法 /judge <card_id> [--stage card|expr|template] [--expr "..."]
argument-hint: <card_id> [--stage card|expr|template] [--expr "expression"]
---

# /judge

參數：`$ARGUMENTS`。從 open machine 根目錄執行。

1. 解析參數：卡號；`--stage`（預設 auto；`card`／`expr`／`template`／`spc`）；`--expr "<expression>"`（使用者自己寫的式子）。卡是 `channel: both` 時 auto 會先審 alpha 通道，要審 SPC 請明示 `--stage spc`。
2. 有 `--expr`：
   - idea 檔已存在 → `python agents/hypothesis_seer/cli/build_idea.py --card <card_id> --append-user "<expr>"`
   - idea 檔不存在 → 需要 setting：問使用者 region／universe／delay／neutralization（或沿用卡片 frontmatter），然後
     `python agents/hypothesis_seer/cli/build_idea.py --card <card_id> --region .. --universe .. --delay .. --neutralization .. --main "<expr>" --author user`
   - 語法 FAIL → 先把 syntax_check 的訊息給使用者，不送審。
3. 呼叫審判官：Agent 工具，`subagent_type: expression-inquisitor`，prompt **只能是**：
   「請審 <card_id>，stage=<stage 或 auto>。先執行 `python agents/expression_inquisitor/cli/blind_pack.py <card_id> --stage <stage>` 取得盲包，依你的規則判決並寫判決書。」
   不附任何推理、設計說明或對話。
4. 把審判官的回覆**原文**轉達給使用者（它的口吻是它的），然後用占卜家的說法翻譯判決——讚美女神＝**通過**、懺悔後再審＝**重新占卜**、處決＝**拒絕**——並更新狀態、補一句下一步：
   - 狀態：通過 → `card.py set-status <card_id> approved`（card）／`expr_approved`（expr）；重新占卜 → `needs_work`；拒絕 → 判決書**明確寫「機制被證偽」**才設 `rejected`（全域擋同機制新卡），否則設 `needs_work` 並說「拒絕是因為寫得不夠具體，不是機制錯」。`--actor seer --reason "<條目>"`。
   - 不自動進第二輪：列出條目，問使用者要不要修；修完他說了才再送。
   - 通過（card）→ alpha 通道：「要我為它寫 expression 嗎？（`/express <card_id>`）」；spc 通道：「要我寫 SPC prompt 嗎？（`/spc <card_id>`）」
   - 通過（expr）→ 「可以進 template 了：`/templatize <card_id>`」
   - 通過（template）→ 印 GA 指令（見 /templatize 第 4 步）
   - 通過（spc，只審了 prompt）→ 「進預測試與 3 次實測（見 /spc 第 6～7 步）」；通過（spc，含 runs）→ 「可以定稿：`python agents/hypothesis_seer/cli/spc_prompt.py finalize <card_id>`，提交不可逆」
   - 重新占卜 → 列條件；問「要我依條件修訂嗎？」（card 直接改卡片並 `bump-version`、expr 用 `/express <card_id> --revise`）
   - 拒絕 → 說明原因；真的是「機制被證偽」才說進禁區；若訊號很強但歸因錯，提醒「另立新卡、在新戰場驗」
5. 沒有裝審判官（Agent 呼叫失敗）→ 說明需要安裝 `agents/install.sh --only inquisitor`，不要自己代替它判決。
