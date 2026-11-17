#!/usr/bin/env python3
"""AI drama short: brief -> character sheets -> keyframe stills -> image-to-video clips -> subtitled vertical video.

The look this reproduces: a photoreal vertical "short drama" ad (TikTok / Instagram
story ads) — consistent actors across 3–8 s shots, spoken lines, big centred white
subtitles, a final CTA card.

Pipeline
  1. characters  Gemini image model makes one reference sheet per actor (or use your own photo).
  2. keyframes   Gemini makes the first frame of every shot WITH the actor references -> faces stay consistent.
  3. clips       fal.ai image-to-video (default Seedance 2.0; Kling / MiniMax / Veo selectable) animates each keyframe.
                 With native_audio the model also speaks the line; otherwise VOICEVOX voices are mixed in.
  4. assemble    crop to 1080x1920, burn subtitles, concat, BGM, CTA card.

Usage
  python tools/drama/drama.py check      productions/<id>/drama.json
  python tools/drama/drama.py cost       productions/<id>/drama.json    # estimate before spending
  python tools/drama/drama.py keyframes  productions/<id>/drama.json    # GEMINI_API_KEY   (~$0.04/image)
  python tools/drama/drama.py clips      productions/<id>/drama.json    # FAL_KEY          (paid per second)
  python tools/drama/drama.py voices     productions/<id>/drama.json    # VOICEVOX (only when native_audio is false)
  python tools/drama/drama.py assemble   productions/<id>/drama.json
  python tools/drama/drama.py stills     productions/<id>/drama.json    # cheap preview: keyframes + subtitles as a slideshow

Review keyframes (outputs/drama/<id>/keyframes/) BEFORE running `clips` — that is the
expensive step, and a bad still only becomes a bad clip.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "manga"))
import manga as M  # noqa: E402  (shared Gemini, VOICEVOX and font helpers)

from PIL import Image, ImageDraw  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H, FPS = 1080, 1920, 30

MODELS = {
    # alias: (fal endpoint, $ per output second (approx., check fal pricing), supports native audio)
    "seedance-2": ("bytedance/seedance-2.0/image-to-video", 0.30, True),
    "seedance-2-fast": ("bytedance/seedance-2.0/fast/image-to-video", 0.15, True),
    "seedance-1-pro": ("fal-ai/bytedance/seedance/v1/pro/image-to-video", 0.12, False),
    "kling-2.1": ("fal-ai/kling-video/v2.1/standard/image-to-video", 0.06, False),
    "minimax-hailuo-02": ("fal-ai/minimax/hailuo-02/standard/image-to-video", 0.045, False),
    "veo-3.1-fast": ("fal-ai/veo3.1/fast/image-to-video", 0.15, True),
}


def load(path):
    p = pathlib.Path(path)
    b = json.loads(p.read_text(encoding="utf-8"))
    b.setdefault("id", p.parent.name)
    b["_dir"] = str(p.parent)
    b["_out"] = str(ROOT / "outputs" / "drama" / b["id"])
    b.setdefault("style", "photo-drama")
    return b


STYLE = ("A vertical 9:16 cinematic film still from a Japanese short drama, shot on a full-frame camera, "
         "realistic Japanese actors, natural skin texture, soft practical lighting, shallow depth of field. "
         "No text, captions, logos or watermarks.")


def model(b):
    alias = b.get("model", "seedance-2-fast")
    if alias in MODELS:
        return MODELS[alias]
    return (alias, b.get("price_per_second", 0.3), b.get("native_audio", False))


def check(b):
    errs = []
    cast = {c["id"] for c in b.get("characters", [])}
    for i, s in enumerate(b["shots"]):
        s.setdefault("id", f"s{i + 1:02d}")
        for c in s.get("cast", []):
            if c not in cast:
                errs.append(f"{s['id']}: unknown character {c}")
        if not s.get("frame"):
            errs.append(f"{s['id']}: needs 'frame' (what the first frame shows)")
        if not s.get("motion"):
            errs.append(f"{s['id']}: needs 'motion' (what moves / is said in the clip)")
        if len(s.get("sub", "").replace("\n", "")) > 30:
            print(f"WARN {s['id']}: subtitle long — split the shot")
    for e in errs:
        print("ERROR", e)
    return errs


def cost(b):
    ep, pps, _ = model(b)
    secs = sum(s.get("seconds", 5) for s in b["shots"])
    imgs = len(b["shots"]) + len(b.get("characters", []))
    print(f"model {ep}: {len(b['shots'])} shots, {secs}s of video ≈ ${secs * pps:.2f}  "
          f"+ {imgs} images ≈ ${imgs * 0.04:.2f}  (approximate — check current fal / Gemini pricing)")


def char_sheet(b, c):
    return pathlib.Path(b["_out"]) / "characters" / f"{c['id']}.png"


def gen_characters(b):
    for c in b.get("characters", []):
        out = char_sheet(b, c)
        out.parent.mkdir(parents=True, exist_ok=True)
        if c.get("image"):
            Image.open(pathlib.Path(b["_dir"]) / c["image"]).convert("RGB").save(out)
            continue
        if out.exists():
            continue
        print("character", c["id"])
        out.write_bytes(M.gemini_image(
            f"{STYLE} Casting reference photo: {c['look']}. Same person twice side by side, front and three-quarter view, "
            "upper body, plain light-grey studio background, neutral expression.", [], "3:2"))


def frame_prompt(b, s):
    cast = {c["id"]: c for c in b.get("characters", [])}
    who = "; ".join(f"{cast[c]['name']} = the person in reference image {i + 1} ({cast[c]['look']})"
                    for i, c in enumerate(s.get("cast", [])))
    return (f"{STYLE} {('Location: ' + b['setting'] + '.') if b.get('setting') else ''} "
            f"Shot: {s['frame']}. {('Camera: ' + s['camera'] + '.') if s.get('camera') else ''} "
            f"{('Actors: ' + who + '. Keep faces, hair and wardrobe identical to the references.') if who else ''}")


def key_path(b, s):
    h = hashlib.sha1((frame_prompt(b, s) + M.GEMINI_MODEL).encode()).hexdigest()[:10]
    return pathlib.Path(b["_out"]) / "keyframes" / f"{s['id']}-{h}.png"


def gen_keyframes(b):
    gen_characters(b)
    cast = {c["id"]: c for c in b.get("characters", [])}
    for s in b["shots"]:
        out = key_path(b, s)
        if s.get("image") or out.exists():
            continue
        print("keyframe", s["id"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(M.gemini_image(frame_prompt(b, s), [char_sheet(b, cast[c]) for c in s.get("cast", [])], "9:16"))


def keyframe(b, s):
    return pathlib.Path(b["_dir"]) / s["image"] if s.get("image") else key_path(b, s)


def clip_path(b, s):
    ep, _, _ = model(b)
    h = hashlib.sha1(json.dumps([key_path(b, s).name, s["motion"], s.get("line"), s.get("seconds", 5), ep],
                                ensure_ascii=False).encode()).hexdigest()[:10]
    return pathlib.Path(b["_out"]) / "clips" / f"{s['id']}-{h}.mp4"


def motion_prompt(b, s):
    _, _, native = model(b)
    p = s["motion"]
    if native and b.get("native_audio", True) and s.get("line"):
        cast = {c["id"]: c for c in b.get("characters", [])}
        sp = cast.get(s.get("speaker"), {}).get("name", "the character")
        p += f' {sp} says in natural Japanese: "{s["line"]}"'
    return p + " Realistic motion, consistent face, no text on screen."


def fal_run(endpoint: str, payload: dict) -> dict:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise SystemExit("FAL_KEY is not set")
    hdr = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"https://queue.fal.run/{endpoint}", data=json.dumps(payload).encode(),
                                 headers=hdr, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        sub = json.load(r)
    status_url, resp_url = sub["status_url"], sub["response_url"]
    t0 = time.time()
    while True:
        time.sleep(6)
        with urllib.request.urlopen(urllib.request.Request(status_url, headers=hdr), timeout=60) as r:
            st = json.load(r)
        if st.get("status") == "COMPLETED":
            break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 1200:
            raise RuntimeError(f"fal job failed/timed out: {st}")
    with urllib.request.urlopen(urllib.request.Request(resp_url, headers=hdr), timeout=120) as r:
        return json.load(r)


def gen_clips(b):
    ep, _, native = model(b)
    for s in b["shots"]:
        out = clip_path(b, s)
        if out.exists():
            continue
        kf = keyframe(b, s)
        if not kf.exists():
            raise SystemExit(f"missing keyframe for {s['id']} — run keyframes first")
        payload = {"prompt": motion_prompt(b, s),
                   "image_url": "data:image/png;base64," + base64.b64encode(kf.read_bytes()).decode(),
                   "duration": str(s.get("seconds", 5))}
        payload.update(b.get("model_params", {}))
        if native:
            payload.setdefault("generate_audio", bool(b.get("native_audio", True)))
        print("clip", s["id"], ep)
        res = fal_run(ep, payload)
        url = (res.get("video") or {}).get("url") or res.get("video_url")
        if not url:
            raise RuntimeError(f"no video url in {json.dumps(res)[:300]}")
        out.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, out)


# ---------------------------------------------------------------- voices (when the video model is silent)

def wants_tts(b):
    _, _, native = model(b)
    return not (native and b.get("native_audio", True))


def line_voice(b, s):
    cast = {c["id"]: c for c in b.get("characters", [])}
    if s.get("speaker") in cast:
        return cast[s["speaker"]].get("voice")
    return b.get("narrator")


def voice_file(b, s):
    h = hashlib.sha1(json.dumps([s.get("line"), line_voice(b, s)], ensure_ascii=False).encode()).hexdigest()[:10]
    return pathlib.Path(b["_out"]) / "voices" / f"{h}.wav"


def gen_voices(b):
    if not wants_tts(b):
        print("model speaks the lines natively; skipping VOICEVOX")
        return
    for s in b["shots"]:
        if not s.get("line") or not line_voice(b, s):
            continue
        fake = {"text": s["line"], "say": s["line"]}
        brief = {"characters": [], "narrator": line_voice(b, s), "_out": b["_out"]}
        out = voice_file(b, s)
        if out.exists():
            continue
        M.gen_voices({**brief, "pages": [{"rows": [{"layout": "full", "panels": [{"id": "x", "bubbles": [fake]}]}]}]})
        src = M.voice_path(brief, fake)
        src.rename(out)


# ---------------------------------------------------------------- assemble

def subtitle_png(text: str, path: pathlib.Path):
    font = M.jp_font(58, bold=True)
    img = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.multiline_text((W // 2, 210), text, font=font, fill=(255, 255, 255), anchor="mm", align="center",
                     spacing=18, stroke_width=6, stroke_fill=(0, 0, 0))
    img.save(path)


def cta_png(b, path: pathlib.Path):
    img = Image.new("RGB", (W, H), (15, 15, 18))
    d = ImageDraw.Draw(img)
    c = b.get("cta", {})
    d.multiline_text((W // 2, H // 2 - 120), c.get("headline", ""), font=M.jp_font(72, True), fill=(255, 255, 255),
                     anchor="mm", align="center", spacing=20)
    d.rounded_rectangle((W // 2 - 330, H // 2 + 80, W // 2 + 330, H // 2 + 220), radius=70, fill=(255, 214, 0))
    d.text((W // 2, H // 2 + 150), c.get("button", "詳しくはこちら"), font=M.jp_font(56, True), fill=(20, 20, 20), anchor="mm")
    img.save(path)


def assemble(b, stills_only=False):
    out = pathlib.Path(b["_out"])
    tmp = out / "parts"
    tmp.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, s in enumerate(b["shots"]):
        sub = tmp / f"{s['id']}-sub.png"
        subtitle_png(s.get("sub", s.get("line", "")), sub)
        part = tmp / f"{i:03d}.mp4"
        secs = s.get("seconds", 5)
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[bg];"
              f"[bg][1:v]overlay=0:{int(H * b.get('subtitle_y', 0.58))}")
        if stills_only or not clip_path(b, s).exists():
            src = ["-loop", "1", "-t", str(secs), "-i", str(keyframe(b, s))]
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"zoompan=z='min(zoom+0.0008,1.08)':d={int(secs * FPS)}:s={W}x{H}:fps={FPS},setsar=1[bg];"
                  f"[bg][1:v]overlay=0:{int(H * b.get('subtitle_y', 0.58))}")
            audio = ["-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo"]
            amap = "2:a"
        else:
            src = ["-i", str(clip_path(b, s))]
            audio = []
            amap = "0:a?"
        vfile = voice_file(b, s)
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + src + ["-i", str(sub)] + audio
        if wants_tts(b) and vfile.exists():
            cmd += ["-i", str(vfile)]
            amap = f"{len([x for x in cmd if x == '-i']) - 1}:a"
        cmd += ["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", amap, "-t", str(secs),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", str(part)]
        subprocess.run(cmd, check=True)
        # guarantee an audio stream for concat
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                "-of", "csv=p=0", str(part)], capture_output=True, text=True).stdout.strip()
        if not probe:
            fixed = tmp / f"{i:03d}a.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(part), "-f", "lavfi", "-i",
                            "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "copy", "-c:a", "aac", str(fixed)], check=True)
            part = fixed
        parts.append(part)
    if b.get("cta"):
        cta = tmp / "cta.png"
        cta_png(b, cta)
        part = tmp / "zz-cta.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(b["cta"].get("seconds", 2.5)),
                        "-i", str(cta), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                        "-vf", f"fps={FPS},setsar=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
                        str(part)], check=True)
        parts.append(part)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    joined = tmp / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", str(joined)], check=True)
    final = out / ("preview-stills.mp4" if stills_only else "video.mp4")
    bgm = b.get("bgm")
    if bgm and (ROOT / bgm).exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(ROOT / bgm),
                        "-filter_complex", f"[1:a]volume={b.get('bgm_volume', 0.08)}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,"
                        "loudnorm=I=-15:TP=-1.5[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(final)], check=True)
    else:
        joined.replace(final)
    print("wrote", final)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, b = sys.argv[1], load(sys.argv[2])
    if check(b):
        sys.exit("fix the errors above")
    {"check": lambda: (cost(b), print("ok")),
     "cost": lambda: cost(b),
     "keyframes": lambda: gen_keyframes(b),
     "clips": lambda: (cost(b), gen_clips(b)),
     "voices": lambda: gen_voices(b),
     "assemble": lambda: assemble(b),
     "stills": lambda: (gen_voices(b) if os.environ.get("VOICEVOX_URL") else None, assemble(b, stills_only=True)),
     }.get(cmd, lambda: sys.exit(f"unknown command {cmd}"))()


if __name__ == "__main__":
    main()
