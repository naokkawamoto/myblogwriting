# note 用プロンプト（メンテナンス手順）

## 方針

- **編集するのは `sections/` 以下だけ**にする（関心ごとでファイル分割）。
- 貼り付け用の全文は **`dist/note_writer_prompt.md` を正**とする（**手で編集しない**）。
- 全文を再生成する: ターミナルで、**このワークスペースのルート**（`onetech-marketing-workspace/`）に移動してから  
  `bash prompts/note/assemble.sh` を実行する。
- `dist/` が無い環境では、初回だけ `assemble.sh` を実行するか、セクションを手動で連結して `dist` を作る。

### 毎回の依頼文

- 運用A: `sections/99_task_input.md` のプレースホルダを書き換えてから `assemble.sh`
- 運用B: 結合版を貼ったあと、チャット側で「今回のテーマは…」を追記（`99` はテンプレのまま維持）

## ファイル一覧

| パス | 役割 |
|------|------|
| `sections/01_role.md` | 書き手の役割・会社ブログとの分担 |
| `sections/02_audience_intent.md` | 想定読者・発信の意図 |
| `sections/03_reader_outcome.md` | 読了後にしてほしいこと |
| `sections/04_voice_style_length.md` | 文体・長さの目安 |
| `sections/05_themes.md` | 主軸テーマ（学習・資格・技術・CURIOSITY CHALLENGE 等） |
| `sections/06_confidentiality.md` | 機密・表現の線引き |
| `sections/07_links_cta.md` | 誘導は公式サイトのみ |
| `sections/08_closing_required.md` | 締め定型（WHAT A WONDERFUL DAY TODAY!・本文と接続する日本語つき） |
| `sections/09_author_background.md` | 個人として触れてよい経歴の骨子（参照用。必要なときだけ・毎回すべて使う必要なし） |
| `sections/99_task_input.md` | 依頼文の置き場（毎回のテーマ入力） |
| `assemble.sh` | 結合スクリプト |
| `dist/note_writer_prompt.md` | 生成物（AI に貼る用） |
| `CHANGELOG.md` | 変更履歴（人間が追記） |

## バージョン

- プロンプトの意味ある変更をしたら `CHANGELOG.md` に1行追記する。
- 互換性の大きな変更（ルール追加・削除）は、依頼テンプレ `99_task_input.md` も見直す。

## 将来（Cursor 自動化のとき）

- 生成パイプラインは `sections/*.md` を読み込み、結合して渡すか、`dist/` を読み込むかを決める。
- 「チェック as LLM」用レビュールールは `../review/README.md`（FM 非依存・採点つきは `evaluator_scored_generic.md`）。
- 会社記事・YouTube（またはディスクリプション）起点の X / LinkedIn 下書き〜外部評価〜改稿は `../social-company-pipeline/README.md`。
