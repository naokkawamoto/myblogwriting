# プロンプトのフロー別索引（運用手順）

YAML を付けたファイルだけ自動一覧されます。**自動ドラフト**: `WORKFLOW_PROMPTS.generated.md`（`python scripts/gen_workflow_prompts.py`）。

## ① note記事作成（評価あり）

| ファイル | 概要 |
|----------|------|
| `note/dist/note_writer_prompt.md` | note 一次記事用標準（`assemble.sh` で結合） |
| `review/evaluator_scored_generic.md` | ChatGPT 採点評価（ステップ3・5 の正本） |
| `ops/note_from_theme.md` | テーマ運用メモ |

## 画像（note アイキャッチ／OGP など）

| ファイル | 概要 |
|----------|------|
| `infographic/meta_build_image_prompt.md` | メタ用。**C**＝note 横長 DX ワークフローインフォ（既定）、**B**＝編集リアル／シネマ、**A**＝汎用 OGP フラット |
| `infographic/spec_note_dx_workflow_infographic.md` | **C** の仕様正本（5 ステップ＋下部 KPI＋日本語キャプション） |
| `infographic/spec_note_editorial_cinematic.md` | **B** の仕様正本 |
| `infographic/spec_hero_ogp_infographic.md` | **A** の仕様正本 |

手動フローの **ステップ8** は **C** に沿って英語プロンプトを出すよう指示済み（`streamlit_ui/manual_chain_app.py`）。

## ② SNSシェア（評価なし・Claudeのみ）

| ファイル | 概要 |
|----------|------|
| `ops/share_short_from_company.md` | X／LinkedIn（日英）／ハッシュタグ。**既定**。YAML `workflows: [sns]` |
| `social-company-pipeline/01_writer_draft.md` | ソースから長めの SNS 下書きパイプライン① |

---

※ **`manual_home`** で①／②／プロンプト管理／アーカイブを開けます。
