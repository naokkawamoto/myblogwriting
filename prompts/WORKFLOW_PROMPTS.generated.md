# WORKFLOW_PROMPTS（自動生成・ドラフト）

`scripts/gen_workflow_prompts.py` がスキャンしました。**YAML は任意**。 `workflows:` に `note` / `sns` を書くと下に振り分けます。

## ① note っぽい（workflows に note）

| ファイル | workflows | tags |
|----------|-----------|------|
| `prompts/ops/note_from_theme.md` | note | note,theme,ops |
| `prompts/review/evaluator_scored_generic.md` | note | evaluation,scoring |

## ② SNS っぽい（workflows に sns / social）

| ファイル | workflows | tags |
|----------|-----------|------|
| `prompts/ops/share_short_from_company.md` | sns | share,x,linkedin |
| `prompts/social-company-pipeline/01_writer_draft.md` | sns | x,linkedin,pipeline |

## その他（front matter なし or 未分類）

| ファイル | workflows | tags |
|----------|-----------|------|
| `prompts/infographic/meta_build_image_prompt.md` | (front matter なし→手で振り分け) |  |
| `prompts/infographic/spec_hero_ogp_infographic.md` | (front matter なし→手で振り分け) |  |
| `prompts/note/dist/note_writer_prompt.md` | (front matter なし→手で振り分け) |  |
| `prompts/social-company-pipeline/02_external_evaluator.md` | (front matter なし→手で振り分け) |  |
| `prompts/social-company-pipeline/03_writer_refine.md` | (front matter なし→手で振り分け) |  |
| `prompts/social-company-pipeline/04_human_review_checklist.md` | (front matter なし→手で振り分け) |  |
