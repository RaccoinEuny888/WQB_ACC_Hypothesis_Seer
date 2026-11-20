"""從本機已同步的 data_fields_raw 挑欄位（唯讀）。

  python agents/hypothesis_seer/cli/pick_fields.py --setting H-261115-003 --query "revision,estimate" [--category Analyst] [--limit 30]
  python agents/hypothesis_seer/cli/pick_fields.py --region USA --universe TOP3000 --delay 1 --dataset analyst11
  python agents/hypothesis_seer/cli/pick_fields.py --region USA --universe TOP3000 --delay 1 --list-datasets [--category Analyst]
  python agents/hypothesis_seer/cli/pick_fields.py --region USA --universe TOP3000 --delay 1 --check close,analyst11_xxx
  --json  機器可讀

排序：coverage 高 → alphaCount 低（人少的空位優先）。欄位不存在就說不存在，不猜。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths, idea_io  # noqa: E402


def load_raw(region: str, universe: str, delay: int) -> list[dict]:
    raw_dir = paths.data_dir(region, universe, delay) / "data_fields_raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"本機沒有 {paths.rel(raw_dir)}；請先 run_data_sync.py 同步 {paths.setting_key(region, universe, delay)}")
    out = []
    for p in sorted(raw_dir.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for r in json.load(f):
                    r["_dataset"] = r.get("dataset", {}).get("id", p.stem)
                    r["_category"] = r.get("category", {}).get("name", "")
                    out.append(r)
        except Exception:
            continue
    return out


def _fmt(r: dict) -> str:
    return (f"{r['id']:<42} {r.get('type', ''):<7} cov={r.get('coverage', 0):.2f} users={r.get('userCount', 0):<5} "
            f"alphas={r.get('alphaCount', 0):<6} pyr={r.get('pyramidMultiplier', '')!s:<4} {r['_dataset']:<22} "
            f"{(r.get('description') or '')[:70]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="挑欄位（唯讀）")
    ap.add_argument("--setting", help="setting 檔名／卡號（取 region/universe/delay）")
    ap.add_argument("--region"); ap.add_argument("--universe"); ap.add_argument("--delay", type=int)
    ap.add_argument("--dataset"); ap.add_argument("--category"); ap.add_argument("--query", help="逗號分隔關鍵字，比對 id 與 description")
    ap.add_argument("--min-coverage", type=float, default=0.0)
    ap.add_argument("--type", choices=["MATRIX", "VECTOR", "GROUP"], default=None)
    ap.add_argument("--list-datasets", action="store_true")
    ap.add_argument("--check", help="逗號分隔欄位 id，驗證存在並印中繼資料")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.setting:
        _, setting = idea_io.load_setting(args.setting)
        region, universe, delay = idea_io.setting_rud(setting)
    else:
        if not (args.region and args.universe and args.delay is not None):
            ap.error("需要 --setting 或 --region/--universe/--delay")
        region, universe, delay = args.region, args.universe, args.delay

    rows = load_raw(region, universe, delay)
    if not args.json:
        print(f"[資料] {paths.setting_key(region, universe, delay)}：{len(rows)} 個欄位")

    if args.check:
        want = [x.strip() for x in args.check.split(",") if x.strip()]
        by_id = {r["id"]: r for r in rows}
        builtin = {"open", "close", "high", "low", "volume", "returns", "vwap", "cap", "adv20", "sharesout"}
        result = []
        for w in want:
            if w in by_id:
                result.append({"id": w, "exists": True, **{k: by_id[w].get(k) for k in ("type", "coverage", "userCount", "alphaCount", "pyramidMultiplier", "description", "_dataset", "_category")}})
            else:
                result.append({"id": w, "exists": w in builtin, "note": "平台內建欄位" if w in builtin else "本機沒有這個欄位"})
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for r in result:
                print(("  [OK]   " if r["exists"] else "  [缺]   ") + r["id"] + ("" if r["exists"] and "note" not in r else f"  ← {r.get('note', '')}")
                      + (f"  {r.get('type')} cov={r.get('coverage')} alphas={r.get('alphaCount')} | {(r.get('description') or '')[:80]}" if r.get("type") else ""))
        return 0

    if args.list_datasets:
        agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "cov": 0.0, "alphas": 0, "users": 0, "cat": ""})
        for r in rows:
            if args.category and r["_category"].lower() != args.category.lower():
                continue
            a = agg[r["_dataset"]]
            a["n"] += 1; a["cov"] += r.get("coverage", 0) or 0; a["alphas"] += r.get("alphaCount", 0) or 0
            a["users"] += r.get("userCount", 0) or 0; a["cat"] = r["_category"]
        items = sorted(agg.items(), key=lambda kv: (kv[1]["alphas"] / max(kv[1]["n"], 1)))
        if args.json:
            print(json.dumps([{"dataset": k, **v, "cov_mean": v["cov"] / max(v["n"], 1)} for k, v in items], ensure_ascii=False, indent=2))
        else:
            print(f"{'dataset':<28}{'category':<16}{'fields':>7}{'cov_mean':>9}{'alphas/field':>13}{'users':>7}")
            for k, v in items[: args.limit]:
                print(f"{k:<28}{v['cat']:<16}{v['n']:>7}{v['cov'] / max(v['n'], 1):>9.2f}{v['alphas'] / max(v['n'], 1):>13.1f}{v['users']:>7}")
        return 0

    sel = rows
    if args.dataset:
        sel = [r for r in sel if r["_dataset"] == args.dataset]
    if args.category:
        sel = [r for r in sel if r["_category"].lower() == args.category.lower()]
    if args.type:
        sel = [r for r in sel if r.get("type") == args.type]
    sel = [r for r in sel if (r.get("coverage") or 0) >= args.min_coverage]
    if args.query:
        kws = [k.strip().lower() for k in args.query.split(",") if k.strip()]
        def hit(r):
            text = (r["id"] + " " + (r.get("description") or "")).lower()
            return sum(1 for k in kws if k in text)
        sel = [r for r in sel if hit(r) > 0]
        sel.sort(key=lambda r: (-hit(r), -(r.get("coverage") or 0), r.get("alphaCount") or 0))
    else:
        sel.sort(key=lambda r: (-(r.get("coverage") or 0), r.get("alphaCount") or 0))
    sel = sel[: args.limit]
    if args.json:
        print(json.dumps([{k: r.get(k) for k in ("id", "type", "coverage", "userCount", "alphaCount", "pyramidMultiplier", "description", "_dataset", "_category")} for r in sel], ensure_ascii=False, indent=2))
    else:
        if not sel:
            print("（沒有符合的欄位）")
        for r in sel:
            print("  " + _fmt(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
