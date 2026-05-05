# 運用（2系統）

社内向けの **「毎回どれを開いて、何を貼るか」** を固定する場所です。

| やりたいこと | 使うファイル | 書き手ルールの正本 |
|--------------|--------------|-------------------|
| **テーマだけ言って note 下書き** | `note_from_theme.md`（手順）＋ `sections/99_task_input.md`（依頼の正本） | `prompts/note/dist/note_writer_prompt.md` |
| **会社コンテンツのリンク／テキスト → X / LinkedIn の短文** | `share_short_from_company.md` | 同ファイル内に最小ルールあり（長いレビューループは別） |

## A. note：テーマから下書き

1. `sections/` を直したあとは、リポジトリルートで `bash prompts/note/assemble.sh` を実行する。  
2. `note_from_theme.md` の手順に従い、**結合プロンプト＋今回の依頼**を AI に渡す。

詳細は `note_from_theme.md` を見る。

## B. 会社コンテンツ → X / LinkedIn 短文

1. `share_short_from_company.md` を開き、プレースホルダを埋める。  
2. そのまま（または Cursor で当該ファイルを `@` 参照して）AI に依頼する。

**より厚い下書き**（評価→改稿まで）は `prompts/social-company-pipeline/` を使う。

## check as LLM（採点つき等）

- 特定モデルに縛らず、任意の LLM に貼る: `prompts/review/README.md`

## Cursor でのおすすめ

- note: `@prompts/note/dist/note_writer_prompt.md` と、依頼を書き換え済みの `@prompts/note/sections/99_task_input.md`（手順は `note_from_theme.md`）  
- シェア短文: `@prompts/ops/share_short_from_company.md`
