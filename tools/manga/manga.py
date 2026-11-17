#!/usr/bin/env python3
"""AI manga short: brief -> character sheets -> panel images -> voices -> animated vertical video.

The look this reproduces: a white vertical page, manga panels revealed one by one,
hand-placed speech bubbles (vertical Japanese text), katakana sound effects, a
page turn, and a "▼このあと…▼" teaser bar. Images are generated WITHOUT text;
all Japanese text is drawn here so it is always legible and correct.

Usage
  python tools/manga/manga.py check   productions/<id>/manga.json
  python tools/manga/manga.py inspect productions/<id>/manga.json   # layout checks + outputs/.../inspect/page-N.png
  python tools/manga/manga.py images  productions/<id>/manga.json   # needs GEMINI_API_KEY
  python tools/manga/manga.py voices  productions/<id>/manga.json   # needs VOICEVOX at $VOICEVOX_URL
  python tools/manga/manga.py render  productions/<id>/manga.json   # needs ffmpeg
  python tools/manga/manga.py panels  productions/<id>/manga.json [dir]  # each panel + its bubbles as .webp (web pages)
  python tools/manga/manga.py all     productions/<id>/manga.json
  python tools/manga/manga.py placeholders productions/<id>/manga.json  # stand-in panels, no API

Outputs go to outputs/manga/<id>/ (panels/, voices/, video.mp4, contact-sheet.jpg,
first-frame-phone.png, timeline.json). Generated panels are cached by prompt hash, so
re-running only regenerates what changed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------- brief


def load(path: str) -> dict:
    p = pathlib.Path(path)
    brief = json.loads(p.read_text(encoding="utf-8"))
    brief.setdefault("id", p.parent.name)
    brief["_dir"] = str(p.parent)
    brief["_out"] = str(ROOT / "outputs" / "manga" / brief["id"])
    return brief


LAYOUTS = {
    # name: list of (x, y, w, h) in a 0..1 row box, row height given per row
    "full": [(0, 0, 1, 1)],
    "split": [(0, 0, 0.5, 1), (0.5, 0, 0.5, 1)],
    "split-wide-left": [(0, 0, 0.62, 1), (0.62, 0, 0.38, 1)],
    "split-wide-right": [(0, 0, 0.38, 1), (0.38, 0, 0.62, 1)],
    "three": [(0, 0, 1 / 3, 1), (1 / 3, 0, 1 / 3, 1), (2 / 3, 0, 1 / 3, 1)],
}
# Phone-UI safe zones (YouTube Shorts / TikTok / Reels, 9:16):
#   top 4% search/tabs, bottom 18% title/caption, right 14% of the lower half = like/comment/share buttons.
# Panels live in y 0.06-0.76, the teaser bar in 0.77-0.82, nothing important below 0.82.
PAGE_TOP, PAGE_BOTTOM, MARGIN, GUTTER = 115, 1460, 36, 16
SAFE_BOTTOM, SAFE_RIGHT_X, SAFE_RIGHT_FROM_Y, SAFE_TOP = int(0.82 * 1920), int(0.86 * 1080), int(0.5 * 1920), int(0.04 * 1920)


def page_rects(page: dict) -> list[tuple[int, int, int, int]]:
    """Pixel rect for every panel on a page, in order."""
    rows = page["rows"]
    weights = [r.get("height", 1.0) for r in rows]
    avail = PAGE_BOTTOM - PAGE_TOP - GUTTER * (len(rows) - 1)
    y = PAGE_TOP
    rects = []
    for r, wt in zip(rows, weights):
        rh = int(avail * wt / sum(weights))
        for (fx, fy, fw, fh) in LAYOUTS[r.get("layout", "full")]:
            x0 = MARGIN + int(fx * (W - 2 * MARGIN))
            x1 = MARGIN + int((fx + fw) * (W - 2 * MARGIN))
            if fx > 0:
                x0 += GUTTER // 2
            if fx + fw < 0.999:
                x1 -= GUTTER // 2
            rects.append((x0, y, x1 - x0, rh))
        y += rh + GUTTER
    return rects


def panels(brief: dict):
    """Yield (page_index, panel_index_on_page, panel, rect)."""
    for pi, page in enumerate(brief["pages"]):
        rects = page_rects(page)
        # Panels are written in READING ORDER and revealed in that order.
        # reading "ltr" (default): left -> right, like web/ad manga.  "rtl": right -> left, like Japanese print manga.
        flat = [p for r in page["rows"] for p in r["panels"]]
        if brief.get("reading", "ltr") == "rtl":
            order, i = [], 0
            for r in page["rows"]:
                n = len(LAYOUTS[r.get("layout", "full")])
                order += list(range(i + n - 1, i - 1, -1))
                i += n
            rects = [rects[j] for j in order]
        if len(flat) != len(rects):
            raise SystemExit(f"page {pi}: {len(flat)} panels but layouts give {len(rects)} slots")
        for k, (p, rect) in enumerate(zip(flat, rects)):
            yield pi, k, p, rect


def check(brief: dict) -> list[str]:
    errs, warns = [], []
    chars = {c["id"] for c in brief.get("characters", [])}
    seen = set()
    for pi, k, p, rect in panels(brief):
        pid = p.get("id") or f"p{pi}-{k}"
        if pid in seen:
            errs.append(f"duplicate panel id {pid}")
        seen.add(pid)
        if not p.get("prompt") and not p.get("image"):
            errs.append(f"{pid}: needs prompt (or image)")
        for c in p.get("cast", []):
            if c not in chars:
                errs.append(f"{pid}: unknown character {c}")
        for b in p.get("bubbles", []):
            if b.get("speaker") and b["speaker"] not in chars:
                errs.append(f"{pid}: bubble speaker {b['speaker']} not in characters")
            t = b.get("text", "")
            if len(t.replace("\n", "")) > 28:
                warns.append(f"{pid}: bubble '{t[:10]}…' is long ({len(t)} chars) — split it")
    # forbid_words: things that must never be drawn (e.g. Free Consult: the product itself).
    forbid = [w.lower() for w in brief.get("forbid_words", [])]
    for pi, k, p, rect in panels(brief):
        text = " ".join([p.get("prompt", ""), p.get("shot", "")]).lower()
        for w in forbid:
            if re.search(r"\b" + re.escape(w) + r"\b", text) if w.isascii() else w in text:
                errs.append(f"{p.get('id')}: prompt mentions forbidden '{w}' (see forbid_words)")
    if brief.get("client") == "free-consult":
        if not brief.get("sales_page", "").startswith("https://consult.antonbase.com/products/"):
            errs.append("free-consult brief needs sales_page = https://consult.antonbase.com/products/<id>/")
        if not forbid:
            errs.append("free-consult brief needs forbid_words (the product, its package, brand and logo)")
    if not brief.get("hook"):
        warns.append("no hook: the first panel must show the conflict without sound")
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import hooks as HK
        known = HK.ids()
        if not brief.get("hook_type"):
            warns.append("no hook_type: pick one from catalog/hooks.json (python3 tools/hooks.py for manga)")
        elif brief["hook_type"] not in known:
            warns.append(f"hook_type '{brief['hook_type']}' is not in catalog/hooks.json")
    except Exception:  # noqa: BLE001
        pass
    if not brief.get("teaser") and not brief.get("cta"):
        warns.append("no teaser/cta at the end")
    for w in warns:
        print("WARN", w)
    for e in errs:
        print("ERROR", e)
    return errs


# ---------------------------------------------------------------- image generation (Gemini)

GEMINI_MODEL = os.environ.get("MANGA_IMAGE_MODEL", "gemini-2.5-flash-image")
RATIOS = {"1:1": 1, "4:3": 4 / 3, "3:4": 3 / 4, "3:2": 1.5, "2:3": 2 / 3, "16:9": 16 / 9,
          "9:16": 9 / 16, "5:4": 1.25, "4:5": 0.8, "21:9": 21 / 9}


def nearest_ratio(w: int, h: int) -> str:
    r = w / h
    return min(RATIOS, key=lambda k: abs(math.log(RATIOS[k] / r)))


def gemini_image(prompt: str, refs: list[pathlib.Path], ratio: str) -> bytes:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set")
    parts = [{"text": prompt}]
    for r in refs:
        parts.append({"inline_data": {"mime_type": "image/png",
                                      "data": base64.b64encode(r.read_bytes()).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ratio}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    blob = part.get("inline_data") or part.get("inlineData")
                    if blob:
                        return base64.b64decode(blob["data"])
            raise RuntimeError(f"no image in response: {json.dumps(data)[:400]}")
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1}: {e}")
            import time
            time.sleep(6 * (attempt + 1))
    raise RuntimeError("unreachable")


STYLES = {
    "photo-manga": ("A photograph-like still frame for a Japanese web manga ad (写真漫画). Realistic Japanese people, "
                    "natural light, shallow depth of field, cinematic, expressive faces."),
    "anime-manga": ("A Japanese manga panel, clean black ink lines, screentone shading, expressive anime faces, "
                    "high contrast, published-manga quality."),
    "color-webtoon": ("A full-color Japanese webtoon panel, clean line art, soft cel shading, bright expressive faces."),
}
NO_TEXT = ("Do NOT draw any text, letters, speech bubbles, captions, sound-effect lettering, logos or watermarks. "
           "Leave some empty space near the top of the frame for speech bubbles.")


def style_text(brief: dict) -> str:
    st = brief.get("style", "photo-manga")
    return STYLES.get(st, st)


def char_sheet_path(brief, c) -> pathlib.Path:
    return pathlib.Path(brief["_out"]) / "characters" / f"{c['id']}.png"


def gen_characters(brief: dict):
    for c in brief.get("characters", []):
        out = char_sheet_path(brief, c)
        if c.get("image"):
            src = pathlib.Path(brief["_dir"]) / c["image"]
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.open(src).convert("RGB").save(out)
            continue
        if out.exists():
            continue
        prompt = (f"{style_text(brief)} Character reference: {c['look']}. "
                  "Show the same person twice side by side: front view and three-quarter view, "
                  "upper body, plain light-grey background, neutral expression. " + NO_TEXT)
        print("character", c["id"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(gemini_image(prompt, [], "3:2"))


def panel_prompt(brief, p) -> str:
    cast = {c["id"]: c for c in brief.get("characters", [])}
    who = "; ".join(f"{cast[c]['name']} = the person in reference image {i + 1} ({cast[c]['look']})"
                    for i, c in enumerate(p.get("cast", [])))
    shot = p.get("shot", "")
    return (f"{style_text(brief)} {('Setting: ' + brief['setting'] + '.') if brief.get('setting') else ''} "
            f"Scene: {p['prompt']}. {('Camera: ' + shot + '.') if shot else ''} "
            f"{('Characters: ' + who + '. Keep their faces, hair and clothes identical to the references.') if who else ''} "
            f"{NO_TEXT}")


def panel_path(brief, p, rect) -> pathlib.Path:
    h = hashlib.sha1((panel_prompt(brief, p) + nearest_ratio(rect[2], rect[3]) + GEMINI_MODEL).encode()).hexdigest()[:10]
    return pathlib.Path(brief["_out"]) / "panels" / f"{p['id']}-{h}.png"


def gen_images(brief: dict):
    gen_characters(brief)
    cast = {c["id"]: c for c in brief.get("characters", [])}
    for pi, k, p, rect in panels(brief):
        if p.get("image"):
            continue
        out = panel_path(brief, p, rect)
        if out.exists():
            continue
        refs = [char_sheet_path(brief, cast[c]) for c in p.get("cast", [])]
        print("panel", p["id"], nearest_ratio(rect[2], rect[3]))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(gemini_image(panel_prompt(brief, p), refs, nearest_ratio(rect[2], rect[3])))


def placeholders(brief: dict):
    """Stand-in panels so layout/timing can be checked without any API."""
    font = jp_font(36, bold=True)
    for pi, k, p, rect in panels(brief):
        out = panel_path(brief, p, rect)
        out.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (rect[2], rect[3]), (200, 205, 214))
        d = ImageDraw.Draw(img)
        for i in range(0, rect[2] + rect[3], 40):
            d.line([(i, 0), (i - rect[3], rect[3])], fill=(188, 193, 203), width=14)
        txt = f"{p['id']}\n" + wrap(p.get("prompt", ""), 18)[:120]
        d.multiline_text((24, rect[3] - 24), txt, font=font, fill=(60, 64, 72), anchor="ld", spacing=6)
        img.save(out)


def wrap(s: str, n: int) -> str:
    return "\n".join(s[i:i + n] for i in range(0, len(s), n))


# ---------------------------------------------------------------- voices (VOICEVOX)


def vv_url() -> str:
    return os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")


_SPEAKERS = None


def vv_speaker(name: str, style: str) -> int:
    global _SPEAKERS
    if _SPEAKERS is None:
        with urllib.request.urlopen(vv_url() + "/speakers", timeout=30) as r:
            _SPEAKERS = json.load(r)
    for s in _SPEAKERS:
        if s["name"] == name:
            for st in s["styles"]:
                if st["name"] == style:
                    return st["id"]
            return s["styles"][0]["id"]
    raise SystemExit(f"VOICEVOX speaker not installed: {name}")


def voice_path(brief, b) -> pathlib.Path:
    v = voice_of(brief, b)
    h = hashlib.sha1(json.dumps([b.get("say", b.get("text")), v], ensure_ascii=False).encode()).hexdigest()[:10]
    return pathlib.Path(brief["_out"]) / "voices" / f"{h}.wav"


def voice_of(brief, b) -> dict | None:
    if b.get("silent"):
        return None
    cast = {c["id"]: c for c in brief.get("characters", [])}
    if b.get("speaker") and cast[b["speaker"]].get("voice"):
        return cast[b["speaker"]]["voice"]
    return brief.get("narrator")


def gen_voices(brief: dict):
    for _, _, p, _ in panels(brief):
        for b in p.get("bubbles", []):
            v = voice_of(brief, b)
            if not v:
                continue
            out = voice_path(brief, b)
            if out.exists():
                continue
            text = (b.get("say") or b["text"]).replace("\n", "")
            sid = vv_speaker(v.get("speaker", "四国めたん"), v.get("style", "ノーマル"))
            q = json.loads(_post(f"/audio_query?text={urllib.parse.quote(text)}&speaker={sid}"))
            q["speedScale"] = v.get("speed", 1.12)
            q["pitchScale"] = v.get("pitch", 0.0)
            q["intonationScale"] = v.get("intonation", 1.15)
            q["prePhonemeLength"], q["postPhonemeLength"] = 0.05, 0.08
            q["outputSamplingRate"] = 48000
            audio = _post(f"/synthesis?speaker={sid}", json.dumps(q).encode())
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(audio)
            print("voice", text[:16])


def _post(path, data=None):
    req = urllib.request.Request(vv_url() + path, method="POST", data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def wav_len(p: pathlib.Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- text drawing

FONT_PATHS = {
    True: ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
           "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"],
    False: ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"],
}
_FONTS = {}


def jp_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _FONTS:
        for fp in FONT_PATHS[bold] + FONT_PATHS[not bold]:
            if os.path.exists(fp):
                _FONTS[key] = ImageFont.truetype(fp, size, index=0 if "JP" in fp else 0)
                break
        else:
            raise SystemExit("no CJK font found (install fonts-noto-cjk)")
    return _FONTS[key]


# vertical presentation forms so tategaki punctuation sits right
VERT = {"ー": "丨", "―": "丨", "-": "丨", "～": "≀", "〜": "≀", "…": "︙", "‥": "︰", "、": "︑", "。": "︒",
        "「": "﹁", "」": "﹂", "『": "﹃", "』": "﹄", "（": "︵", "）": "︶", "(": "︵", ")": "︶",
        "！": "︕", "!": "︕", "？": "︖", "?": "︖", "：": "︓"}
SMALL_KANA = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ")


def draw_vertical(text: str, size: int, color=(0, 0, 0)) -> Image.Image:
    """Render tategaki: columns right->left, one per line of `text`."""
    font = jp_font(size, bold=True)
    cols = text.split("\n")
    step = int(size * 1.08)
    colw = int(size * 1.25)
    rows = max(len(c) for c in cols)
    img = Image.new("RGBA", (colw * len(cols), step * rows + size // 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for ci, col in enumerate(cols):
        x = img.width - colw * (ci + 1) + (colw - size) // 2
        y = 0
        i = 0
        while i < len(col):
            ch = col[i]
            # keep "!?" / "!!" pairs on one cell, latin like "w" upright
            if ch in "!?！？" and i + 1 < len(col) and col[i + 1] in "!?！？":
                pair = (ch + col[i + 1]).replace("！", "!").replace("？", "?")
                d.text((x + size // 2, y + size // 2), pair, font=jp_font(int(size * 0.7), True), fill=color, anchor="mm")
                i += 2
                y += step
                continue
            g = VERT.get(ch, ch)
            dx, dy = 0, 0
            if ch in SMALL_KANA:
                dx, dy = size // 8, -size // 8
            if ch in "、。":
                dx, dy = size // 2, -size // 2
            d.text((x + size // 2 + dx, y + size // 2 + dy), g, font=font, fill=color, anchor="mm")
            y += step
            i += 1
    return img


def draw_horizontal(text: str, size: int, color=(0, 0, 0)) -> Image.Image:
    font = jp_font(size, bold=True)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = tmp.multiline_textbbox((0, 0), text, font=font, spacing=size // 4, align="center")
    img = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(img).multiline_text((-bb[0] + 2, -bb[1] + 2), text, font=font, fill=color,
                                       spacing=size // 4, align="center")
    return img


def bubble_image(b: dict, scale: float) -> tuple[Image.Image, tuple[int, int]]:
    """Return (RGBA bubble with tail, anchor offset of the bubble centre)."""
    kind = b.get("kind", "speech")  # speech | thought | shout | narration
    size = int(b.get("size", 40) * scale)
    vertical = b.get("vertical", True) and kind != "narration"
    txt = (draw_vertical if vertical else draw_horizontal)(b["text"], size)
    pad_x, pad_y = int(size * 0.75), int(size * 0.9)
    if kind == "narration":
        pad_x, pad_y = int(size * 0.5), int(size * 0.35)
    bw, bh = txt.width + 2 * pad_x, txt.height + 2 * pad_y
    tail = int(size * 1.4)
    img = Image.new("RGBA", (bw + 2 * tail, bh + 2 * tail), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (tail, tail, tail + bw, tail + bh)
    lw = max(3, int(size * 0.09))
    cx, cy = img.width // 2, img.height // 2
    tdir = b.get("tail", "down")  # down | up | left | right | none
    tail_pts = {
        "down": [(cx - size * 0.35, tail + bh - 6), (cx + size * 0.35, tail + bh - 6), (cx + size * 0.15, img.height - 4)],
        "up": [(cx - size * 0.35, tail + 6), (cx + size * 0.35, tail + 6), (cx - size * 0.15, 4)],
        "left": [(tail + 6, cy - size * 0.35), (tail + 6, cy + size * 0.35), (4, cy + size * 0.2)],
        "right": [(tail + bw - 6, cy - size * 0.35), (tail + bw - 6, cy + size * 0.35), (img.width - 4, cy + size * 0.2)],
    }.get(tdir)
    if kind == "narration":
        d.rectangle(box, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=lw)
    elif kind == "shout":
        pts = []
        n = 22
        for i in range(n):
            a = 2 * math.pi * i / n
            r = 1.0 if i % 2 == 0 else 0.82
            pts.append((cx + math.cos(a) * bw / 2 * r * 1.08, cy + math.sin(a) * bh / 2 * r * 1.08))
        d.polygon(pts, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=lw)
    elif kind == "thought":
        d.ellipse(box, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=lw)
        if tdir and tdir != "none":
            for i, rr in enumerate((size * 0.28, size * 0.18)):
                ox, oy = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}[tdir]
                px = cx + ox * (bw / 2 + size * (0.5 + i * 0.6))
                py = cy + oy * (bh / 2 + size * (0.5 + i * 0.6))
                d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(255, 255, 255, 255),
                          outline=(0, 0, 0, 255), width=max(2, lw - 1))
    else:
        d.rounded_rectangle(box, radius=int(min(bw, bh) * 0.48), fill=(255, 255, 255, 255),
                            outline=(0, 0, 0, 255), width=lw)
        if tail_pts:
            d.polygon(tail_pts, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
            d.line([tail_pts[0], tail_pts[2], tail_pts[1]], fill=(0, 0, 0, 255), width=lw)
            # cover the bubble outline where the tail joins
            j = 0 if tdir in ("down", "up") else 1
            a, c = tail_pts[0], tail_pts[1]
            d.line([(a[0] + (lw if j == 0 else 0), a[1] + (lw if j else 0)),
                    (c[0] - (lw if j == 0 else 0), c[1] - (lw if j else 0))], fill=(255, 255, 255, 255), width=lw + 2)
    img.alpha_composite(txt, (cx - txt.width // 2, cy - txt.height // 2))
    return img, (cx, cy)


def sfx_image(s: dict, scale: float) -> Image.Image:
    """Katakana sound effect with thick outline (e.g. ドクン, クスクス)."""
    size = int(s.get("size", 90) * scale)
    vertical = s.get("vertical", False)
    color = tuple(s.get("color", [20, 20, 20]))
    stroke = tuple(s.get("stroke", [255, 255, 255]))
    font = jp_font(size, bold=True)
    text = s["text"]
    if vertical:
        text = "\n".join(text)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    sw = max(4, size // 9)
    bb = tmp.multiline_textbbox((0, 0), text, font=font, stroke_width=sw, spacing=-size // 8)
    img = Image.new("RGBA", (bb[2] - bb[0] + 8, bb[3] - bb[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(img).multiline_text((-bb[0] + 4, -bb[1] + 4), text, font=font, fill=color,
                                       stroke_width=sw, stroke_fill=stroke, spacing=-size // 8)
    return img.rotate(s.get("rotate", -8), expand=True, resample=Image.BICUBIC)


# ---------------------------------------------------------------- timeline


def build_timeline(brief: dict) -> dict:
    """Events with start times. Panel reveal -> each bubble when its voice starts."""
    t = brief.get("lead_in", 0.25)
    events = []
    reveal = brief.get("reveal_seconds", 0.35)
    for pi, k, p, rect in panels(brief):
        if k == 0 and pi > 0:
            events.append({"type": "page", "page": pi, "t": t})
            t += brief.get("page_turn_seconds", 0.45)
        events.append({"type": "panel", "page": pi, "id": p["id"], "rect": rect, "t": t, "panel": p})
        t += reveal
        for s in p.get("sfx", []):
            events.append({"type": "sfx", "page": pi, "id": p["id"], "rect": rect, "t": t + s.get("delay", 0), "sfx": s})
        for b in p.get("bubbles", []):
            vp = voice_path(brief, b)
            if voice_of(brief, b) and vp.exists():
                dur = wav_len(vp)
            else:
                dur = 0.55 + 0.11 * len(b.get("say", b["text"]).replace("\n", ""))
            events.append({"type": "bubble", "page": pi, "id": p["id"], "rect": rect, "t": t, "dur": dur, "bubble": b,
                           "voice": str(vp) if voice_of(brief, b) and vp.exists() else None})
            t += dur + b.get("pause", brief.get("bubble_gap", 0.18))
        t += p.get("hold", brief.get("panel_hold", 0.25))
    teaser = brief.get("teaser")
    if teaser:
        events.append({"type": "teaser", "t": t, "text": teaser})
        t += brief.get("teaser_seconds", 2.0)
    return {"events": events, "duration": round(t + 0.2, 3)}


# ---------------------------------------------------------------- render


def ease_out_back(x: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def fit_cover(img: Image.Image, w: int, h: int, focus=(0.5, 0.4)) -> Image.Image:
    s = max(w / img.width, h / img.height)
    im = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    x = int((im.width - w) * focus[0])
    y = int((im.height - h) * focus[1])
    return im.crop((x, y, x + w, y + h))


def render(brief: dict):
    out = pathlib.Path(brief["_out"])
    out.mkdir(parents=True, exist_ok=True)
    tl = build_timeline(brief)
    (out / "timeline.json").write_text(json.dumps(
        {"duration": tl["duration"], "events": [{k: v for k, v in e.items() if k not in ("panel",)} for e in tl["events"]]},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # pre-load panel art (slightly oversized so we can drift/zoom inside the frame)
    art = {}
    for pi, k, p, rect in panels(brief):
        src = pathlib.Path(brief["_dir"]) / p["image"] if p.get("image") else panel_path(brief, p, rect)
        if not src.exists():
            raise SystemExit(f"missing panel image {src} — run `images` (or `placeholders`) first")
        im = Image.open(src).convert("RGB")
        zoom = 1.08
        art[p["id"]] = fit_cover(im, int(rect[2] * zoom), int(rect[3] * zoom), tuple(p.get("focus", (0.5, 0.4))))
    bubble_cache, sfx_cache = {}, {}
    teaser_font = jp_font(50, bold=True)

    n = int(tl["duration"] * FPS)
    ev = tl["events"]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "19", "-pix_fmt", "yuv420p", str(out / "silent.mp4")], stdin=subprocess.PIPE)
    frames_for_sheet = []
    for f in range(n):
        t = f / FPS
        frame = Image.new("RGB", (W, H), (255, 255, 255))
        # current page and page-turn slide
        page_evs = [e for e in ev if e["type"] == "page" and e["t"] <= t]
        cur_page = page_evs[-1]["page"] if page_evs else 0
        slide = 0.0
        if page_evs:
            x = (t - page_evs[-1]["t"]) / brief.get("page_turn_seconds", 0.45)
            if x < 1:
                slide = (1 - x) ** 3
        layer = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        shake = (0, 0)
        for e in ev:
            if e["t"] > t or e.get("page") != cur_page or e["type"] != "panel":
                continue
            x0, y0, w, h = e["rect"]
            age = t - e["t"]
            if True:
                a = min(1.0, age / 0.3)
                im = art[e["id"]]
                drift = min(1.0, age / 6.0)
                ox = int((im.width - w) * (0.5 + 0.5 * drift * e["panel"].get("pan", 0)))
                oy = int((im.height - h) * (0.5 - 0.3 * drift))
                tile = im.crop((ox, oy, ox + w, oy + h))
                if a < 1:
                    sc = 0.9 + 0.1 * ease_out_back(a)
                    tw, th = max(2, int(w * sc)), max(2, int(h * sc))
                    tile = tile.resize((tw, th), Image.BILINEAR)
                    mask = Image.new("L", tile.size, int(255 * a))
                    layer.paste(tile, (x0 + (w - tw) // 2, y0 + (h - th) // 2), mask)
                else:
                    layer.paste(tile, (x0, y0))
                    ImageDraw.Draw(layer).rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=(0, 0, 0), width=5)
                if e["panel"].get("shake") and age < 1.2:
                    amp = 10 * (1 - age / 1.2)
                    shake = (int(amp * math.sin(age * 55)), int(amp * math.cos(age * 47)))
        for e in ev:
            if e["t"] > t or e.get("page") != cur_page or e["type"] not in ("bubble", "sfx"):
                continue
            x0, y0, w, h = e["rect"]
            age = t - e["t"]
            spec = e.get("bubble") or e.get("sfx")
            key = json.dumps(spec, ensure_ascii=False, sort_keys=True)
            if e["type"] == "bubble":
                if key not in bubble_cache:
                    bubble_cache[key] = bubble_image(spec, brief.get("text_scale", 1.0))[0]
                im = bubble_cache[key]
            else:
                if key not in sfx_cache:
                    sfx_cache[key] = sfx_image(spec, brief.get("text_scale", 1.0))
                im = sfx_cache[key]
            px, py = spec.get("at", [0.5, 0.25])
            cx, cy = x0 + int(px * w), y0 + int(py * h)
            pop = min(1.0, age / 0.18)
            sc = 0.6 + 0.4 * ease_out_back(pop)
            if e["type"] == "sfx" and spec.get("pulse"):
                sc *= 1 + 0.06 * math.sin(age * 9)
            if sc != 1:
                im2 = im.resize((max(2, int(im.width * sc)), max(2, int(im.height * sc))), Image.BILINEAR)
            else:
                im2 = im
            # keep inside the canvas
            bx = min(max(cx - im2.width // 2, 8), W - im2.width - 8)
            by = min(max(cy - im2.height // 2, PAGE_TOP - 50), H - im2.height - 8)
            layer.alpha_composite(im2, (bx, by))
        frame.paste(layer.convert("RGB"), (shake[0], int(slide * H) + shake[1]))
        if slide > 0:  # previous page sliding out
            pass
        # teaser bar
        for e in ev:
            if e["type"] == "teaser" and e["t"] <= t:
                age = t - e["t"]
                a = min(1.0, age / 0.25)
                d = ImageDraw.Draw(frame)
                bar_y = PAGE_BOTTOM + 18
                d.rectangle((0, bar_y, W, bar_y + 100), fill=(int(17 * a + 255 * (1 - a)),) * 3)
                d.text((W // 2, bar_y + 50), e["text"], font=teaser_font, fill=(255, 255, 255), anchor="mm")
        ff.stdin.write(frame.tobytes())
        if f % FPS == 0:
            frames_for_sheet.append(frame.resize((216, 384)))
        if f == int(0.6 * FPS):
            frame.resize((360, 640), Image.LANCZOS).save(out / "first-frame-phone.png")
    ff.stdin.close()
    ff.wait()
    contact_sheet(frames_for_sheet, out / "contact-sheet.jpg")
    mix_audio(brief, tl, out)
    print(f"rendered {out / 'video.mp4'} ({tl['duration']:.1f}s)")


def contact_sheet(frames, path):
    cols = 8
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * 216, rows * 404), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for i, fr in enumerate(frames):
        x, y = (i % cols) * 216, (i // cols) * 404
        sheet.paste(fr, (x, y))
        d.text((x + 6, y + 386), f"{i}s", fill=(255, 255, 255), font=jp_font(16))
    sheet.save(path, quality=85)


def mix_audio(brief, tl, out):
    inputs, filters = [], []
    idx = 0
    for e in tl["events"]:
        if e["type"] == "bubble" and e.get("voice"):
            inputs += ["-i", e["voice"]]
            ms = int(e["t"] * 1000)
            filters.append(f"[{idx + 1}:a]aresample=48000,adelay={ms}|{ms}[v{idx}]")
            idx += 1
    sfx = brief.get("sfx_sounds", {})
    for e in tl["events"]:
        snd = (e.get("sfx") or {}).get("sound")
        if e["type"] == "sfx" and snd and (ROOT / sfx.get(snd, snd)).exists():
            inputs += ["-i", str(ROOT / sfx.get(snd, snd))]
            ms = int(e["t"] * 1000)
            filters.append(f"[{idx + 1}:a]aresample=48000,volume=0.6,adelay={ms}|{ms}[v{idx}]")
            idx += 1
    bgm = brief.get("bgm")
    if bgm and (ROOT / bgm).exists():
        inputs += ["-stream_loop", "-1", "-i", str(ROOT / bgm)]
        filters.append(f"[{idx + 1}:a]aresample=48000,volume={brief.get('bgm_volume', 0.12)},"
                       f"atrim=0:{tl['duration']}[v{idx}]")
        idx += 1
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "silent.mp4")] + inputs
    if idx:
        mix = "".join(f"[v{i}]" for i in range(idx))
        fc = ";".join(filters) + f";{mix}amix=inputs={idx}:normalize=0:dropout_transition=0,"
        fc += f"apad,atrim=0:{tl['duration']},loudnorm=I=-15:TP=-1.5[a]"
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "copy", "-c:a", "aac"]
    cmd += [str(out / "video.mp4")]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------- inspect (machine checks + page stills)


def _placed_box(spec, kind, rect, scale):
    """Where render() will put a bubble/sfx: (x0, y0, x1, y1, moved_px, image)."""
    im = bubble_image(spec, scale)[0] if kind == "bubble" else sfx_image(spec, scale)
    x0, y0, w, h = rect
    px, py = spec.get("at", [0.5, 0.25])
    cx, cy = x0 + int(px * w), y0 + int(py * h)
    bx = min(max(cx - im.width // 2, 8), W - im.width - 8)
    by = min(max(cy - im.height // 2, PAGE_TOP - 50), H - im.height - 8)
    moved = abs(bx - (cx - im.width // 2)) + abs(by - (cy - im.height // 2))
    return (bx, by, bx + im.width, by + im.height, moved, im)


def _tight(im, box):
    """Shrink a box to the non-transparent pixels of the image (bubble images carry tail padding)."""
    bb = im.getbbox() or (0, 0, im.width, im.height)
    return (box[0] + bb[0], box[1] + bb[1], box[0] + bb[2], box[1] + bb[3])


def inspect(brief: dict) -> int:
    """Check every page's final state. Writes outputs/manga/<id>/inspect/page-N.png. Returns error count."""
    out = pathlib.Path(brief["_out"]) / "inspect"
    out.mkdir(parents=True, exist_ok=True)
    scale = brief.get("text_scale", 1.0)
    errs = warns = 0
    pages = {}
    for pi, k, p, rect in panels(brief):
        pages.setdefault(pi, []).append((p, rect))
    for pi, items in pages.items():
        canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        boxes = []
        for p, rect in items:
            src = pathlib.Path(brief["_dir"]) / p["image"] if p.get("image") else panel_path(brief, p, rect)
            if src.exists():
                canvas.paste(fit_cover(Image.open(src).convert("RGB"), rect[2], rect[3], tuple(p.get("focus", (0.5, 0.4)))),
                             rect[:2])
            else:
                ImageDraw.Draw(canvas).rectangle((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]), fill=(220, 220, 220))
            ImageDraw.Draw(canvas).rectangle((rect[0], rect[1], rect[0] + rect[2] - 1, rect[1] + rect[3] - 1), outline=(0, 0, 0), width=5)
            for kind, specs in (("bubble", p.get("bubbles", [])), ("sfx", p.get("sfx", []))):
                for spec in specs:
                    x0, y0, x1, y1, moved, im = _placed_box(spec, kind, rect, scale)
                    canvas.alpha_composite(im, (x0, y0))
                    tb = _tight(im, (x0, y0, x1, y1))
                    label = f"{p['id']} {kind} '{spec['text'].replace(chr(10), '')[:8]}'"
                    boxes.append((label, kind, tb, rect))
                    if moved > 40:
                        print(f"WARN page{pi} {label}: pushed {moved}px to stay on screen — move 'at' inward")
                        warns += 1
                    size = spec.get("size", 40 if kind == "bubble" else 90) * scale
                    if size < 34:
                        print(f"WARN page{pi} {label}: text size {size:.0f}px < 34px is hard to read on a phone")
                        warns += 1
                    if tb[3] > SAFE_BOTTOM or tb[1] < SAFE_TOP:
                        print(f"ERROR page{pi} {label}: inside the top/bottom phone-UI zone")
                        errs += 1
                    if tb[2] > SAFE_RIGHT_X and tb[3] > SAFE_RIGHT_FROM_Y:
                        print(f"WARN page{pi} {label}: under the right-side like/comment buttons (x>0.86, y>0.5)")
                        warns += 1
                    if kind == "bubble":
                        area = (tb[2] - tb[0]) * (tb[3] - tb[1])
                        if area > 0.45 * rect[2] * rect[3]:
                            print(f"WARN page{pi} {label}: bubble covers {area / (rect[2] * rect[3]):.0%} of its panel — shorten text or enlarge panel")
                            warns += 1
                        ox = max(0, rect[0] - tb[0]) + max(0, tb[2] - rect[0] - rect[2])
                        oy = max(0, rect[1] - tb[1]) + max(0, tb[3] - rect[1] - rect[3])
                        if ox > (tb[2] - tb[0]) * 0.35 or oy > (tb[3] - tb[1]) * 0.35:
                            print(f"WARN page{pi} {label}: more than a third sticks out of its panel")
                            warns += 1
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i][2], boxes[j][2]
                ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
                iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
                if ix * iy > 0.08 * min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])):
                    level = "ERROR" if boxes[i][1] == boxes[j][1] == "bubble" else "WARN"
                    print(f"{level} page{pi} overlap: {boxes[i][0]}  x  {boxes[j][0]}")
                    errs += level == "ERROR"
                    warns += level == "WARN"
        # draw the phone-UI zones so a human/agent can see them
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        d.rectangle((0, SAFE_BOTTOM, W, H), fill=(255, 0, 0, 60))
        d.rectangle((0, 0, W, SAFE_TOP), fill=(255, 0, 0, 60))
        d.rectangle((SAFE_RIGHT_X, SAFE_RIGHT_FROM_Y, W, SAFE_BOTTOM), fill=(255, 0, 0, 60))
        for label, kind, tb, _ in boxes:
            d.rectangle(tb, outline=(0, 120, 255, 255) if kind == "bubble" else (0, 170, 0, 255), width=3)
        canvas.alpha_composite(ov)
        canvas.convert("RGB").save(out / f"page-{pi + 1}.png")
    tl = build_timeline(brief)
    print(f"estimated length {tl['duration']:.1f}s (real VOICEVOX audio is usually ~1.3x longer than this estimate)")
    print(f"inspect: {errs} errors, {warns} warnings; pages saved to {out}")
    return errs


