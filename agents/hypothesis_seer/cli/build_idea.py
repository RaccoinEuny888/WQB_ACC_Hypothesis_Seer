"""建 setting 檔 + idea 檔，並跑語法檢查。

  python agents/hypothesis_seer/cli/build_idea.py --card H-261115-003 \
      --region USA --universe TOP3000 --delay 1 --neutralization SUBINDUSTRY \
      --main "..." --naive "..." --falsify "..." --falsify-differs "資料源 P→Q" \
      [--notes design_notes.json] [--no-check]
  python agents/hypothesis_seer/cli/build_idea.py --card H-261115-003 --append-user "expr"   # 使用者自己寫的式子加進 idea
  python agents/hypothesis_seer/cli/build_idea.py --card H-261115-003 --revise --main "..."   # 修訂（版本 +1，保留 setting）

寫入：DB/ResearchDB/setting/<card>.json（從 default_setting.json 複製再覆蓋欄位）、DB/ResearchDB/idea/<card>.json。
不寫 payload、不碰 AlphaDB。送模擬是使用者執行 python -m src.idea --idea <card>。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agents.common import paths, idea_io, ledger  # noqa: E402

DEFAULT_SETTING = paths.OM.SETTING / "default_setting.json"
SETTING_KEYS = ("region", "universe", "delay", "neutralization", "decay", "truncation", "pasteurization",
                "nanHandling", "unitHandling", "maxTrade", "maxPosition", "testPeriod")


def _read_expr(v: str | None) -> str | None:
    if v is None:
        return None
    p = Path(v)
    if v.endswith((".txt", ".expr")) and p.exists():
        return p.read_text(encoding="utf-8").strip()
    return v.strip()


def build_setting(card: str, overrides: dict) -> Path:
    base = {}
    if DEFAULT_SETTING.exists():
        with open(DEFAULT_SETTING, "r", encoding="utf-8") as f:
            base = json.load(f)
    base.update({k: v for k, v in overrides.items() if v is not None})
    base["language"] = "FASTEXPR"
    base.setdefault("instrumentType", "EQUITY")
    lists = [k for k, v in base.items() if isinstance(v, list)]
    if lists:
        raise SystemExit(f"default_setting.json 有陣列欄位 {lists}，單筆模擬需固定值；請用參數覆蓋或改 default_setting.json")
    out = paths.OUT.SETTING / f"{card}.json"
    paths.ensure_parent(out)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="建 setting + idea")
    ap.add_argument("--card", required=True)
    for k in SETTING_KEYS:
        ap.add_argument(f"--{k}", default=None)
    ap.add_argument("--main"); ap.add_argument("--naive"); ap.add_argument("--falsify")
    ap.add_argument("--falsify-differs", default=None, help="反向證偽組與 main 只差的那一個變數")
    ap.add_argument("--author", default="seer", choices=["seer", "user"])
    ap.add_argument("--notes", default=None, help="design_notes JSON 檔（審判官看不到）")
    ap.add_argument("--append-user", default=None, help="把使用者自己寫的 expression 加進既有 idea")
    ap.add_argument("--revise", action="store_true", help="修訂既有 idea（版本 +1，setting 沿用）")
    ap.add_argument("--no-check", action="store_true")
    args = ap.parse_args()

    card = args.card
    idea_p = paths.idea_path(card)

    # ---- 追加使用者式子
    if args.append_user:
        _, idea = idea_io.load_idea(card)
        idea["expressions"].append({"role": "user", "author": "user", "expr": _read_expr(args.append_user), "hash": None})
        idea_io.save_idea(idea_p, idea)
        ledger.append("user", "idea_written", card, {"roles": ["user"], "append": True}, [paths.rel(idea_p)])
        print(f"[idea] 已追加 role=user → {paths.rel(idea_p)}")
    else:
        exprs = []
        for role, raw in (("main", args.main), ("naive", args.naive), ("falsify", args.falsify)):
            e = _read_expr(raw)
            if e:
                d = {"role": role, "author": args.author, "expr": e, "hash": None}
                if role == "falsify" and args.falsify_differs:
                    d["differs_only_in"] = args.falsify_differs
                exprs.append(d)
        if not exprs:
            ap.error("至少要給 --main（或 --append-user）")
        if args.revise and idea_p.exists():
            _, old = idea_io.load_idea(card)
            version = int(old.get("version", 1)) + 1
            setting_file = old.get("setting_file")
            keep_user = [e for e in old["expressions"] if e.get("role") == "user"]
        else:
            version, setting_file, keep_user = 1, None, []
        if setting_file is None or any(getattr(args, k) is not None for k in SETTING_KEYS):
            over = {k: getattr(args, k) for k in SETTING_KEYS}
            if over.get("delay") is not None:
                over["delay"] = int(over["delay"])
            for k in ("decay",):
                if over.get(k) is not None:
                    over[k] = int(over[k])
            for k in ("truncation",):
                if over.get(k) is not None:
                    over[k] = float(over[k])
            sp = build_setting(card, over)
            setting_file = sp.name
            print(f"[setting] {paths.rel(sp)}")
        notes = None
        if args.notes:
            with open(args.notes, "r", encoding="utf-8") as f:
                notes = json.load(f)
        idea = {"card_id": card, "version": version, "setting_file": setting_file,
                "expressions": exprs + keep_user, "design_notes": notes or {}}
        idea_io.save_idea(idea_p, idea)
        ledger.append(args.author, "idea_written", card,
                      {"roles": [e["role"] for e in exprs], "version": version, "setting_file": setting_file}, [paths.rel(idea_p)])
        print(f"[idea] v{version} {len(exprs)} 條 → {paths.rel(idea_p)}")

    if args.no_check:
        return 0
    print("\n[syntax_check]", flush=True)
    r = subprocess.run([sys.executable, str(paths.COMMON / "syntax_check.py"), "-i", card], cwd=paths.ROOT)
    ledger.append(args.author, "syntax_checked", card, {"pass": r.returncode == 0})
    if r.returncode == 0:
        print(f"\n下一步（由使用者執行）：python -m src.idea --idea {card}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
