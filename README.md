# AI Manga & Drama Factory

商品やテーマから、縦型の **AI漫画ショート動画**（写真漫画・漫画風のコマ＋縦書きフキダシ＋効果音＋次回予告）と
**AIドラマショート動画**（実写風の俳優＋台詞＋字幕＋CTA）を作る工場。

- 脚本の作り方: [`docs/script-method.md`](docs/script-method.md)
- 設計書とツール: [`docs/formats.md`](docs/formats.md)
- 確認: [`docs/review.md`](docs/review.md)
- エージェント向け: [`AGENTS.md`](AGENTS.md)

## すぐ試す（APIキー不要）

```bash
pip install pillow numpy   # ffmpeg と Noto CJK フォントも必要
python tools/manga/manga.py placeholders productions/sample-manga-posture/manga.json
python tools/manga/manga.py render       productions/sample-manga-posture/manga.json
# -> outputs/manga/sample-manga-posture/video.mp4（絵はダミー）
```

## 本番の生成

GitHub Secrets に `GEMINI_API_KEY`（漫画・キーフレーム）と `FAL_KEY`（ドラマの動画化）を登録し、Build ワークフローを使う。
費用の目安: 漫画1本 $0.3〜0.6、ドラマ30秒 $5〜10（`python tools/drama/drama.py cost …` で事前見積もり）。
