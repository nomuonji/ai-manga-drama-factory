# 設計書（manga.json / drama.json）とツールの全項目

脚本（`docs/script-method.md`）が決まってから書く。手順は `docs/playbook-manga.md` / `docs/playbook-drama.md`。

## 2つの形式の違い

| | AI漫画ショート（`tools/manga/manga.py`） | AIドラマショート（`tools/drama/drama.py`） |
|---|---|---|
| 見た目 | 白い紙面に漫画のコマが1つずつ出る。縦書き吹き出し、カタカナ効果音、ページめくり、「▼このあと…▼」の帯 | 実写風の俳優、3〜8秒のカット、台詞、中央の白い字幕、最後にCTA画面 |
| 絵 | Gemini の画像モデル（`GEMINI_API_KEY`）。人物ごとのキャラ見本を全コマに渡して顔をそろえる | 同じ方法で、各カットの最初の1枚（キーフレーム）を作る |
| 動き | このツールが付ける（コマの出現・ゆっくり寄る・揺れ・吹き出しの出現） | fal.ai の動画モデル（`FAL_KEY`）。Seedance 2.0 が既定。Kling・MiniMax・Veo も選べる |
| 声 | VOICEVOX（人物ごとに話者を決める） | 動画モデルがしゃべる（native audio）か VOICEVOX |
| 文字 | 日本語はすべてツールが描く。絵の中には描かせない | 字幕はツールが描く |
| 費用の目安 | 絵8〜12枚で $0.3〜0.6 / 本 | 30秒で $5〜10、2分で $20〜40（`drama.py cost` で見積もる） |
| 時間 | Actions で 5〜10 分 | Actions で 15〜40 分 |

モデルの名前や値段は変わる。お金を使う前に `drama.py cost` を回し、呼び出しが 404 になったら fal のモデルページで名前を確かめる。

---

## manga.json

雛形: `templates/manga.json`。記入例: `productions/sample-manga-posture/manga.json`。

### 全体

| 項目 | 必須 | 意味 | 例・既定値 |
|---|---|---|---|
| `id` | ○ | 制作ID。フォルダ名と同じ | `"manga-posture-app"` |
| `title` | ○ | 題名（人が読む用） | |
| `hook` | ○ | 1コマ目で何が起きるか（脚本から） | |
| `audience` | | 誰に向けたものか | |
| `desire_scene` | | 欲求喚起シーン（脚本から） | |
| `style` | | 絵の作風。`photo-manga`（写真漫画）/ `anime-manga`（モノクロ漫画）/ `color-webtoon`（カラー）/ 英語の自由記述 | `photo-manga` |
| `setting` | | 全コマ共通の舞台（英語） | `"a modern Tokyo office, evening"` |
| `reading` | | コマを出す順。`ltr`（左→右。Web・広告漫画）/ `rtl`（右→左。紙の漫画） | `ltr` |
| `characters` | ○ | 登場人物（下の表） | |
| `narrator` | | ナレーション枠の声 | `{"speaker":"青山龍星"}` |
| `pages` | ○ | ページの配列（下の表） | |
| `teaser` | | 最後に出す帯の文字 | `"▼ このあと、大事件が… ▼"` |
| `teaser_seconds` | | 帯を出しておく秒数 | 2.0 |
| `bgm` / `bgm_volume` | | BGM のファイル（`assets/music/`）と音量 | 0.12 |
| `sfx_sounds` | | 効果音の名前 → ファイル | `{"don": "assets/sfx/don.ogg"}` |
| `text_scale` | | 吹き出し・効果音の文字を全体に大きく／小さく | 1.0 |
| `lead_in` | | 最初のコマが出るまでの秒数 | 0.25 |
| `reveal_seconds` | | コマが出てから最初の吹き出しまで | 0.35 |
| `bubble_gap` | | 吹き出しと吹き出しの間 | 0.18 |
| `panel_hold` | | コマの最後の余韻 | 0.25 |
| `page_turn_seconds` | | ページめくりの長さ | 0.45 |

### characters[]（登場人物）

| 項目 | 必須 | 意味 |
|---|---|---|
| `id` | ○ | 英小文字の短い名前。コマの `cast`、吹き出しの `speaker` で使う |
| `name` | ○ | 名前（絵の指示の中でも使う） |
| `look` | ○ | 見た目（英語）。年齢・性別・髪型と髪色・服と色・体格・特徴を全部書く。書き方は `docs/prompt-guide.md` |
| `voice` | | VOICEVOX の声: `speaker`（話者名）、`style`（ノーマル等）、`speed`（1.05〜1.2）、`pitch`、`intonation` |
| `image` | | 自分で用意した見本画像（制作フォルダからの相対パス）。あれば生成しない |

