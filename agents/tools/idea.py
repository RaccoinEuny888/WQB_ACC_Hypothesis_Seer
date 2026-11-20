"""idea → payload → AlphaDB/pending（由使用者執行；安裝後位於 src/idea.py）

  python -m src.idea --idea H-261115-003                 # 送 pending，hash 寫回 idea 檔
  python -m src.idea --idea H-261115-003 --roles main    # 只送某些 role
  python -m src.idea --idea H-261115-003 --dry           # 只算 hash、不寫
  python -m src.idea --status H-261115-003               # 每條 expression 現在在哪一格、成績多少

流程與 GA 相同：idea 檔的 setting_file 指向 DB/ResearchDB/setting/ 裡的設定檔（固定值模式）。
hash = sha256(settings + expression)，由 src.alpha.Alpha 計算，建立 payload 時就有，不必等 worker。
已在 pending/running/complete/error 任一格的 hash 不重送。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

if os.getcwd() not in sys.path:          # 從 open machine 根目錄執行；讓 src.* 可 import
    sys.path.insert(0, os.getcwd())

from src.alpha import Alpha
from src.paths import AlphaPath, ResearchPath

try:
    from src.arc import is_arc_region, ARC_PAYLOAD_TYPE
except Exception:  # 舊版 open machine 沒有 arc
    def is_arc_region(_):
        return False
    ARC_PAYLOAD_TYPE = "REGION_AGNOSTIC"

IDEA_DIR = os.path.join(ResearchPath.ROOT, "idea")
QUEUES = {"pending": AlphaPath.PENDING, "running": AlphaPath.RUNNING,
          "complete": AlphaPath.COMPLETE, "error": AlphaPath.ERROR}
TZ = timezone(timedelta(hours=8))


def _resolve_idea(arg: str) -> str:
    if os.path.exists(arg):
        return arg
    name = arg if arg.endswith(".json") else arg + ".json"
    return os.path.join(IDEA_DIR, name)


def _load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize(exprs: list) -> list[dict]:
    out = []
    for i, e in enumerate(exprs, 1):
        if isinstance(e, str):
            out.append({"role": "user", "author": "user", "expr": e, "hash": None})
        elif isinstance(e, dict) and "expr" in e:
            d = dict(e); d.setdefault("role", "user"); d.setdefault("hash", None); out.append(d)
        else:
            raise SystemExit(f"expressions 第 {i} 項格式不對")
    return out


def _locate(name: str) -> str | None:
    for q, folder in QUEUES.items():
        if os.path.exists(os.path.join(folder, name)):
            return q
    return None


def _ledger(event: str, card_id: str, payload: dict) -> None:
    """有 agents/ 就記帳本，沒有就略過（idea.py 不依賴 agents）。"""
    try:
        sys.path.insert(0, os.getcwd())
        from agents.common import ledger  # type: ignore
        ledger.append("user", event, card_id, payload)
    except Exception:
        pass


def submit(idea_arg: str, roles: list[str] | None, dry: bool) -> int:
    idea_path = _resolve_idea(idea_arg)
    if not os.path.exists(idea_path):
        print(f"找不到 idea 檔：{idea_path}")
        return 1
    idea = _load_json(idea_path)
    setting_file = idea.get("setting_file")
    if not setting_file:
        print("idea 檔沒有 setting_file。請在 DB/ResearchDB/setting/ 建一個設定檔（可複製 default_setting.json）並填入 idea 檔的 setting_file。")
        return 1
    setting_path = os.path.join(ResearchPath.SETTING, setting_file)
    if not os.path.exists(setting_path):
        print(f"找不到 setting 檔：{setting_path}")
        return 1
    setting = _load_json(setting_path)
    lists = [k for k, v in setting.items() if isinstance(v, list)]
    if lists:
        print(f"setting 檔有陣列欄位 {lists}（優化模式）。單筆模擬需要固定值，請另存一份固定值的設定檔。")
        return 1

    exprs = _normalize(idea.get("expressions", []))
    idea["expressions"] = exprs
    card_id = idea.get("card_id", os.path.splitext(os.path.basename(idea_path))[0])
    ptype = ARC_PAYLOAD_TYPE if is_arc_region(setting.get("region")) else "REGULAR"
    print(f"[idea] {card_id}  setting={setting_file}  type={ptype}  "
          f"{setting.get('region')}/{setting.get('universe')}/d{setting.get('delay')}/{setting.get('neutralization')}")

    n_sent = n_skip = 0
    sent = []
    for i, e in enumerate(exprs, 1):
        if roles and e.get("role") not in roles:
            continue
        payload = {"type": ptype, "regular": e["expr"], "settings": setting}
        alpha = Alpha(payload=payload)
        name = alpha.get_name()
        where = _locate(name)
        e["hash"] = name
        if where:
            print(f"  #{i} {e.get('role', ''):8s} 已在 {where}/ → 不重送  {name[:12]}…")
            n_skip += 1
            continue
        if dry:
            print(f"  #{i} {e.get('role', ''):8s} (dry) hash={name[:12]}…")
            continue
        os.makedirs(AlphaPath.PENDING, exist_ok=True)
        alpha.save(os.path.join(AlphaPath.PENDING, name))
        e["submitted_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        sent.append(name)
        n_sent += 1
        print(f"  #{i} {e.get('role', ''):8s} → pending  {name[:12]}…")

    if not dry:
        with open(idea_path, "w", encoding="utf-8") as f:
            json.dump(idea, f, ensure_ascii=False, indent=2)
        print(f"[write] hash 已寫回 {idea_path}")
        if sent:
            _ledger("hashes_linked", card_id, {"hashes": sent, "setting_file": setting_file})
    print(f"[done] 送出 {n_sent}、略過 {n_skip}。worker 跑完後：python -m src.idea --status {card_id}")
    return 0


def status(idea_arg: str) -> int:
    idea_path = _resolve_idea(idea_arg)
    if not os.path.exists(idea_path):
        print(f"找不到 idea 檔：{idea_path}")
        return 1
    idea = _load_json(idea_path)
    exprs = _normalize(idea.get("expressions", []))
    print(f"{'#':<3}{'role':<9}{'queue':<10}{'sharpe':>8}{'fitness':>9}{'turnover':>10}{'returns':>9}  checks(FAIL)")
    for i, e in enumerate(exprs, 1):
        h = e.get("hash")
        if not h:
            print(f"{i:<3}{e.get('role', ''):<9}{'未送出':<10}")
            continue
        where = _locate(h)
        if where != "complete":
            print(f"{i:<3}{e.get('role', ''):<9}{(where or '不在任何佇列'):<10}  {h[:12]}…")
            continue
        rec = _load_json(os.path.join(AlphaPath.COMPLETE, h))
        res = rec.get("result") or {}
        perf = res.get("is") or {}
        fails = [c["name"] for c in perf.get("checks", []) if c.get("result") == "FAIL"]
        print(f"{i:<3}{e.get('role', ''):<9}{'complete':<10}{perf.get('sharpe', float('nan')):>8}"
              f"{perf.get('fitness', float('nan')):>9}{perf.get('turnover', float('nan')):>10}"
              f"{perf.get('returns', float('nan')):>9}  {','.join(fails) or '-'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="idea → payload → pending")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--idea", help="卡號、idea 檔名或路徑：送 pending 並寫回 hash")
    g.add_argument("--status", help="卡號、idea 檔名或路徑：查每條 expression 的佇列與成績")
    ap.add_argument("--roles", default=None, help="逗號分隔，只送這些 role")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    if args.status:
        return status(args.status)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    return submit(args.idea, roles, args.dry)


if __name__ == "__main__":
    sys.exit(main())
