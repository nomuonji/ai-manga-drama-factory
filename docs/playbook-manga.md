# AI漫画ショートの作り方（1ステップずつ）

動画づくりに慣れていないエージェント向けの手順書。**上から順に1ステップずつやる。ステップを飛ばさない。**
各ステップに「やること」「コマンド」「できあがりの確認（ゲート）」「よくある失敗」がある。ゲートを満たすまで次へ進まない。

関係する文書:
- 脚本の考え方: `docs/script-method.md`
- 設計書の全項目: `docs/formats.md`
- 絵の指示の書き方: `docs/prompt-guide.md`
- 作り手の暗黙知（見る順番・数値）: `docs/craft.md`
- 困ったとき: `docs/troubleshooting.md`

---

## ステップ0 準備（最初の1回だけ）

やること: 道具がそろっているか確かめる。

```bash
python3 --version          # 3.10 以上
ffmpeg -version | head -1  # 入っていること
python3 -c "import PIL; print(PIL.__version__)"   # 無ければ pip install pillow numpy
fc-list | grep -i "Noto Sans CJK" | head -1       # 無ければ fonts-noto-cjk を入れる
```

ゲート: 4つとも結果が出る。
よくある失敗: フォントが無いと日本語が豆腐（□）になる。`docs/troubleshooting.md` の「文字が□になる」を見る。

APIキー（`GEMINI_API_KEY`）や VOICEVOX が手元に無くても、ステップ1〜5（脚本・設計書・ダミー絵での確認）はできる。絵と声の生成は GitHub Actions（Build）でやる。

## ステップ1 制作フォルダを作る

```bash
ID=manga-<短い英語名>          # 例: manga-posture-app。英小文字・数字・ハイフンだけ
mkdir -p productions/$ID
cp templates/script.md productions/$ID/script.md
```

ゲート: `productions/$ID/script.md` がある。

## ステップ2 脚本を書く（ここが一番大事）

`docs/script-method.md` の第0〜6節を、`productions/$ID/script.md` を埋めながら順にやる。

1. 第0節: 受け取った情報を書く。**分からない項目は空欄のままにせず、人に聞く。** 聞けないときは「仮定: …」と書いて進む。
2. 第1節: 商品理解を3行。
3. 第2節: 欲しくなる場面を **10個以上**。1個ずつ「体でわかる／他人の目／商品につながる」に ○× を付ける。
4. 第3〜4節: 型を選んで **3案**。各案3行（冒頭・転換・終わり）。
5. **人に3案を見せて選んでもらう。** 人が「任せる」と言ったときだけ、自分で選び、選んだ理由を1行書く。
6. 第5〜6節: 選んだ案をビートシート（1行1コマ）にする。

ゲート（全部 ○ になるまで次へ進まない）:
- [ ] 1コマ目だけを見て（音なし）、何が起きているか一言で言える
- [ ] どのコマにも「前のコマから新しく分かること」が書いてある
- [ ] 気づき・衝撃のところにリアクションのコマ（顔のアップ・効果音）がある
- [ ] 吹き出し1つが縦2〜3行・1行6文字以内
- [ ] 商品は人物の答えとして出てくる（宣伝口調の台詞がない）
- [ ] 終わり方が「回収」か「続きが気になる」のどちらかに決まっている
- [ ] 第8節の広告チェックが全部埋まっている

よくある失敗:
- 1コマ目が「ある日のオフィス」のような説明で、何も起きていない → 事件が起きている瞬間から始める。
- 商品の説明を台詞にする（「この○○は△△成分配合で…」）→ 削る。人物は「実はさ…」「これだけです」としか言わない。
- 似たコマが続く（驚く顔が2回）→ 1つにする。

## ステップ3 設計書（manga.json）を書く

```bash
cp templates/manga.json productions/$ID/manga.json
```

`productions/$ID/manga.json` を開き、ビートシートを写す。項目の意味は `docs/formats.md`。順番:

1. `id` をフォルダ名と同じにする。`title` `hook` `audience` `desire_scene` を脚本から写す。
2. `style` を選ぶ（`photo-manga` 写真漫画 / `anime-manga` モノクロ漫画 / `color-webtoon` カラー）。
3. `characters`: 登場人物ごとに `id`（英小文字）、`name`、`look`（英語で見た目を細かく）、`voice`（VOICEVOX の話者）。書き方は `docs/prompt-guide.md` の「人物」。
4. `pages` → `rows` → `panels`: 1ページ3〜5コマ、ページは2〜3枚。
   - 1行（row）ごとに `layout` を選ぶ: `full`（1コマ）、`split`（2等分）、`split-wide-left` / `split-wide-right`（6:4）、`three`（3等分）。
   - `height` は行の高さの比。見せ場のコマは 1.2〜1.4、つなぎのコマは 0.8〜1.0。
   - 各コマ: `id`（p1, p2, … 通し番号）、`prompt`（英語・文字なし）、`cast`（出る人物の id）、`shot`（寄り・引き）。
5. 吹き出し `bubbles`: `speaker`、`text`（`\n` で列を分ける。縦書きは右の列から読まれる）、`at`（コマの中の位置。左上が [0,0]、右下が [1,1]）、`tail`（しっぽの向き）、`kind`（speech / thought / shout / narration）。
   - **置き場所の基本**: コマの上半分（y 0.2〜0.4）、顔の無い側。話している人に近い側に置き、しっぽをその人へ向ける。
   - 1コマに吹き出し2つまで。3つ目が要るならコマを分ける。