### pages[] → rows[] → panels[]

ページは「行（row）」を上から並べたもの。1行の中のコマの並びは `layout` で決める。

| row の項目 | 意味 |
|---|---|
| `layout` | `full`（1コマ）/ `split`（2等分）/ `split-wide-left`（左が広い 6:4）/ `split-wide-right`（右が広い 4:6）/ `three`（3等分） |
| `height` | 行の高さの比（ページ内の他の行との比）。見せ場 1.2〜1.4、つなぎ 0.8〜1.0 |
| `panels` | この行のコマ。`layout` のコマ数と同じ数だけ書く。**読む順に書く** |

| panel の項目 | 必須 | 意味 |
|---|---|---|
| `id` | ○ | `p1`, `p2`, … の通し番号 |
| `prompt` | ○ | 絵の内容（英語）。誰が・どこで・何をしていて・どんな表情か。**文字を書かせない** |
| `cast` | | 写る人物の id。ここに書いた人のキャラ見本が絵の生成に渡される。**写る人は必ず書く** |
| `shot` | | 撮り方（英語）: `close-up`、`medium shot`、`wide shot`、`over-the-shoulder`、`from below` など |
| `focus` | | 絵を切り抜くとき残す中心 [x, y]（0〜1）。顔が切れるときに使う | 
| `shake` | | `true` でコマが出たとき画面が揺れる（衝撃のコマ用） |
| `pan` | | -1〜1。ゆっくり横に流れる向き |
| `hold` | | このコマだけの余韻（秒） |
| `image` | | 自分で用意した絵（あれば生成しない） |
| `bubbles` | | 吹き出し（下の表） |
| `sfx` | | 効果音の文字（下の表） |

### bubbles[]（吹き出し）

| 項目 | 意味 | 既定 |
|---|---|---|
| `text` | 文字。`\n` で列（縦書き）を分ける。**右の列から読まれる**。1列6文字まで、3列まで | |
| `speaker` | 話す人物の id（声が付く） | |
| `kind` | `speech`（ふつう）/ `thought`（心の声・もくもく）/ `shout`（叫び・ギザギザ）/ `narration`（四角い説明枠・横書き） | `speech` |
| `at` | コマの中の位置 [x, y]。左上 [0,0]、右下 [1,1]。吹き出しの中心がここに来る | [0.5, 0.25] |
| `tail` | しっぽの向き `down` / `up` / `left` / `right` / `none` | `down` |
| `size` | 文字の大きさ（px、1080幅基準）。34 未満は読みにくい | 40 |
| `vertical` | `false` で横書き | `true` |
| `say` | 声で読む文（表示と読みを変えたいとき。例: 表示「3分!?」読み「さんぷん!?」） | `text` と同じ |
| `silent` | `true` で声を付けない | |
| `pause` | この吹き出しの後の間（秒） | `bubble_gap` |

### sfx[]（効果音の文字）

| 項目 | 意味 | 既定 |
|---|---|---|
| `text` | カタカナ（ドクン、ガーン、クスクス、ヒソヒソ…） | |
| `at` | コマの中の位置 [x, y] | |
| `size` | 大きさ | 90 |
| `rotate` | 傾き（度） | -8 |
| `pulse` | `true` で脈打つ | |
| `vertical` | `true` で縦に並べる | |
| `color` / `stroke` | 文字色・縁の色 [R,G,B] | 黒 / 白 |
| `sound` | 鳴らす音（`sfx_sounds` の名前） | |
| `delay` | コマが出てから鳴るまで（秒） | 0 |

### コマンド

```bash
python3 tools/manga/manga.py check        productions/<id>/manga.json   # 書き間違い・長すぎる台詞
python3 tools/manga/manga.py placeholders productions/<id>/manga.json   # ダミー絵（無料）
python3 tools/manga/manga.py inspect      productions/<id>/manga.json   # 配置の機械チェック＋ページ画像
python3 tools/manga/manga.py render       productions/<id>/manga.json   # 動画（ある絵と声で）
python3 tools/manga/manga.py images       productions/<id>/manga.json   # 絵の生成（GEMINI_API_KEY）
python3 tools/manga/manga.py voices       productions/<id>/manga.json   # 声の生成（VOICEVOX）
python3 tools/manga/manga.py all          productions/<id>/manga.json   # images → voices → inspect → render
```

