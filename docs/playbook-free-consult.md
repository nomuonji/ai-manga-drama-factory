# Free Consult 向け漫画（SNS予告 + セールスページ漫画版）

Free Consult（consult.antonbase.com、リポジトリ `nomuonji/free-consult-blog`）の商品セールスページに、AI漫画を2通りで使う。

1. **SNS用の漫画予告動画**：悩みの場面を漫画で見せ、最後に「続きはリンクから」でセールスページへ送る。
2. **セールスページの漫画版**：`/products/<id>/manga/`。悩み・失敗・場面のスライドの写真を、漫画のコマに差し替えた版。写真版 `/products/<id>/` と GA4 で比べる。

どちらも同じ brief（manga.json）から作る。先に `docs/playbook-manga.md` を読むこと。

## 絶対のルール

Free Consult の画像ルール（free-consult-blog `docs/SOCIAL_PRODUCT_IMAGE_USAGE.md` §9・§9.1）に従う。

- **商品を描かない。** 商品、パッケージ、ロゴ、商品に似せた物をコマに入れない。brief の `forbid_words` にその商品の名前・形（bottle, tube, box…）を足しておくと、`check` が止めてくれる。
- **商品写真を参照画像として渡さない。** Amazon・楽天・メーカーの写真を描き直すのは禁止。
- **販売店の画像を SNS に使わない。** 動画の中にも入れない。
- 解決は「何かを見せる」直前で止める。スマホ画面は読めない構図にし、手元の物は映さない。答えはセールスページで見せる。
- 台詞に価格・レビュー・星評価・効果の断定（「必ず痩せる」など）を入れない。
- 実在の人物や他作品のキャラクターに似せない。

## 手順

1. セールスページを決める。Affiliate Operator の `sales_page_get` で、悩み（problem）・失敗（failure）・場面（scene）のスライドの見出しを読む。漫画はこの悩みをそのまま絵にする。
2. `templates/free-consult-manga.json` を `productions/fc-<セールスページid>/manga.json` にコピーする。
   - `id`、`sales_page`、`forbid_words` を埋める。
   - フックは `catalog/hooks.json` から選ぶ（`python3 tools/hooks.py for manga`）。予告動画なら rumor / overheard / being-watched が合いやすい。
   - コマの `id` は、セールスページのスライドと対応がわかる名前にする（例：`problem1`、`scene1`）。
3. `check` → `placeholders` → `inspect` で配置を直す。吹き出しはコマの内側に収める（漫画版ページではコマごとに切り出すので、はみ出た部分は切れる）。
4. GitHub Actions（build.yml）で画像・音声を作り、予告動画を `render` する。
5. **予告動画（SNS）**：`outputs/manga/<id>/video.mp4`。投稿文の最後にセールスページへの導線を入れる（プロフィールのリンク、または投稿先で許される場合は URL）。
6. **漫画版ページ**：
   ```bash
   python3 tools/manga/manga.py panels productions/fc-<id>/manga.json /path/to/free-consult-blog/public/comics/<セールスページid>
   ```
   で、コマを吹き出し付きの `.webp` に書き出す。free-consult-blog にコミットし、Firestore の `sales_pages/<id>` の該当スライドに
   ```json
   "comic": { "url": "/comics/<セールスページid>/problem1.webp", "alt": "鏡の前で髪を押さえてため息をつく女性" }
   ```
   を足す（`sales_page_save`）。保存は problem / failure / scene のスライドだけ通る。まとめて保存したら `site_rebuild` を1回。
7. 公開後、`/products/<id>/manga/` を開いて確認する。コマには「イメージ（AI生成）」が自動で付く。

## 比べ方

- 販売店ボタンのクリックで GA4 イベント `sales_offer_click` が送られる。`page_variant` が `photo` か `manga` か、`page_id` がどのページかを持つ。
- SNS の予告動画から来た人は漫画版へ、それ以外は写真版へ、というようにリンク先を分けると比べやすい。
- 漫画版は noindex（canonical は写真版）。検索からの流入は写真版だけに来る。
