---
name: ai-manga-drama
description: Make an AI manga short (photo-manga / anime panels with vertical speech bubbles) or an AI drama short (photoreal actors via Seedance/Kling image-to-video) from a product or theme. Use for 漫画ショート動画, 漫画広告, AIドラマ, ショートドラマ広告.
---

# AI manga / AI drama shorts

Read `AGENTS.md`, then `docs/script-method.md` (脚本) and `docs/formats.md` (tools).

1. Fill `templates/script.md` sections 0–2 (inputs, product, 10+ desire-trigger scenes). Ask for anything missing.
2. Propose 3 story options (hook panel → escalation → turn → teaser/CTA) in chat and let the user pick before generating anything paid.
3. Write the beat sheet in script.md, then copy `templates/manga.json` or `templates/drama.json` into `productions/<id>/`.
4. `python tools/manga/manga.py check|placeholders|render` (or `drama.py check|cost`) locally to check structure, timing and cost.
5. Generate in the "Build" workflow (manga: PR commit; drama: manual keyframes → stills → clips → assemble).
6. Look at contact sheet, first frame and every panel/keyframe before calling it done. Report technical pass, your review, and what still needs the user's eyes/ears separately.
