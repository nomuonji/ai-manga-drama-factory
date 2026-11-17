# 困ったとき

エラーの文言で探す。直らないときは、何をして何が出たかを人に報告して止まる（同じ失敗を何度も繰り返さない）。

| 症状・エラー | 原因 | 直し方 |
|---|---|---|
| 日本語が □（豆腐）になる／`no CJK font found` | 日本語フォントが無い | Ubuntu: `sudo apt-get install fonts-noto-cjk`。Mac: Noto Sans CJK を入れ、`tools/manga/manga.py` の `FONT_PATHS` にパスを足す |
| `ffmpeg: command not found` | ffmpeg が無い | `sudo apt-get install ffmpeg` / `brew install ffmpeg` |
| `ModuleNotFoundError: PIL` | Pillow が無い | `pip install pillow numpy` |
| `json.decoder.JSONDecodeError` | JSON の書き間違い | 出た行番号の前後を見る。カンマの付け忘れ・付けすぎ、`"` の閉じ忘れが多い。`python3 -m json.tool <file>` で確かめる |
| `page 0: 1 panels but layouts give 2 slots` | `layout` のコマ数と `panels` の数が違う | `split` は2つ、`three` は3つ書く |
| `unknown character xxx` | `cast` / `speaker` に書いた id が `characters` に無い | 綴りを合わせる |
| `missing panel image … run images (or placeholders) first` | 絵がまだ無い | `placeholders`（ダミー）か `images`（本番）を先に |
| `GEMINI_API_KEY is not set` | キーが無い | 手元では作らず、Build ワークフローで作る。手元で作るなら `export GEMINI_API_KEY=…`（ファイルやログに書かない） |
| Gemini が `no image in response` | 安全フィルタで止まった、または混雑 | プロンプトから刺激の強い言葉（下着・血・暴力・子ども＋恋愛 等）を外す。数分おいて再実行 |
| Gemini が 429 | 回数制限 | 数分待って再実行。生成済みの絵は保存されているので、残りだけ作られる |
| `VOICEVOX speaker not installed: XXX` | 話者名が違う | `curl http://127.0.0.1:50021/speakers` で正しい名前を見る（例: 青山龍星、剣崎雌雄、冥鳴ひまり、春日部つむぎ、四国めたん、ずんだもん） |
| 声が付かない（無音） | VOICEVOX が動いていない／`voices` を回していない | 手元では `docker run -d -p 50021:50021 voicevox/voicevox_engine:cpu-latest`。Build では自動で動く |
| `FAL_KEY is not set` | キーが無い | GitHub Secrets に `FAL_KEY` を登録して Build で回す |
| fal で 404 / 422 | モデルIDが変わった・パラメータ名が違う | fal のモデルページ（`https://fal.ai/models/<モデルID>/llms.txt`）で入力項目を確かめ、`model` か `model_params` を直す |
| fal で長時間終わらない | 混雑 | ツールは20分で止まる。もう一度 `clips`（できたカットは飛ばされる） |
| 動画が横長・黒帯 | モデルが縦で返さなかった | `model_params` に `{"aspect_ratio":"9:16"}` を足す（項目名はモデルのページで確認） |
| 吹き出しが顔にかかる | 位置が悪い | `at` を 0.05〜0.1 ずつ動かす。または `focus` で絵の切り抜き位置を変える |
| `inspect` で `inside the top/bottom phone-UI zone` | 吹き出しが画面の下か上の端 | `at` の y を内側へ。最下段のコマなら y を 0.3 前後に |
| 尺が長すぎる | 台詞が多い・間が長い | `bubble_gap`・`panel_hold` を小さく → 台詞を短く → コマを減らす、の順 |
| Actions の artifact に動画が無い | 途中で失敗した | Actions のログで最初の赤いエラーを読む。この表で探す |
