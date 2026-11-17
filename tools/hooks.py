#!/usr/bin/env python3
"""Hook catalog helper.

  python3 tools/hooks.py                 # list every hook type
  python3 tools/hooks.py show <id>       # one hook in full
  python3 tools/hooks.py check           # validate catalog/hooks.json (CI runs this)
  python3 tools/hooks.py for <format>    # hooks usable for manga / drama
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "hooks.json"
REQUIRED = ["id", "name", "mechanism", "first_frame", "formats", "placement", "evidence", "sources"]


def load():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def ids():
    return {h["id"] for h in load()["hooks"]}


def check() -> int:
    data = load()
    errs = 0
    seen = set()
    for h in data["hooks"]:
        for k in REQUIRED:
            if not h.get(k):
                print(f"ERROR {h.get('id', '?')}: missing {k}")
                errs += 1
        if h.get("id") in seen:
            print(f"ERROR duplicate id {h['id']}")
            errs += 1
        seen.add(h.get("id"))
        if h.get("evidence") not in data["evidence_levels"]:
            print(f"ERROR {h['id']}: evidence must be one of {list(data['evidence_levels'])}")
            errs += 1
        for f in h.get("formats", []):
            if f not in ("manga", "drama"):
                print(f"ERROR {h['id']}: unknown format {f}")
                errs += 1
        for s in h.get("sources", []):
            if not s.startswith("http") and not (ROOT / s).exists():
                print(f"ERROR {h['id']}: source path not found: {s}")
                errs += 1
    print(f"{len(data['hooks'])} hooks, {errs} errors")
    return errs


def main():
    a = sys.argv[1:]
    data = load()
    if not a or a[0] == "for":
        fmt = a[1] if len(a) > 1 else None
        for h in data["hooks"]:
            if fmt and fmt not in h["formats"]:
                continue
            print(f"{h['id']:<18} [{h['evidence']:<10}] {h['name']} — {h['mechanism'][:50]}…")
    elif a[0] == "show":
        h = next((x for x in data["hooks"] if x["id"] == a[1]), None)
        print(json.dumps(h, ensure_ascii=False, indent=2) if h else f"no hook {a[1]}")
    elif a[0] == "check":
        sys.exit(1 if check() else 0)


if __name__ == "__main__":
    main()