def export_panels(brief: dict, dest: str | None = None) -> list[pathlib.Path]:
    """Save each panel, with its own bubbles/SFX, as a standalone image (for web pages).

    Writes outputs/manga/<id>/panels/<panel id>.webp (or into `dest`). Text that sticks
    out of its panel is cut off, so run `inspect` first and keep bubbles inside.
    """
    out = pathlib.Path(dest) if dest else pathlib.Path(brief["_out"]) / "panels"
    out.mkdir(parents=True, exist_ok=True)
    scale = brief.get("text_scale", 1.0)
    saved = []
    for pi, k, p, rect in panels(brief):
        src = pathlib.Path(brief["_dir"]) / p["image"] if p.get("image") else panel_path(brief, p, rect)
        if not src.exists():
            sys.exit(f"panel {p['id']}: no image yet ({src}) — run images or placeholders first")
        canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        canvas.paste(fit_cover(Image.open(src).convert("RGB"), rect[2], rect[3], tuple(p.get("focus", (0.5, 0.4)))), rect[:2])
        for kind, specs in (("bubble", p.get("bubbles", [])), ("sfx", p.get("sfx", []))):
            for spec in specs:
                x0, y0, x1, y1, moved, im = _placed_box(spec, kind, rect, scale)
                canvas.alpha_composite(im, (x0, y0))
                tb = _tight(im, (x0, y0, x1, y1))
                if tb[0] < rect[0] or tb[1] < rect[1] or tb[2] > rect[0] + rect[2] or tb[3] > rect[1] + rect[3]:
                    print(f"WARN {p['id']} {kind} '{spec['text'][:8]}': cut off at the panel edge in the export")
        im = canvas.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])).convert("RGB")
        path = out / f"{p['id']}.webp"
        im.save(path, "WEBP", quality=86)
        saved.append(path)
        print(f"saved {path} ({im.width}x{im.height})")
    return saved


# ---------------------------------------------------------------- main


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    brief = load(path)
    if check(brief):
        sys.exit("fix the errors above first")
    if cmd == "check":
        tl = build_timeline(brief)
        print(f"ok: {sum(1 for _ in panels(brief))} panels, ~{tl['duration']:.1f}s (estimated without voices)")
    elif cmd == "inspect":
        sys.exit(1 if inspect(brief) else 0)
    elif cmd == "images":
        gen_images(brief)
    elif cmd == "placeholders":
        placeholders(brief)
    elif cmd == "voices":
        gen_voices(brief)
    elif cmd == "render":
        render(brief)
    elif cmd == "panels":
        export_panels(brief, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "all":
        gen_images(brief)
        gen_voices(brief)
        inspect(brief)
        render(brief)
    else:
        sys.exit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
