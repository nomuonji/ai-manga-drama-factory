# フックの一覧（レパートリー）の使い方と増やし方

一覧の正本は `catalog/hooks.json`。考え方は `docs/script-method.md` 第3.5節。

## フックとは

冒頭の2〜8秒で、スクロールする指を止めるもの。**最初の画・最初のテロップ・最初の一言（音）の組み合わせ**で、文の一行だけのことではない。
媒体のガイドでも、伝えたいことを最初の3秒に入れる・フックを最初の6秒の中で優先する・同じ本編で冒頭だけ変えた版を複数作る、が基本になっている（出典は下）。

置き方は2通り:
- **別素材のフック**: 本編の前に付ける、物語の外の2〜8秒（参考のAIドラマ広告の冒頭8秒）。差し替えやすい。ドラマは `drama.json` の `hooks`。
- **本編1カット目＝フック**: 物語がそのまま強い瞬間から始まる。漫画は1コマ目、ドラマは1カット目。

## 交換可能な接続型フック（2026-11-26）
本編を先に固定し、冒頭の短い視覚素材だけを交換する。物語全体の企画とは別。 `catalog/hooks.json` の `scope=modular-opener` を選ぶ。 `adaptable` は接続設計が必要、`body-dependent` は本筋に依存、`outro-teaser` は終端用途。
各型の `modular` には差替変数、短い局所回収、出口フレーム、接続、本編との契約、再利用テストを収録。1〜4秒は目安。冒頭の人物・場所が本編と違っても、動作・形・遮蔽・音・題名等で接続し、主題を誤認させない。元動画の転載ではなく自作・許諾済み素材で再現する。
本編2種に同じ素材（字幕や出口の差替は可）を接続する設計検証を行い、直接本編から始める対照も残す。視聴選択と接続直後の維持を別々に計測。冒頭で引き付けても接続で離脱するなら失敗。既存の observed 型を含む比較条件は維持する。
今回の12型は第三者の事例解説・制作ガイドから抽出した guidance 候補であり、原動画全編の検証・本人合格・市場実績は未確認。原典・秒数・出口・本編入口・反例が直接確認できたら事例を追記する。
研究源: [Tweenery](https://tweenery.com/tools/video-hooks)、[Nabit](https://nabit.ai/ads)、[Viral Hooks](https://viralhooks.org/database/41140-creative-transition-for-product-promo/)、[Savannah Sanchez](https://runneth.com/library/talk/the-30-ad-formats-every-top-brand-is-stealing-in-2025/)、[Content Department](https://contentdept.com.au/resources/social-media-hooks/)、[TikTok Creative Codes](https://ads.tiktok.com/business/en-US/creative-codes)。

## 選び方

```bash
python3 tools/hooks.py                # 全部
python3 tools/hooks.py for drama      # ドラマで使えるもの
python3 tools/hooks.py show contrast-pair
```

1. 脚本の「欲求喚起シーン」と「型」が決まったら、合いそうなフックを **違う仕組みのものから2〜3個** 選ぶ（同じ仕組みの言い換えは1つと数える）。
2. `script.md` の「3.5 フック」欄に、一覧の `id` と、今回の具体的な画・テロップを書く。
3. `drama.json` の `hooks[]` には `"type": "<一覧のid>"` を書く。漫画は `manga.json` の `"hook_type"`。`check` が一覧に無い id を警告する。
4. `evidence` が `observed` のものを少なくとも1つ入れる。`hypothesis` だけで固めない。

## 評価と錬成（My Portal の道場）

フックの良し悪しは本人の評価で決める。作り方は My Portal のチャット用スキル `short-form-video-direction`（v10 からフックを最重要工程として追加）で、道場 `short-video-direction`（ショート動画演出道場）が合格率で鍛えている。
- 本人に見せるフック違いの版は、見せる前に道場へ trial として登録する（試す仮説と合格の予測を付ける）。
- 本人の一言（良い／ボツ／ここが嫌）を道場に記録し、結果をこの一覧の該当する型の `results` にも足す。
- My Portal につながらないエージェントは、`productions/<id>/results.md` に本人の評価を書いておく（後でつながるエージェントが道場へ移す）。

## 一覧に足すとき

新しい型を見つけたら `catalog/hooks.json` に1件足す。

| 項目 | 書くこと |
|---|---|
| `id` | 英小文字・ハイフン |
| `name` | 日本語の短い名前 |
| `mechanism` | なぜ指が止まるのか（仕組み）。見た目の説明ではなく仕組み |
| `first_frame` | 最初の画に何が写っているか |
| `text_example` | テロップや台詞の例（**自分で作った例**。他人の動画の文言を写さない） |
| `best_for` | 向いている商材・話 |
| `formats` | `manga` / `drama` |
| `placement` | 別素材か、1コマ目か、終わりか |
| `avoid` | 規制・不快・やりがちな失敗 |
| `evidence` | `observed`（自分たちで実例を分解した）/ `guidance`（ガイド・記事に書いてある）/ `hypothesis`（仮説） |
| `sources` | 根拠。実例なら `docs/cases/…` を先に作ってそのパスを書く。記事ならURL |

ルール:
- **仕組みが同じなら新しい型にしない。** 既存の型の `sources` に実例を足す。
- 実例から足すときは、先に `docs/cases/` に1カットずつの分解を書く（ルールは `docs/cases/README.md`）。
- 使って結果が出たら、その型に `results` を足す: `{"production": "<id>", "variant": "h1", "result": "人の評価や数字", "date": "YYYY-MM-DD"}`。良い結果が続いたものは `hypothesis` → `observed` に上げる。
- 足したら `python3 tools/hooks.py check` が 0 errors になること。

## 根拠

- TikTok 広告のクリエイティブのベストプラクティス（最初の3秒で内容を伝える、テキストは1秒5〜10語） https://ads.tiktok.com/help/article/creative-best-practices
- 冒頭3秒・フックは最初の6秒で優先・1広告グループに3〜5本（上のガイドを引用した記事） https://selzee.com/blog/tiktok-ads-best-practices
- 同じ本編で冒頭だけ2パターン作ってABテストする https://0120.co.jp/blog/video-103/?service=video
- フックは文だけでなく、テキスト・動き・構図・テンポ・音・最初の視覚的な問いの組み合わせ https://www.seedance.tv/ja/blog/seedance-video-hook-generator-workflow-2026-ja
- フックの型の例（問い、悩みから、POV、隠して見せる、使っている所から、言い切り など） https://www.imagine.art/blogs/tiktok-ad-hooks
