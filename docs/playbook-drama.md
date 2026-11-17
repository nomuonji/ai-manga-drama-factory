# AIドラマショートの作り方（1ステップずつ）

実写風の俳優が演じる縦型ドラマ。**動画化（clips）はお金がかかる**ので、安い工程で全部確かめてから動画にする。
上から順に1ステップずつやる。ゲートを満たすまで次へ進まない。

```
脚本 → 設計書 → check / cost → keyframes（静止画, 安い） → 見る → stills（仮の通し, 無料）
  → 見る → clips（動画化, 高い） → assemble → 見て直す → 報告
```

---

## ステップ1 脚本

漫画と同じく `docs/script-method.md` で脚本を作る（`templates/script.md` をコピー）。ドラマ特有の注意:

- **1カット＝1つの動作**（振り向く、スマホを見せる、握手する）。1カットの中で2つ以上のことを起こさない。動画モデルは複雑な段取りを守れない。
- 1カット 4〜8秒、全体 30〜90秒が作りやすい（暫定）。2分の広告は、カット数が多く費用も高い（`cost` で確認）。
- 登場人物は **1カット2人まで**。3人以上は顔が崩れやすい。
- 台詞は1カット1人・1文。掛け合いはカットを分ける。
- 最初のカットは、音なしで状況がわかる顔のアップか、事件の瞬間。
- **フックは本編と別に2〜3種類作る**（`docs/script-method.md` 第3.5節、`docs/cases/20261117-…` の冒頭8秒）。本編と同じ人物で、物語の外で本編の対立（差・悩み）をひと目で見せる2〜8秒。題名テロップ（この先の約束）をフックか本編1カット目に置く。

## ステップ2 設計書（drama.json）

```bash
ID=drama-<短い英語名>
mkdir -p productions/$ID
cp templates/drama.json productions/$ID/drama.json
python3 tools/drama/drama.py check productions/$ID/drama.json
python3 tools/drama/drama.py cost  productions/$ID/drama.json
```

各カット（`shots[]`）に書くこと:

| 項目 | 書くこと | 例 |
|---|---|---|
| `frame` | 最初の1枚に写るもの（英語） | Kenta freezes mid-sentence in a meeting, sweat on his forehead |
| `motion` | そのカットで起きる動き（英語、1つだけ） | Kenta opens his mouth, hesitates, glances down at his notes |
| `camera` | 寄り・引き・角度 | close-up, slightly from below |
| `cast` | 写る人物の id | ["senpai"] |
| `seconds` | 長さ（多くのモデルは 5 か 10） | 5 |
| `speaker` / `line` | 話す人と台詞（日本語） | senpai / えっと…ア、アイ… |
| `sub` | 字幕（日本語、2行まで。心の声は（）で） | （やばい…何も出てこない） |

フック（`hooks`）: 2〜3種類。各フックは `id`、`idea`、`shots`（書き方は上と同じ、合計2〜8秒）。フックごとに完成動画が1本ずつできる。

全体の項目: `model`（動画モデル）、`native_audio`（モデルに台詞をしゃべらせるか）、`characters`、`setting`、`bgm`、`cta`。

ゲート: `check` が ok。`cost` の金額を人に伝え、了承をもらう（了承済みの予算内なら不要）。

モデルの選び方（2026-11 時点。値段は変わるので `cost` と fal の料金ページで確かめる）:

| モデル（`model`） | 特徴 | 目安 |
|---|---|---|
| `seedance-2-fast` | 既定。台詞の音声も作れる | 安め |
| `seedance-2` | 画質・動きが一番良い。音声あり | 高い |
| `kling-2.1` | 安い。音声なし（VOICEVOX で声を付ける） | 安い |
| `minimax-hailuo-02` | とても安い。音声なし | 最安 |
| `veo-3.1-fast` | 音声あり。英語の台詞に強い | 中 |

## ステップ3 キーフレーム（最初の1枚）を作って見る

GitHub Actions の **Build** を手動実行: `production=$ID`、`kind=drama`、`step=keyframes`。
（手元にキーがあれば `python3 tools/drama/drama.py keyframes productions/$ID/drama.json`）

artifact の `keyframes/*.png` と `characters/*.png` を全部見る。

ゲート（全カット ○ になるまで clips に進まない）:
- [ ] 同じ人物が全カットで同じ顔・髪・服
- [ ] 場所が脚本どおり（会議室のはずが別の場所になっていない）
- [ ] 文字・ロゴ・透かしが写っていない
- [ ] 手・指・持ち物がおかしくない
- [ ] 縦長（9:16）の中で、顔が字幕の位置（下から4割あたり）に重なっていない

直し方: そのカットの `frame` / `camera` を書き直してもう一度 `keyframes`。変えたカットだけが作り直される。

## ステップ4 仮の通し（stills）で話を確かめる（無料）

Build: `step=stills`。キーフレームをゆっくり寄せながら並べ、字幕と VOICEVOX の声を付けた `preview-stills.mp4` ができる。

ゲート:
- [ ] フックごとの版（`preview-stills-h1.mp4` …）を見比べ、どれも最初の2秒で目が止まる
- [ ] フックから本編に切り替わったとき、同じ人物の話だとわかる
- [ ] 字幕だけ読んで話がわかる
- [ ] 間延びするカット、詰まりすぎるカットがない
- [ ] 最後の CTA まで含めて尺が目安に入る

## ステップ5 動画にする（有料）

Build: `step=clips`。カットごとに動画モデルで動かす。1カット数分かかる。
**一度作ったカットは保存されるので、失敗したカットだけ直して再実行すればよい。**

## ステップ6 組み立て

Build: `step=assemble`。縦1080×1920に合わせ、字幕を焼き込み、つなぎ、BGM と CTA を付けて `video.mp4` を作る。

## ステップ7 見て直す

`docs/review.md` の順で見る。ドラマで起きやすいこと:

| 見つけたもの | 直し方 |
|---|---|
| 途中で顔が変わる | `motion` を短く単純に。カメラの大きな動きをやめる。`seconds` を5に |
| 口の動きと声が合わない | そのカットに `"native_audio": false` を書くと、そのカットだけ VOICEVOX の声になる（全体の `native_audio` より優先） |
| 商品名・固有名詞の読みが違う | 台詞をひらがなにする。直らなければ VOICEVOX に切り替える |
| 変な文字が画面に出る | `frame` に no text を足す。看板・画面が写らない構図に |
| 動きが不自然・速すぎる | `motion` に slowly / subtle を足す |

## ステップ8 報告

technical（生成したカット数・費用・尺）、review（自分で見たこと）、human（音・演技・広告として出せるか。未確認は未確認と書く）を分けて書く。

## 完成の定義

- keyframes の全ゲート ○ を確認してから clips を回した
- 人物の顔が全カットでそろっている
- 字幕が読める・スマホのUIに隠れない
- 費用が了承の範囲内
- 報告が3つに分かれている
