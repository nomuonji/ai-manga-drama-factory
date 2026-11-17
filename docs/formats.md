# Formats and tools (manga.json / drama.json)

Two ad-style vertical formats seen working on X/Instagram in Nov 2026, rebuilt here as
reusable tools. Both start from **a product or theme** and end in a 30–120 s vertical MP4.

| | AI manga short (`tools/manga/`) | AI drama short (`tools/drama/`) |
|---|---|---|
| Looks like | white page, photo-like or ink manga panels revealed one by one, vertical speech bubbles, katakana SFX, page turn, `▼このあと…▼` bar | photoreal actors, 3–8 s shots, spoken lines, big centred white subtitles, CTA card |
| Images | Gemini image model (`GEMINI_API_KEY`), characters kept consistent by passing a reference sheet into every panel | same, for the first frame of each shot |
| Motion | drawn here (panel pop-in, slow drift, shake, bubble pop) | fal.ai image-to-video: Seedance 2.0 (default), Kling, MiniMax Hailuo, Veo (`FAL_KEY`) |
| Voice | VOICEVOX per character | the video model speaks (native audio) or VOICEVOX |
| Text | all Japanese is drawn by code, never by the image model | subtitles drawn by code |
| Cost (approx.) | 8–12 images ≈ $0.3–0.6 per video | 30 s ≈ $5 (Seedance fast) … $10 (Seedance 2.0), 2 min ≈ $20–40 |
| Time | 5–10 min in Actions | 15–40 min in Actions |

Model ids and prices change. Run `drama.py cost` before spending, and check fal's page for the endpoint id if a call 404s.

## Reference examples (observed 2026-11-18)

- AI manga ad (@k_4415, CMO AI Pro): 7.6 s teaser — two women giggle「あれ見て…w」「やばいって…w」 → a man wonders「あれ、もしかして…」「ん？」 → close-up holding his thinning head「俺なんか見られてる…？」 with ドクンドクン → `▼このあと、大事件が…▼`. Their write-up says a 60 s manga ad takes 40–60 min with Claude Code: product URL → research → strategy → story → character design → panels → voice → video. Story sources: topics trending on X/TikTok, aspirations and everyday worries seen on Instagram, and episode 1 of short dramas / web manga. The person gives the product URL, the art style, the opening tempo, and anything the URL does not say about the customer.
- AI drama ad (seen in @sawakichi007_g's post): 2 min 4 s Instagram story ad for a men's clinic. Photoreal Japanese actors, a relationship-drama setup in the first seconds, the product introduced by a character as advice, price reassurance lines, a "first 5 per clinic" offer, `詳しくはこちら` button. Replies say Seedance or Kling; another suggests MiniMax via the fal API.

These are reference points only. Do not copy their stories, lines or characters.

Script first: follow `docs/script-method.md` before writing any JSON.

## Making a manga short

1. Copy `templates/manga.json` to `productions/<id>/manga.json`. Fill `hook`, `audience`, `desire_scene`, `characters` (look + VOICEVOX voice), `pages → rows → panels`.
   - Row layouts: `full`, `split`, `split-wide-left`, `split-wide-right`, `three`. `height` is relative within the page.
   - Panel: `prompt` (scene, in English, no text), `cast`, `shot`, `focus` [x,y] for the crop, `shake`, `pan`.
   - Bubble: `text` (`\n` = new column), `speaker`, `kind` speech|thought|shout|narration, `at` [x,y] in the panel, `tail` down|up|left|right|none, `size`, `say` (spoken text if it differs), `silent`.
   - SFX: `text`, `at`, `size`, `rotate`, `pulse`, `vertical`, `sound` (key in `sfx_sounds`).
   - `style`: `photo-manga` (like the reference), `anime-manga`, `color-webtoon`, or a free-text style.
2. `python tools/manga/manga.py check …` then `placeholders` + `render` locally to check layout and timing without any API.
3. Commit in a PR → the "Build" workflow makes the character sheets, panels, voices and video. Download the artifact.
4. **Look before you judge**: `contact-sheet.jpg` (1 frame/s), `first-frame-phone.png`, then the panels. Check: same face across panels, hands and props correct, no stray text in the images, bubbles not covering faces, voices matching characters. Fix a panel by editing its `prompt` — only changed panels are regenerated (cache by prompt hash, kept between runs).

## Making a drama short

1. Copy `templates/drama.json` to `productions/<id>/drama.json`. Each shot: `frame` (first frame), `motion` (what happens), `camera`, `cast`, `seconds` (5 or 10 on most models), `speaker` + `line` (spoken), `sub` (subtitle). `model` picks the video model, `native_audio` lets it speak.
2. Run the "Build" workflow manually, `kind=drama`:
   1. `step=keyframes` (cheap). Look at every keyframe. Regenerate until faces and places are right.
   2. `step=stills` → `preview-stills.mp4`, a slideshow with subtitles and VOICEVOX lines, to check the story and timing for free.
   3. `step=clips` (paid). Only shots whose keyframe/motion changed are regenerated.
   4. `step=assemble` → `video.mp4`.
3. Watch the whole video with sound. Check the same things as above plus lip sync and Japanese pronunciation of product names (native-audio models often misread them; then switch that shot to VOICEVOX by removing `line` from the model prompt and setting `native_audio: false`).

## Setup needed (once)

- Repository secrets: `GEMINI_API_KEY` (Google AI Studio) and, for drama, `FAL_KEY` (fal.ai, pay as you go).
- These tools only make the MP4. Posting is done elsewhere (e.g. video-publisher).
