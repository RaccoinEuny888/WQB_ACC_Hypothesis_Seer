"""SPC 提交登記簿（DB/ResearchDB/spc/registry.jsonl，append-only；提交動作由使用者在平台執行）。

  python agents/hypothesis_seer/cli/spc_registry.py submitted H-xxx --name InsiderCluster-USMid50-v1 --weight 0.05 [--model ...] [--frequency Weekly]
  python agents/hypothesis_seer/cli/spc_registry.py weight H-xxx --name ... --weight 0 --reason "持續 Failed Validation"
  python agents/hypothesis_seer/cli/spc_registry.py checked H-xxx --name ... --status ok|failed_validation [--note ...]
  python agents/hypothesis_seer/cli/spc_registry.py list
  python agents/hypothesis_seer/cli/spc_registry.py coverage        # 全組合不重複標的數（目標 ≥500）、同檔出現在幾份 prompt
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths, ledger  # noqa: E402


def read_all() -> list[dict]:
    p = paths.OUT.SPC_REGISTRY
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def append(rec: dict) -> dict:
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), **rec}
    paths.ensure_parent(paths.OUT.SPC_REGISTRY)
    with open(paths.OUT.SPC_REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def current_state() -> dict[str, dict]:
    """每個 prompt name 的最新狀態。"""
    st: dict[str, dict] = {}
    for r in read_all():
        s = st.setdefault(r["prompt_name"], {"card_id": r.get("card_id"), "prompt_name": r["prompt_name"], "weight": None,
                                              "status": "ok", "submitted_at": None, "last_checked": None, "model": None, "frequency": None})
        if r["event"] == "spc_submitted":
            s.update({"weight": r.get("weight"), "submitted_at": r["ts"], "model": r.get("model"), "frequency": r.get("frequency"), "version": r.get("version")})
        elif r["event"] == "spc_weight_changed":
            s["weight"] = r.get("weight")
        elif r["event"] == "spc_status_checked":
            s["status"] = r.get("status"); s["last_checked"] = r["ts"]
    for s in st.values():
        # 權重歸零 ＝ 下架：狀態自動變 Fail；否則顯示 Submitted
        s["label"] = "Fail" if (s.get("weight") or 0) <= 0 else f"Submitted, Weight: {s.get('weight')}"
    return st


def by_card() -> dict[str, list[dict]]:
    """卡號 → 這張卡的 prompt 狀態清單（羅盤的結案卡用）。"""
    out: dict[str, list[dict]] = {}
    for s in current_state().values():
        out.setdefault(str(s.get("card_id")), []).append(s)
    return out


def coverage() -> dict:
    st = current_state()
    per_isin: Counter = Counter()
    per_prompt = {}
    for name, s in st.items():
        if (s.get("weight") or 0) <= 0:
            continue
        uj = paths.spc_dir(s["card_id"]) / "universe.json"
        if uj.exists():
            isins = json.loads(uj.read_text(encoding="utf-8")).get("isins", [])
            per_prompt[name] = len(isins)
            for i in isins:
                per_isin[i] += 1
    return {"n_active_prompts": len(per_prompt), "n_unique_instruments": len(per_isin), "target": 500,
            "n_overlap_instruments": sum(1 for c in per_isin.values() if c > 1), "per_prompt": per_prompt}


def main() -> int:
    ap = argparse.ArgumentParser(description="SPC 登記簿")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submitted"); s.add_argument("card"); s.add_argument("--name", required=True); s.add_argument("--weight", type=float, required=True)
    s.add_argument("--model"); s.add_argument("--frequency"); s.add_argument("--version", type=int)
    w = sub.add_parser("weight"); w.add_argument("card"); w.add_argument("--name", required=True); w.add_argument("--weight", type=float, required=True); w.add_argument("--reason", default="")
    c = sub.add_parser("checked"); c.add_argument("card"); c.add_argument("--name", required=True); c.add_argument("--status", required=True, choices=["ok", "failed_validation"]); c.add_argument("--note", default="")
    sub.add_parser("list"); sub.add_parser("coverage")
    args = ap.parse_args()

    if args.cmd == "submitted":
        if not 0 < args.weight <= 1:
            print("權重要在 0～1"); return 1
        if args.weight > 0.10:
            print("  [WARN] 首次提交建議 0.05～0.10（低權重觀察期）")
        rec = append({"event": "spc_submitted", "card_id": args.card, "prompt_name": args.name, "weight": args.weight,
                      "model": args.model, "frequency": args.frequency, "version": args.version})
        ledger.append("user", "spc_submitted", args.card, {"prompt_name": args.name, "weight": args.weight})
        # prompt.json 狀態
        pj = paths.spc_dir(args.card) / "prompt.json"
        if pj.exists():
            d = json.loads(pj.read_text(encoding="utf-8")); d["status"] = "submitted"; d["submitted_name"] = args.name
            pj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(rec, ensure_ascii=False)); print("提醒：不依單日 PnL 調權重；定期檢查是否 Failed Validation，是就 weight 歸零。")
    elif args.cmd == "weight":
        rec = append({"event": "spc_weight_changed", "card_id": args.card, "prompt_name": args.name, "weight": args.weight, "reason": args.reason})
        ledger.append("user", "spc_weight_changed", args.card, {"prompt_name": args.name, "weight": args.weight, "reason": args.reason})
        print(json.dumps(rec, ensure_ascii=False))
        if args.weight <= 0:
            print(f"{args.name} 權重歸零 → 狀態 Fail（卡上只記狀態與權重）")
    elif args.cmd == "checked":
        rec = append({"event": "spc_status_checked", "card_id": args.card, "prompt_name": args.name, "status": args.status, "note": args.note})
        ledger.append("user", "spc_status_checked", args.card, {"prompt_name": args.name, "status": args.status})
        print(json.dumps(rec, ensure_ascii=False))
        if args.status == "failed_validation":
            print("持續 Failed Validation → 把權重歸零：spc_registry.py weight <card> --name ... --weight 0")
    elif args.cmd == "list":
        st = current_state()
        if not st:
            print("（還沒有提交登記）")
        for name, s in st.items():
            print(f"  {name:<36} 卡 {s['card_id']}  {s['label']}  平台檢查 {s['status']}  提交 {str(s['submitted_at'] or '')[:10]}  最後檢查 {str(s['last_checked'] or '—')[:10]}")
    else:
        print(json.dumps(coverage(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