出力（`outputs/manga/<id>/`）: `characters/`、`panels/`、`voices/`、`inspect/page-N.png`、`video.mp4`、`contact-sheet.jpg`、`first-frame-phone.png`、`timeline.json`。
絵と声はプロンプト・台詞のハッシュで保存される。**変えたコマ・台詞だけが作り直される。**

### 画面の配置（変えるときは `tools/manga/manga.py` の定数）

- 1080×1920、30fps。
- コマは y 0.06〜0.76、帯は y 0.77〜0.82。下 18%・上 4%・右下（x>0.86, y>0.5）はスマホのUIで隠れるので大事なものを置かない（`inspect` が検査する）。

---

## drama.json

雛形: `templates/drama.json`。記入例: `productions/sample-drama-english/drama.json`。

### 全体

| 項目 | 意味 | 既定 |
|---|---|---|
| `id` / `title` / `hook` / `audience` | 漫画と同じ | |
| `model` | 動画モデル: `seedance-2-fast` / `seedance-2` / `seedance-1-pro` / `kling-2.1` / `minimax-hailuo-02` / `veo-3.1-fast`、または fal のモデルID | `seedance-2-fast` |
| `price_per_second` | モデルIDを直接書いたときの見積もり単価 | 0.3 |
| `native_audio` | 動画モデルに台詞をしゃべらせる（対応モデルのみ）。`false` なら VOICEVOX | `true` |
| `model_params` | モデルにそのまま渡す追加の値（解像度など） | |
| `setting` | 全カット共通の場所（英語） | |
| `characters` | 漫画と同じ（`look`、`voice`、`image`） | |
| `narrator` | 話者のいない台詞の声 | |
| `bgm` / `bgm_volume` | BGM | 0.08 |
| `subtitle_y` | 字幕の上端の位置（画面の高さに対する割合） | 0.58 |
| `cta` | 最後の画面: `headline`、`button`、`seconds` | |

### shots[]（カット）

| 項目 | 必須 | 意味 |
|---|---|---|
| `id` | | 省略すると s01, s02, … |
| `frame` | ○ | 最初の1枚に写るもの（英語） |
| `motion` | ○ | カットの中で起きる動き（英語）。1つだけ |
| `camera` | | 撮り方（英語） |
| `cast` | | 写る人物の id（2人まで推奨） |
| `seconds` | | 長さ。多くのモデルは 5 か 10 |
| `speaker` / `line` | | 話す人と台詞（日本語） |
| `sub` | | 字幕（2行まで。省略すると `line`） |
| `native_audio` | | このカットだけ設定を変える |
| `image` | | 自分で用意したキーフレーム |

### コマンド

```bash
python3 tools/drama/drama.py check     productions/<id>/drama.json
python3 tools/drama/drama.py cost      productions/<id>/drama.json   # 費用の見積もり
python3 tools/drama/drama.py keyframes productions/<id>/drama.json   # 最初の1枚（GEMINI_API_KEY、安い）
python3 tools/drama/drama.py stills    productions/<id>/drama.json   # 仮の通し（無料。VOICEVOX があれば声付き）
python3 tools/drama/drama.py clips     productions/<id>/drama.json   # 動画化（FAL_KEY、高い）
python3 tools/drama/drama.py voices    productions/<id>/drama.json   # VOICEVOX の声（native_audio でないカット）
python3 tools/drama/drama.py assemble  productions/<id>/drama.json   # 字幕・連結・BGM・CTA
```

出力（`outputs/drama/<id>/`）: `characters/`、`keyframes/`、`clips/`、`voices/`、`preview-stills.mp4`、`video.mp4`。

---

## Build ワークフロー（GitHub Actions）

- **漫画**: PR に `productions/*/manga.json` が入ると自動で `all` を実行。手動実行もできる（`kind=manga`、`step=all|images|render`）。
- **ドラマ**: 手動実行のみ（`kind=drama`、`step=keyframes|stills|clips|assemble`）。お金がかかるので自動では動かない。
- 生成物は Actions のキャッシュに残るので、次の実行で同じ絵・動画にお金を払い直さない。
- 結果は artifact（`ai-manga-<番号>` / `ai-drama-<番号>`）からダウンロードする。

## 準備（最初の1回）

- GitHub Secrets: `GEMINI_API_KEY`（Google AI Studio）、ドラマを作るなら `FAL_KEY`（fal.ai、従量課金）。
- このリポジトリは MP4 を作るところまで。投稿は別の仕組み（video-publisher など）で行う。
