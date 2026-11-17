# AI Manga & Drama Factory — エージェント向け手順

このリポジトリは、商品やテーマから **AI漫画ショート動画** と **AIドラマショート動画**（縦型・広告/SNS向け）を作る工場。
Claude / Codex / ChatGPT / 人、誰が作っても同じ手順・同じ品質になるように、判断基準はすべてこのリポジトリの文書に置く。

## 必ず読む順番

1. `docs/script-method.md` — 脚本の作り方。**絵や動画を作る前に、ここで脚本を確定させる。**
2. `docs/formats.md` — `manga.json` / `drama.json` の書き方と、ツールの使い方・費用。
3. `docs/review.md` — 仕上がりの確認と報告の仕方。

## 作業の流れ

```
受け取り → 商品理解 → 欲求喚起シーン10個以上 → 3案 → 人が選ぶ
  → ビートシート → productions/<id>/script.md
  → productions/<id>/manga.json か drama.json
  → check / placeholders / render（ローカル、無料）
  → Build ワークフロー（生成、有料）
  → docs/review.md で確認 → 報告
```

1. `productions/<id>/` を作り、`templates/script.md` をコピーして脚本を書く。
2. 人に3案を見せて選んでもらう。人が「任せる」と言った場合だけ自分で選ぶ。
3. `templates/manga.json` か `templates/drama.json` をコピーして設計書を書く。
4. ローカル確認（APIキー不要）:
   - 漫画: `python tools/manga/manga.py check …` → `placeholders …` → `render …`
   - ドラマ: `python tools/drama/drama.py check …` / `cost …`
5. 生成: 漫画はPRに `manga.json` をコミットすると Build ワークフローが動く。ドラマは Build を手動実行（`keyframes` → 確認 → `stills` → `clips` → `assemble`）。**キーフレームを見ずに `clips`（有料）を回さない。**
6. `docs/review.md` の順で確認し、technical / review / human を分けて報告する。

## 守ること

- 絵の中に文字を描かせない。日本語はすべてコードで描く。
- 実在の人物・有名人・他社のキャラクターを描かない。参考作品の台詞・話・人物をそのまま使わない。
- 規制のある業種（医療・美容・健康・金融・恋活）は、公開前に人の確認を取る。
- APIキーは GitHub の Secrets だけに置く。ログやファイルに出さない。
- 新しい演出・レイアウト・型は、作品の中に直書きせず `tools/` に汎用機能として足し、`docs/formats.md` に書く。
- 脚本の作り方を改善したら `docs/script-method.md` を更新し、根拠（実例のURLや配信結果）を「根拠」節に足す。根拠のない基準は「暫定」と書く。

## 置き場所

| 何 | どこ |
|---|---|
| 脚本・設計書・結果 | `productions/<id>/script.md`, `manga.json` / `drama.json`, `results.md` |
| 雛形 | `templates/` |
| ツール | `tools/manga/manga.py`, `tools/drama/drama.py` |
| BGM・効果音（CC0のみ） | `assets/`（出典は `assets/LICENSES.md`） |
| 生成物 | `outputs/`（git管理外。Build の成果物とキャッシュに残る） |
