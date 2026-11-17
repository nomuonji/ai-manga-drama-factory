#!/usr/bin/env python3
"""ガチャ工場: 動画AIにゆるく頼んで何本も作らせ、当たりを選び、当たりやすい条件を学ぶ。

なぜこうするか（docs/gacha.md）:
  『なんかわけのわからない動画作って』で面白い動画が出るとき、面白さの大部分は
  動画AI自身（テレビCMの型を覚えていて、絵・声・テロップを一度に出す）と、
  何本も作って当たりを選ぶことから来ている。エージェントが中身を書き込むほど
  説明的・狙いすぎになって外れる。だからエージェントの仕事は
    1) 引き出し方（型・指示のゆるさ・モデル）を変えて何本も作らせる
    2) 見られる形（コマ送り＋文字起こし）にして人に選んでもらう
    3) どの条件から当たりが出たかを記録し、次は当たりやすい条件に多く賭ける
  の3つ。

Usage
  python3 tools/gacha/gacha.py plan  [--n 8] [--budget 15]        # 何を作るか決める（お金はかからない）
  python3 tools/gacha/gacha.py run   <batch-id>                    # 生成（FAL_KEY、有料）
  python3 tools/gacha/gacha.py review <batch-id>                   # コマ送り・文字起こし・一覧ページ
  python3 tools/gacha/gacha.py rate  <batch-id> <c01> pass|partial|fail "本人の言葉"
  python3 tools/gacha/gacha.py stats                               # 型・モデル・書き方ごとの当たり率

batch は gacha/<batch-id>/batch.json（git 管理）。動画は outputs/gacha/<batch-id>/（git 管理外）。
評価は gacha/ratings.jsonl に追記され、stats と次の plan の配分に使われる。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import random
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAT = ROOT / "catalog" / "gacha-formats.json"
BATCHES = ROOT / "gacha"
RATINGS = BATCHES / "ratings.jsonl"
OUT = ROOT / "outputs" / "gacha"

# alias: (fal endpoint, approx $/s with audio, max seconds, how to pass duration)
MODELS = {
    "sora-2": ("fal-ai/sora-2/text-to-video", 0.10, 12, "int"),
    "seedance-2-fast": ("bytedance/seedance-2.0/fast/text-to-video", 0.24, 15, "str"),
    "seedance-2": ("bytedance/seedance-2.0/text-to-video", 0.31, 15, "str"),
    "veo-3.1-fast": ("fal-ai/veo3.1/fast", 0.15, 8, "veo"),
}
DEFAULT_MODELS = ["sora-2", "seedance-2-fast"]


def catalog():
    return json.loads(CAT.read_text(encoding="utf-8"))


def ratings():
    if not RATINGS.exists():
        return []
    return [json.loads(l) for l in RATINGS.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- learning which conditions hit

def arm_stats():
    """pass=1, partial=0.5, fail=0 per (format, style, model). Beta(1,1) prior."""
    st = {}
    for r in ratings():
        k = (r["format"], r["style"], r["model"])
        a, b = st.get(k, (1.0, 1.0))
        v = {"pass": 1.0, "partial": 0.5, "fail": 0.0}[r["verdict"]]
        st[k] = (a + v, b + 1 - v)
    return st


def plan(n: int, budget: float, models: list[str], seconds: int, aspect: str, seed: int | None):
    """Thompson sampling over (format, style, model): rated-good arms get more draws, untried arms still get tried."""
    cat = catalog()
    rng = random.Random(seed)
    st = arm_stats()
    arms = [(f["id"], s, m) for f in cat["formats"] for s in f["styles"] for m in models]
    picks = []
    # 参考事例と同じ『完全おまかせ』は、評価が溜まるまで毎回1本は必ず入れる（比べる基準になる）
    free_arms = [k for k in arms if k[0] == "free"]
    if free_arms and sum(1 for k in st if k[0] == "free") < 3:
        picks.append(rng.choice(free_arms))
    while len(picks) < n:
        best = max(arms, key=lambda k: rng.betavariate(*st.get(k, (1.0, 1.0))) + rng.random() * 1e-6)
        picks.append(best)
    fmts = {f["id"]: f for f in cat["formats"]}
    cands, cost = [], 0.0
    for i, (fid, style, model) in enumerate(picks, 1):
        f = fmts[fid]
        secs = min(seconds, MODELS[model][2])
        text = f["prompt"]
        if style == "seeded":
            text += f" 具材: {rng.choice(cat['ingredients']['things'])}、{rng.choice(cat['ingredients']['places'])}。"
        if style in ("format", "seeded"):
            text += f" 長さ{secs}秒、カットを何回か切り替える、日本語の声とテロップ。"
        text += " " + cat["guardrails"]
        c = round(secs * MODELS[model][1], 2)
        if cost + c > budget:
            break
        cost += c
        cands.append({"id": f"c{i:02d}", "format": fid, "style": style, "model": model, "seconds": secs,
                      "aspect": aspect, "prompt": text, "est_cost": c})
    bid = dt.datetime.now().strftime("%Y%m%d-%H%M")
    d = BATCHES / bid
    d.mkdir(parents=True, exist_ok=True)
    batch = {"id": bid, "created": dt.datetime.now().isoformat(timespec="seconds"), "budget": budget,
             "est_cost": round(cost, 2), "candidates": cands}
    (d / "batch.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"batch {bid}: {len(cands)} candidates, est ${cost:.2f} (budget ${budget})")
    for c in cands:
        print(f"  {c['id']} {c['model']:<16} {c['format']:<14} {c['style']:<7} {c['seconds']}s ${c['est_cost']}")
    return bid


# ---------------------------------------------------------------- generation (fal queue API)

def fal(endpoint, payload):
    key = os.environ.get("FAL_KEY")
    if not key:
        raise SystemExit("FAL_KEY is not set (put it in GitHub Secrets and use the Gacha workflow)")
    hdr = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"https://queue.fal.run/{endpoint}", data=json.dumps(payload).encode(), headers=hdr, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        sub = json.load(r)
    t0 = time.time()
    while True:
        time.sleep(8)
        with urllib.request.urlopen(urllib.request.Request(sub["status_url"], headers=hdr), timeout=60) as r:
            s = json.load(r)
        if s.get("status") == "COMPLETED":
            break
        if s.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 1500:
            raise RuntimeError(f"fal: {s}")
    with urllib.request.urlopen(urllib.request.Request(sub["response_url"], headers=hdr), timeout=120) as r:
        return json.load(r)


def payload_for(c):
    ep, _, _, dur = MODELS[c["model"]]
    p = {"prompt": c["prompt"], "aspect_ratio": c["aspect"]}
    if dur == "int":
        p["duration"] = c["seconds"]
    elif dur == "str":
        p["duration"] = str(c["seconds"])
        p["generate_audio"] = True
    elif dur == "veo":
        p["duration"] = f"{min(8, c['seconds'])}s"
        p["generate_audio"] = True
    return ep, p


def run(bid):
    batch = json.loads((BATCHES / bid / "batch.json").read_text(encoding="utf-8"))
    out = OUT / bid
    out.mkdir(parents=True, exist_ok=True)
    failed = []
    for c in batch["candidates"]:
        mp4 = out / f"{c['id']}.mp4"
        if mp4.exists():
            continue
        ep, p = payload_for(c)
        print("generate", c["id"], ep)
        try:
            res = fal(ep, p)
            url = (res.get("video") or {}).get("url")
            urllib.request.urlretrieve(url, mp4)
        except Exception as e:  # noqa: BLE001  one failure must not waste the rest of the batch
            print("  failed:", e)
            failed.append(c["id"])
    print(f"done. failed: {failed or 'none'}")


# ---------------------------------------------------------------- review pack (so an agent that cannot watch can still read it)

def review(bid):
    import base64
    batch = json.loads((BATCHES / bid / "batch.json").read_text(encoding="utf-8"))
    out = OUT / bid
    rows = []
    try:
        from faster_whisper import WhisperModel  # optional: transcript of the audio
        wm = WhisperModel("small", device="cpu", compute_type="int8")
    except Exception:  # noqa: BLE001
        wm = None
    for c in batch["candidates"]:
        mp4 = out / f"{c['id']}.mp4"
        if not mp4.exists():
            continue
        sheet = out / f"{c['id']}-sheet.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                        "fps=1,scale=320:-1,tile=8x2:padding=4:color=black", "-frames:v", "1", str(sheet)], check=True)
        text = ""
        if wm:
            segs, _ = wm.transcribe(str(mp4), language="ja")
            text = " / ".join(s.text.strip() for s in segs)
            (out / f"{c['id']}.txt").write_text(text, encoding="utf-8")
        rows.append((c, sheet, text))
    html = ["<meta charset=utf-8><title>gacha " + bid + "</title><style>body{font-family:sans-serif;background:#111;color:#eee}"
            "video{max-width:420px;max-height:420px}div.c{display:flex;gap:16px;margin:24px 0;border-bottom:1px solid #333;padding-bottom:16px}"
            "code{color:#9cf}</style><h1>ガチャ " + bid + "</h1><p>良い／ボツを一言で。<code>gacha.py rate " + bid + " c01 pass \"…\"</code></p>"]
    for c, sheet, text in rows:
        html.append(f"<div class=c><video controls src='{c['id']}.mp4'></video><div><h2>{c['id']}</h2>"
                    f"<p>{c['model']} / {c['format']} / {c['style']} / {c['seconds']}s</p><p><b>声:</b> {text or '（文字起こしなし）'}</p>"
                    f"<img src='{sheet.name}' width=640><details><summary>prompt</summary>{c['prompt']}</details></div></div>")
    (out / "index.html").write_text("\n".join(html), encoding="utf-8")
    print("review pack:", out / "index.html")


# ---------------------------------------------------------------- rating & stats

def rate(bid, cid, verdict, words):
    assert verdict in ("pass", "partial", "fail"), "verdict: pass | partial | fail"
    batch = json.loads((BATCHES / bid / "batch.json").read_text(encoding="utf-8"))
    c = next(x for x in batch["candidates"] if x["id"] == cid)
    rec = {"at": dt.datetime.now().isoformat(timespec="seconds"), "batch": bid, "id": cid, "verdict": verdict,
           "words": words, "format": c["format"], "style": c["style"], "model": c["model"]}
    with RATINGS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("recorded", rec)


def stats():
    rs = ratings()
    if not rs:
        print("no ratings yet")
        return
    for key in ("format", "style", "model"):
        agg = {}
        for r in rs:
            a = agg.setdefault(r[key], [0, 0.0])
            a[0] += 1
            a[1] += {"pass": 1, "partial": 0.5, "fail": 0}[r["verdict"]]
        print(f"\n[{key}]")
        for k, (n, s) in sorted(agg.items(), key=lambda x: -x[1][1] / x[1][0]):
            print(f"  {k:<18} {s / n:5.0%}  ({n})")


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "plan":
        opts = {"--n": "8", "--budget": "15", "--seconds": "12", "--aspect": "9:16", "--models": ",".join(DEFAULT_MODELS), "--seed": ""}
        for i in range(1, len(a), 2):
            opts[a[i]] = a[i + 1]
        plan(int(opts["--n"]), float(opts["--budget"]), opts["--models"].split(","), int(opts["--seconds"]),
             opts["--aspect"], int(opts["--seed"]) if opts["--seed"] else None)
    elif cmd == "run":
        run(a[1])
    elif cmd == "review":
        review(a[1])
    elif cmd == "rate":
        rate(a[1], a[2], a[3], a[4] if len(a) > 4 else "")
    elif cmd == "stats":
        stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
