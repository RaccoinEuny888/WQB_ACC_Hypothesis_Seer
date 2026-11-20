"""沒有審判官時的 expression 結果自檢：用卡上的生死線 K1／K2 與固定門檻判斷能不能進 template。

  python agents/hypothesis_seer/cli/self_check.py <card_id>            # 印表＋判定；PASS 就把卡設成 expr_self_checked
  python agents/hypothesis_seer/cli/self_check.py <card_id> --no-set   # 只看不改狀態

規則（使用者 2026-11-19 裁定 [R]）：
  main：Sharpe > 1 且 turnover < 0.5
  K1：main 的 Sharpe > naive 的 Sharpe（多剝掉的那一步有用）
  K2：falsify（反向證偽組）的 Sharpe < main 的 Sharpe（歸因沒錯）
三條都 complete 才判；缺 naive 或 falsify 就照實說「K1／K2 無法判」，不算 PASS。
只讀本機 DB/AlphaDB/complete/ 的結果；不打平台。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths, idea_io  # noqa: E402

MAIN_SHARPE, MAIN_TVR = 1.0, 0.5


def _perf(h: str | None) -> tuple[str, dict]:
    if not h:
        return "未送出", {}
    for q, folder in paths.OM.QUEUES.items():
        p = folder / h
        if p.exists():
            if q != "complete":
                return q, {}
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return "complete(讀不到)", {}
            perf = ((rec.get("result") or {}).get("is") or {})
            return "complete", {"sharpe": perf.get("sharpe"), "turnover": perf.get("turnover"), "fitness": perf.get("fitness"),
                                "fails": [c["name"] for c in perf.get("checks", []) if c.get("result") == "FAIL"]}
    return "不在任何佇列", {}


def check(card_id: str) -> dict:
    _, idea = idea_io.load_idea(card_id)
    exprs = idea_io.normalize_expressions(idea.get("expressions", []))
    by_role: dict[str, dict] = {}
    for e in exprs:
        role = e.get("role", "user")
        q, perf = _perf(e.get("hash"))
        by_role.setdefault(role, {"queue": q, **perf, "expr": e.get("expr", "")})
    m, n, f = by_role.get("main", {}), by_role.get("naive", {}), by_role.get("falsify", {})

    def sh(d):
        v = d.get("sharpe")
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)

    rules = []
    ms, mt = sh(m), m.get("turnover")
    rules.append({"rule": f"main Sharpe > {MAIN_SHARPE}", "ok": ms is not None and ms > MAIN_SHARPE, "value": ms,
                  "note": "" if ms is not None else "main 還沒有結果"})
    rules.append({"rule": f"main turnover < {MAIN_TVR}", "ok": mt is not None and float(mt) < MAIN_TVR, "value": mt})
    ns, fs = sh(n), sh(f)
    rules.append({"rule": "K1 main Sharpe > naive Sharpe", "ok": ms is not None and ns is not None and ms > ns, "value": (ms, ns),
                  "note": "" if ns is not None else "naive 沒有結果，K1 無法判"})
    rules.append({"rule": "K2 falsify Sharpe < main Sharpe", "ok": ms is not None and fs is not None and fs < ms, "value": (fs, ms),
                  "note": "" if fs is not None else "falsify 沒有結果，K2 無法判"})
    return {"card": card_id, "roles": by_role, "rules": rules, "pass": all(r["ok"] for r in rules)}


def render(rep: dict) -> str:
    out = [f"{rep['card']} 自檢（沒有審判官時的替代；門檻 [R]）"]
    out.append(f"  {'role':<9}{'queue':<12}{'sharpe':>8}{'turnover':>10}{'fitness':>9}  checks(FAIL)")
    for role, d in rep["roles"].items():
        out.append(f"  {role:<9}{d.get('queue', ''):<12}{str(d.get('sharpe', '')):>8}{str(d.get('turnover', '')):>10}{str(d.get('fitness', '')):>9}  {','.join(d.get('fails', [])) or '-'}")
    for r in rep["rules"]:
        out.append(f"  {'✔' if r['ok'] else '✘'} {r['rule']}　{r['value']}" + (f"　（{r['note']}）" if r.get("note") else ""))
    out.append("  → " + ("PASS：可以進 template（/templatize）" if rep["pass"] else "FAIL：先回卡上第 4 關看是哪一條沒過；K1 沒過＝多剝掉的那一步沒用，K2 沒過＝歸因可能錯"))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="expression 結果自檢")
    ap.add_argument("card")
    ap.add_argument("--no-set", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = check(args.card)
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str) if args.json else render(rep))
    if rep["pass"] and not args.no_set:
        from agents.common import card as card_mod
        card_mod.set_status(args.card, "expr_self_checked", "seer", "self_check.py PASS（main Sharpe>1、tvr<0.5、K1、K2）")
        print(f"[status] {args.card} → expr_self_checked")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
