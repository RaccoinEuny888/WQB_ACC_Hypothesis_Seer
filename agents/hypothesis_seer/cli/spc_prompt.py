"""SPC prompt 包（占卜家工具）：子清單、prompt.json 組裝、字元預算、audit 開關、表單草稿。

  python agents/hypothesis_seer/cli/spc_prompt.py masters             # 列出主清單與期限
  python agents/hypothesis_seer/cli/spc_prompt.py master <清單.txt> --source user_paste   # 沒裝審判官時：不檢查、直接存成主清單
  # 從主清單切子清單（跟著假說切面：--pick ticker 清單 / --rank 101-150 / --file 每行 ticker）
  python agents/hypothesis_seer/cli/spc_prompt.py universe H-xxx --rank 101-150 [--master <file>] [--facet "市值帶 101-150"]
  python agents/hypothesis_seer/cli/spc_prompt.py universe H-xxx --pick AAPL,MSFT,NVDA
  # 占卜家先用 Write 寫原稿 agents/workspace/spc/H-xxx/sections.json（各段英文內容），再組裝；產出寫到 DB/ResearchDB/spc/H-xxx/：
  python agents/hypothesis_seer/cli/spc_prompt.py render H-xxx [--audit on|off] [--name ...] [--model ...] [--frequency Weekly] [--weight 0.05]
  python agents/hypothesis_seer/cli/spc_prompt.py show H-xxx          # 印 rendered_text（貼去測試）
  python agents/hypothesis_seer/cli/spc_prompt.py finalize H-xxx      # 驗證通過後：audit 關掉、Sample Output 取 run_3、寫 form_final.md

sections.json 的鍵（都是英文 prompt 片段，universe 與 footer 由程式帶入）：
  role, web_search, workflow, direction_rule, bull_bear_gate, scoring, mechanical_direction(bool), target_count(int)
格式鎖定尾註一字不差（knowledge/spc/spec/FORMAT_SPEC.md 第三節）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths, ledger  # noqa: E402
import re  # noqa: E402
from datetime import timedelta  # noqa: E402

# 主清單的讀取與存檔放在占卜家這裡，沒裝審判官也能用；
# 格式／Luhn／MIC／去重／反查等檢查屬於審判官（agents/expression_inquisitor/cli/spc_universe.py），沒裝就不檢查。
PAIR_RE = re.compile(r"([A-Z]{2}[A-Z0-9]{9}[0-9])\s*\|\s*([A-Z]{4})")
EXPIRE_DAYS = 90


def load_master(path: str | None = None) -> tuple[Path | None, dict | None]:
    if path:
        p = Path(path)
    else:
        masters = sorted(paths.OUT.SPC_UNIVERSE.glob("master_*.json")) if paths.OUT.SPC_UNIVERSE.exists() else []
        masters = [m for m in masters if "_expired" not in m.name]
        p = masters[-1] if masters else None
    if not p or not p.exists():
        return None, None
    return p, json.loads(p.read_text(encoding="utf-8"))


def master_status(p: Path, m: dict) -> str:
    exp = m.get("expires_at")
    if exp and datetime.fromisoformat(exp).date() < datetime.now().date():
        return f"已過期（{exp}）→ 重新生成；舊檔改名加 _expired"
    return f"有效至 {exp}" + ("" if m.get("checked", True) else "（未經審判官檢查）")


def cmd_masters(args) -> int:
    if not paths.OUT.SPC_UNIVERSE.exists() or not list(paths.OUT.SPC_UNIVERSE.glob("master_*.json")):
        print("（還沒有主清單；先 /spc universe）"); return 0
    for p in sorted(paths.OUT.SPC_UNIVERSE.glob("master_*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {p.name}: {m.get('n')} 檔，來源 {m.get('source')}，{master_status(p, m)}，反查 {m.get('reverse_check') or '未做'}")
    return 0


def cmd_master(args) -> int:
    """沒裝審判官時：把使用者貼回（或 WebSearch 查到）的清單直接存成主清單，不做任何檢查。"""
    items, seen = [], set()
    for raw in Path(args.file).read_text(encoding="utf-8").splitlines():
        line = raw.strip().strip("`").strip()
        m = PAIR_RE.search(line) if line and not line.startswith("#") else None
        if not m or m.group(1) in seen:
            continue
        head = re.sub(r"^\d+[.)]\s*", "", line[: m.start()].rstrip(" ,=-\t"))
        parts = [x.strip() for x in re.split(r"[,\t]", head) if x.strip()]
        seen.add(m.group(1))
        items.append({"rank": len(items) + 1, "ticker": (parts[0].split()[0].upper() if parts else ""),
                      "name": ", ".join(parts[1:]), "isin": m.group(1), "mic": m.group(2), "verified_name": None})
    if not items:
        print("讀不到任何 `TICKER, NAME, ISIN|MIC` 行"); return 1
    today = datetime.now()
    p = paths.OUT.SPC_UNIVERSE / f"master_{today.strftime('%Y%m%d')}.json"
    paths.ensure_parent(p)
    p.write_text(json.dumps({"generated_at": today.isoformat(timespec="seconds"), "source": args.source, "checked": False,
                             "expires_at": (today + timedelta(days=EXPIRE_DAYS)).date().isoformat(),
                             "n": len(items), "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger.append("seer", "spc_universe_built", None, {"file": paths.rel(p), "n": len(items), "source": args.source, "checked": False}, [paths.rel(p)])
    print(f"[master] {len(items)} 檔 → {paths.rel(p)}（沒有審判官：未檢查格式、Luhn、MIC、反查）")
    return 0

FOOTER = ("Output ONLY the raw JSON object. Do not include any conversational filler, markdown formatting (like ```json), "
          "or explanatory prose.")
AUDIT_BLOCK = ("AUDIT (testing only)\nAfter the JSON object, print a line containing exactly ---AUDIT--- and then, for every stock, "
               "one line: TICKER | the key figure(s) you found | the date of the source | the source URL. "
               "This section is for verification that you actually searched; keep it after the JSON.")
BUDGET = {"role": 600, "workflow": 1800, "web_search": 300, "bull_bear_gate": 400, "universe": 1100, "scoring_footer": 500}
HARD_LIMIT = 10000
SECTION_ORDER = [("ROLE", "role"), ("UNIVERSE (ticker = ISIN|MIC; use the ticker to search, use ISIN|MIC as the output key)", "_universe"),
                 ("MANDATORY WEB SEARCH", "web_search"), ("WORKFLOW (apply to every stock, in order)", "workflow"),
                 ("DIRECTION RULE (mechanical, do not override)", "direction_rule"), ("BULL vs. BEAR GATE", "bull_bear_gate"),
                 ("SCORING", "scoring"), ("_AUDIT", "_audit"), ("OUTPUT", "_output")]


def _d(card: str) -> Path:
    return paths.spc_dir(card)


def _load_prompt(card: str) -> dict:
    p = _d(card) / "prompt.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_prompt(card: str, data: dict) -> Path:
    p = _d(card) / "prompt.json"
    paths.ensure_parent(p)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ------------------------------------------------------------------ universe
def cmd_universe(args) -> int:
    mp, master = load_master(args.master)
    if not master:
        print("沒有主清單。先 /spc universe"); return 1
    print(f"[master] {paths.rel(mp)}：{master['n']} 檔，{master_status(mp, master)}")
    items = master["items"]
    if args.rank:
        a, b = [int(x) for x in args.rank.split("-")]
        sel = [it for it in items if a <= int(it.get("rank", 0)) <= b]
    elif args.pick:
        want = [t.strip().upper() for t in args.pick.split(",") if t.strip()]
        by = {it["ticker"]: it for it in items}
        sel = [by[t] for t in want if t in by]
        missing = [t for t in want if t not in by]
        if missing:
            print(f"  [WARN] 主清單沒有：{missing}（先補進主清單再切，不要手寫 ISIN）")
    elif args.file:
        want = [ln.strip().upper() for ln in Path(args.file).read_text(encoding="utf-8").splitlines() if ln.strip()]
        by = {it["ticker"]: it for it in items}
        sel = [by[t] for t in want if t in by]
    else:
        print("要 --rank / --pick / --file 其中一個"); return 1
    if not sel:
        print("切出來是空的"); return 1
    lines = [f"{it['ticker']} = {it['isin']}|{it['mic']}" for it in sel]
    up = _d(args.card) / "universe.txt"
    paths.ensure_parent(up)
    up.write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {"card_id": args.card, "master_file": paths.rel(mp), "facet": args.facet or (args.rank and f"rank {args.rank}") or "pick",
            "n": len(sel), "built_at": datetime.now().isoformat(timespec="seconds"), "tickers": [it["ticker"] for it in sel],
            "isins": [it["isin"] for it in sel]}
    (_d(args.card) / "universe.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[universe] {len(sel)} 檔 → {paths.rel(up)}（切面：{meta['facet']}）")
    if not 35 <= len(sel) <= 65:
        print("  [WARN] 官方建議每份 ~50 檔")
    return 0


# ------------------------------------------------------------------ render
def render_text(sections: dict, universe_lines: list[str], audit: bool) -> str:
    parts = []
    for title, key in SECTION_ORDER:
        if key == "_universe":
            body = "\n".join(universe_lines)
        elif key == "_audit":
            if not audit:
                continue
            title, body = "AUDIT (testing only)", AUDIT_BLOCK.split("\n", 1)[1]
        elif key == "_output":
            body = ('A single JSON object: {"ISIN|MIC": score, ...}, with keys taken only from the universe above. '
                    "Score EVERY stock in the universe; use exactly 3 decimal places; scores must be differentiated (never equal-weighted).\n" + FOOTER)
        else:
            body = (sections.get(key) or "").strip()
            if not body:
                continue
        parts.append(f"{title}\n{body}")
    return "\n\n".join(parts).strip() + "\n"


def cmd_render(args) -> int:
    d = _d(args.card)
    sp = paths.spc_draft_dir(args.card) / "sections.json"  # 原稿在 agents 工作區；產出寫 DB/ResearchDB/spc/
    if not sp.exists() and (d / "sections.json").exists():
        sp = d / "sections.json"  # 舊版放在 ResearchDB 的原稿仍可讀
    up = d / "universe.txt"
    if not sp.exists():
        print(f"缺 {paths.rel(paths.spc_draft_dir(args.card) / 'sections.json')}：占卜家先用 Write 寫各段（role, web_search, workflow, direction_rule, bull_bear_gate, scoring, mechanical_direction, target_count）"); return 1
    if not up.exists():
        print(f"缺 {paths.rel(up)}：先 spc_prompt.py universe {args.card} …"); return 1
    sections = json.loads(sp.read_text(encoding="utf-8"))
    uni = [ln for ln in up.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = _load_prompt(args.card)
    audit = {"on": True, "off": False}.get(args.audit, prev.get("audit", True))
    text = render_text(sections, uni, audit)
    n = len(text)
    form = prev.get("form", {})
    for k in ("name", "model", "model_version", "frequency", "weight"):
        v = getattr(args, k, None)
        if v is not None:
            form[k] = v
    version = prev.get("version", 0) + 1 if args.bump or not prev else prev.get("version", 1)
    data = {"card_id": args.card, "version": version, "channel": "spc", "universe_file": paths.rel(up),
            "n_universe": len(uni), "sections": sections, "audit": audit, "rendered_text": text, "char_count": n,
            "char_limit": HARD_LIMIT, "form": form, "status": prev.get("status", "draft"),
            "mechanical_direction": bool(sections.get("mechanical_direction", True)),
            "target_count": int(sections.get("target_count") or len(uni)),
            "updated_at": datetime.now().isoformat(timespec="seconds"), "history": prev.get("history", [])}
    p = _save_prompt(args.card, data)
    (d / "prompt.txt").write_text(text, encoding="utf-8")
    print(f"[prompt] v{version} → {paths.rel(p)}（audit={'on' if audit else 'off'}）")
    print(f"  字元數 {n:,} / {HARD_LIMIT:,}（{'OK' if n <= HARD_LIMIT else '超限！'}；建議留 ≥3,000 緩衝給修訂版）")
    sec_len = {k: len((sections.get(k) or "")) for k in ("role", "web_search", "workflow", "direction_rule", "bull_bear_gate", "scoring")}
    sec_len["universe"] = sum(len(x) + 1 for x in uni)
    for k, v in sec_len.items():
        b = BUDGET.get(k)
        print(f"  {k:<16}{v:>6} 字元{'' if not b else f'（建議 ~{b}）'}")
    print(f"  universe {len(uni)} 檔；mechanical_direction={data['mechanical_direction']}；target_count={data['target_count']}")
    print(f"  form：{json.dumps(form, ensure_ascii=False)}")
    ledger.append("seer", "spc_prompt_built", args.card, {"version": version, "chars": n, "audit": audit, "n_universe": len(uni)}, [paths.rel(p)])
    if n > HARD_LIMIT:
        print("  刪減順序：工作流冗詞 → 縮 universe → 絕不砍尾註與 web search 指令")
        return 1
    return 0


def cmd_show(args) -> int:
    data = _load_prompt(args.card)
    if not data:
        print("還沒有 prompt.json"); return 1
    print(data["rendered_text"])
    return 0


def cmd_finalize(args) -> int:
    d = _d(args.card)
    data = _load_prompt(args.card)
    if not data:
        print("還沒有 prompt.json"); return 1
    vals = sorted(d.glob("validation_v*.json"))
    if not vals:
        print("沒有驗證報告（審判官 spc_validate.py 還沒跑）→ 不能定稿"); return 1
    last = json.loads(vals[-1].read_text(encoding="utf-8"))
    if not last.get("pass"):
        print(f"最新驗證 {vals[-1].name} 未通過 → 不能定稿；提交不可逆"); return 1
    run3 = d / "runs" / "run_3.json"
    sample = run3.read_text(encoding="utf-8").split("---AUDIT---")[0].strip() if run3.exists() else ""
    if not sample:
        print("缺 runs/run_3.json（Sample Output 必須是第 3 次實測原文）"); return 1
    data["audit"] = False
    data["rendered_text"] = render_text(data["sections"], [ln for ln in (d / "universe.txt").read_text(encoding="utf-8").splitlines() if ln.strip()], False)
    data["char_count"] = len(data["rendered_text"])
    data["status"] = "final"
    data["finalized_at"] = datetime.now().isoformat(timespec="seconds")
    _save_prompt(args.card, data)
    (d / "prompt.txt").write_text(data["rendered_text"], encoding="utf-8")
    f = data.get("form", {})
    form_md = (f"# SPC 表單定稿 {args.card} v{data['version']}\n\n| 欄位 | 值 |\n|---|---|\n"
               f"| Prompt Name | {f.get('name', '')} |\n| Model | {f.get('model', '')} |\n| Model Version | {f.get('model_version', '')} |\n"
               f"| Update Frequency | {f.get('frequency', '')} |\n| Prompt Weight | 建議 {f.get('weight', '')}（首次 0.05～0.10；實際設多少由你決定） |\n"
               f"| Prompt 字元數 | {data['char_count']:,} / 10,000 |\n\n## Prompt（貼進表單）\n\n```\n{data['rendered_text']}```\n\n"
               f"## Sample Prompt Output（第 3 次實測原文）\n\n```\n{sample}\n```\n\n提交後告訴占卜家你實際設的權重：`/spc submitted {args.card} --name {f.get('name', '')} --weight <你在平台設的權重>`\n")
    (d / "form_final.md").write_text(form_md, encoding="utf-8")
    print(f"[final] audit 已關、{data['char_count']:,} 字元 → {paths.rel(d / 'form_final.md')}；提交由你在平台執行")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SPC prompt 包")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("universe"); u.add_argument("card"); u.add_argument("--master"); u.add_argument("--rank"); u.add_argument("--pick"); u.add_argument("--file"); u.add_argument("--facet")
    r = sub.add_parser("render"); r.add_argument("card"); r.add_argument("--audit", choices=["on", "off"]); r.add_argument("--bump", action="store_true")
    for k in ("name", "model", "model_version", "frequency", "weight"):
        r.add_argument(f"--{k}")
    s = sub.add_parser("show"); s.add_argument("card")
    f = sub.add_parser("finalize"); f.add_argument("card")
    sub.add_parser("masters")
    m = sub.add_parser("master"); m.add_argument("file"); m.add_argument("--source", default="user_paste", choices=["user_paste", "websearch"])
    args = ap.parse_args()
    return {"universe": cmd_universe, "render": cmd_render, "show": cmd_show, "finalize": cmd_finalize,
            "masters": cmd_masters, "master": cmd_master}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
