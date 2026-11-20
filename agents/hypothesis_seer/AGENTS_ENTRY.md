<!-- agents:seer-entry -->
# Hypothesis Seer（占卜家）— 給 Claude Code 以外的工具（Codex、Cursor、Gemini CLI…）

Claude Code 讀 `CLAUDE.md`；其他工具讀這份。內容相同：主對話是占卜家。

1. **先讀 `agents/hypothesis_seer/SEER.md` 全文並照做**：人設、鐵律、說話風格、流程都在那裡。
2. **指令**：這個工具可能沒有 slash command。使用者打 `/hypothesis 我的直覺`（或說「用 hypothesis 幫我…」）時，讀對應的 SKILL.md 照做，把後面的文字當成 `$ARGUMENTS`：

   | 指令 | 讀這份 |
   |---|---|
   | `/hypothesis` `/papers` `/express` `/templatize` `/spc` | `agents/hypothesis_seer/skills/<指令>/SKILL.md` |
   | `/judge` | `agents/expression_inquisitor/skills/judge/SKILL.md`（有裝審判官才有） |
   | `/research-compass` `/dataset-profile` `/operator-classify` | `agents/research_compass/skills/<指令>/SKILL.md`（有裝羅盤才有） |

3. **審判官要「盲審」**：skill 寫「Agent 工具 `subagent_type: expression-inquisitor`」的地方，如果這個工具不能開 subagent，**不要自己代替審判官判決**（你寫的卡，你審就不是盲審）。改請使用者開一個新的對話，貼上：
   「請讀 `agents/expression_inquisitor/AGENT.md`，以審判官身分審 <卡號>，stage=<stage>。先執行 `python agents/expression_inquisitor/cli/blind_pack.py <卡號> --stage <stage>` 取得盲包，依規則判決並寫判決書。」
   判決書寫好後回到這裡，照 `/judge` 第 4 步轉達（通過／重新占卜／拒絕）。
4. **其他 Claude Code 專屬功能的替代**：
   - 判斷「有沒有裝審判官」：`ls .claude/agents/expression-inquisitor.md` 或 `ls agents/expression_inquisitor/AGENT.md`，任一存在就算有。
   - 沒有 AskUserQuestion：skill 已寫了文字版的問法，列選項後停下來等使用者回。
   - 沒有 WebSearch：照 skill 裡「沒有 WebSearch」的分支走（文獻只用使用者給的來源、全標 `[?]`）。
   - `/spc` 第 6 步的預測試要開 subagent：不能開就請使用者把 prompt 貼到乾淨視窗跑一次、把輸出存成 `runs/pretest.json`。
5. 鐵律照舊：不讀 `.env`、`session.pkl`、`login_time.pkl`；不送模擬、不寫 payload、不碰 `DB/AlphaDB/`；session 過期就停下來請使用者啟動 worker 並登入。
<!-- /agents:seer-entry -->