6. 効果音 `sfx`: 衝撃・緊張・笑いのコマにだけ。1ページ1〜2個まで。
7. 最後に `teaser`（続きが気になる終わり）か、別の出口を書く。

確認コマンド:

```bash
python3 tools/manga/manga.py check productions/$ID/manga.json
```

ゲート: `ERROR` が0。`WARN` は1つずつ読んで、直すか、直さない理由を script.md に書く。
よくある失敗:
- JSON の書き間違い（カンマ忘れ）→ エラーの行番号を見る。`python3 -m json.tool productions/$ID/manga.json` でも確かめられる。
- `layout` のコマ数と `panels` の数が合わない（`split` なのに panels が1つ）→ `page 0: 1 panels but layouts give 2 slots` と出る。

## ステップ4 ダミー絵で配置を確かめる（無料・1分）

```bash
python3 tools/manga/manga.py placeholders productions/$ID/manga.json   # 灰色の仮の絵を作る
python3 tools/manga/manga.py inspect      productions/$ID/manga.json   # 配置の機械チェック
```

`inspect` が見ること: 吹き出し同士の重なり、スマホの画面UIで隠れる場所（下18%・上4%・右下のボタン）、画面からのはみ出し、コマからのはみ出し、小さすぎる文字、吹き出しがコマの45%以上を覆っていないか。
結果の画像: `outputs/manga/$ID/inspect/page-1.png` …（赤い所＝スマホのUIで隠れる場所、青枠＝吹き出し、緑枠＝効果音）。

ゲート: `inspect: 0 errors`。画像を見られるなら page-N.png を全部見て、吹き出しの読む順番が自然か（上→下、同じ高さなら話す順）確かめる。
直し方: 吹き出しを動かすときは `at` を 0.05〜0.1 ずつ変えて、もう一度 `inspect`。

## ステップ5 ダミー絵で動画にする（無料・1〜2分）

```bash
python3 tools/manga/manga.py render productions/$ID/manga.json
```

できるもの（`outputs/manga/$ID/`）: `video.mp4`、`contact-sheet.jpg`（1秒ごとのコマ送り）、`first-frame-phone.png`（スマホ大の最初の画）、`timeline.json`（いつ何が出るか）。

ゲート:
- [ ] contact-sheet で、毎秒なにか新しいもの（コマ・吹き出し・効果音）が出ている。3秒以上何も変わらない区間がない
- [ ] 尺が目安に入る（予告型 8〜20秒、1本で完結する型 30〜60秒）。**声なしの推定は実際の声より短い（実際は約1.3倍）**
- [ ] ページめくりが脚本の区切りと合っている

## ステップ6 本番の絵と声を作る（GitHub Actions）

手元に `GEMINI_API_KEY` と VOICEVOX が無い前提の手順:

1. ブランチを作り、`productions/$ID/` を commit して push し、PR を作る。
2. PR に `manga.json` が入っていると **Build** ワークフローが自動で動く（キャラ見本 → コマ絵 → 声 → 検査 → 動画）。
3. 終わったら、Actions の実行ページから artifact（`ai-manga-<番号>`）をダウンロードする。

手元にキーと VOICEVOX があるとき:

```bash
export GEMINI_API_KEY=...            # ログやファイルに書かない
export VOICEVOX_URL=http://127.0.0.1:50021
python3 tools/manga/manga.py all productions/$ID/manga.json
```

費用の目安: 人物1人＝絵1枚、コマ1つ＝絵1枚。8コマ・3人で11枚、$0.5 前後。
ゲート: artifact に `video.mp4`、`characters/*.png`、`panels/*.png` がある。

## ステップ7 見て直す

`docs/review.md` の順に見る。特にAIの絵で起きやすいこと:

| 見つけたもの | 直し方 |
|---|---|
| コマによって顔が違う | `characters[].look` をもっと細かく（髪型・髪色・服の色・眼鏡など）。そのコマの `prompt` に「same person as reference」を足す。キャラ見本（`characters/*.png`）自体がおかしければ見本から作り直す（その人の `look` を変えると見本も作り直される） |
| 絵の中に文字・ロゴが出た | その `prompt` に「plain wall, no signs, no screens with text」を足す。スマホ画面は「screen facing away」 |
| 手・指がおかしい | 手を写さない構図に（`shot` を close-up や from behind に） |
| 吹き出しが顔に重なる | `at` を動かすか、`focus`（絵のどこを残すか [x,y]）を変える |
| 声がキャラに合わない | `voice.speaker` を変える。速すぎ・遅すぎは `speed`（1.05〜1.2） |
| 間延びする | `panel_hold`・`bubble_gap` を小さく。台詞を短く |

直すのは1回に1つの原因だけ。直したら同じ確認をもう一度。**変えたコマだけが作り直される**（プロンプトのハッシュで保存されている）。

## ステップ8 報告する

`docs/review.md` の「報告」の形で、次を分けて書く:
- technical: 何が通ったか（inspect 0 errors、尺、生成枚数、費用）
- review: 自分が見て確認したこと、気になったが直さなかった点と理由
- human: 人に見てほしいこと（音、面白さ、広告として出せるか）。未確認のものは「未確認」と書く

## 完成の定義（Definition of Done）

- script.md の全ゲートが ○、広告チェックが埋まっている
- `inspect` 0 errors
- 本番の絵で、人物の顔が全コマでそろい、絵に文字が無い
- 声つきの `video.mp4` がある
- 報告に technical / review / human が分けて書いてある
