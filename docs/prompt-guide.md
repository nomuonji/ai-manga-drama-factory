# 絵と動きの指示（プロンプト）の書き方

画像AI・動画AIへの指示は **英語** で書く。日本語の台詞・字幕は指示に入れない（ツールが後から描く）。
ツールが自動で足すもの: 作風（`style`）、舞台（`setting`）、人物の見本、「文字を描かない」指示。だから各コマには **そのコマ固有のこと** だけ書けばよい。

## 人物（characters[].look）

顔をそろえる一番の鍵。**曖昧な言葉を使わず、目に見える特徴を並べる。**

```
良い: Japanese man, 28, short black hair slightly messy, tired eyes, navy suit, loosened dark-red tie,
      slim build, slouching posture
悪い: a normal salaryman            （毎回違う人になる）
悪い: handsome cool man             （主観の言葉は絵にならない）
```

書く順番: 国・性別・年齢 → 髪（長さ・色・形）→ 顔の特徴（目・眉・眼鏡・ひげ）→ 服（種類・色）→ 体格・姿勢 → 持ち物。
- 登場人物どうしで **髪型か服の色を必ず変える**（並んだとき見分けがつくように）。
- 実在の人物名・芸能人名・「〇〇似」は書かない。
- 子どもを出すときは、場面に必要な場合だけ。

## コマ・キーフレーム（panels[].prompt / shots[].frame）

1文で「誰が・どこで・何をしていて・どんな顔か」。

```
the tired man sees his own reflection in the dark office window: hunched back, rounded shoulders,
exhausted face; dramatic contrast lighting
```

- 人物は `characters` の `name` か「the tired man」のように見本と結びつく呼び方で書く。`cast` に入れ忘れると見本が渡らず別人になる。
- **表情と体の動きを具体的に**: surprised eyes / covering their mouths and giggling / holding his head with both hands。
- **1コマ1つの出来事**。「AしてからBする」は2コマに分ける。
- 吹き出しを置く場所を空けたいときは: `leave empty space above his head`。
- 文字が出やすいもの（看板、本の表紙、スマホ画面、パソコン画面、商品パッケージ）は避けるか、`screen facing away from camera`、`plain wall` と書く。
- 商品そのものを正確に描かせるのは難しい。形が大事な商品は、自分で撮った写真を `image` で使うか、商品が写らない構図にする。

### 撮り方（shot / camera）の言葉

| 言葉 | 使いどころ |
|---|---|
| `extreme close-up` | 目・口元。衝撃の瞬間 |
| `close-up` | 顔。気づき・感情 |
| `medium shot` | 上半身。会話 |
| `medium two-shot` | 2人の上半身。掛け合い |
| `wide shot` | 全身と場所。状況説明（1本に1〜2回まで） |
| `over-the-shoulder` | 相手の肩越し。見られている感じ |
| `from below` / `from above` | 下から＝強く見える／上から＝弱く見える |
| `reflection in a window/mirror` | 自分の姿に気づく場面 |

### 作風（style）

| 値 | 見た目 | 向いている商材 |
|---|---|---|
| `photo-manga` | 写真のような人物をコマに。参考事例の見た目 | 美容・健康・生活・仕事の悩み（リアルさが要る） |
| `anime-manga` | 白黒のペン画とトーン | 学び・エンタメ・軽い話 |
| `color-webtoon` | カラーの線画 | 若い人向け・明るい話 |

## 動き（shots[].motion）— ドラマのみ

動画AIは「最初の1枚」から数秒の動きを作る。**1カット1動作、ゆっくり、短く。**

```
良い: Kenta opens his mouth, hesitates, glances down at his notes; the client tilts his head politely
悪い: Kenta walks into the room, sits down, talks with the client, then they shake hands  （4動作は崩れる）
```

- 動きの強さ: `slowly`、`subtle`、`gently` を付けると顔が崩れにくい。
- カメラ: `slow push-in`（ゆっくり寄る）、`static camera`（固定）。速いパン・回り込みは崩れやすい。
- 台詞はツールが自動で足す（native audio のとき）。motion に台詞を書かない。

## よくある失敗と言い換え

| 出たもの | 足す・変える言葉 |
|---|---|
| 絵に文字・ロゴが入る | `no text, no signs, plain background` |
| 指が6本・手が変 | 手が写らない `shot`（close-up of face）に |
| 毎回顔が違う | `look` を細かく。`cast` に入れたか確認 |
| 人物が多すぎる | `only two people in the frame` |
| 表情が薄い | 感情を体の動きで書く（`eyes wide, mouth open, frozen`） |
| 暗すぎる | `soft warm indoor light` |
| 外国人っぽくなる | `Japanese` を `look` と `setting` の両方に書く |
