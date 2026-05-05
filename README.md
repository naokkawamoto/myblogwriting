# onetech-marketing-workspace

One Technology Japan の **マーケ／note／将来の SNS 用プロンプト** を置く場所です。  
**`onetechsystem` とは別フォルダ**で管理します（リポジトリも別にできます）。

## 中身

| パス | 内容 |
|------|------|
| `prompts/note/` | note 用の分割プロンプトと結合版（詳細はその中の `README.md`） |
| `prompts/social-company-pipeline/` | 記事（HTML/テキスト）・YouTube（またはディスクリプション）起点の X / LinkedIn 下書き → 外部LLM評価 → 改稿 → 人間レビュー（詳細はその中の `README.md`） |
| `prompts/ops/` | **日常運用の入口**（テーマ→note／会社コンテンツ→X・LinkedIn短文）。`README.md` から |
| `prompts/review/` | **check as LLM**（FM 非依存・採点つき等）。`README.md` から |
| `prompts/infographic/` | ヒーロー／OGP インフォ用 **仕様** と **画像プロンプト生成メタ**。`README.md` から |
| `streamlit_ui/` | **ローカル Web**（Streamlit）。**手動ハンドオフ**（ハブ `manual_home.py`・①は `manual_chain_app`）/ **API 生成** `api/streamlit_app.py`。`streamlit_ui/README.md` から |
| `teacher/` | **別 Git**：個人用ブログ執筆用（例: [myblogwriting](https://github.com/naokkawamoto/myblogwriting)）。`teacher/README.md` と `scripts/setup_teacher_blog_repo.sh` |

## Cursor で開く

1. Cursor の **File → Open Folder…**  
2. 次のフォルダを選ぶ:  
   `/Users/kawamotonaoki/onetech-marketing-workspace`

## 仕組み化の進め方

- 段階的な方針は **`docs/mechanism-roadmap.md`**（フェーズ0〜3・最初の一歩）。
- **Python CLI `otm`**（ターミナル）: `pip install -e .` → `otm note` / `otm share` / `otm call`。使い方は **`ot_marketing/README.md`**。
- **ローカル Web フォーム（Streamlit・API）**: `pip install -e ".[web]"` → `bash streamlit_ui/run.sh` または `streamlit run streamlit_ui/api/streamlit_app.py`。手順は **`streamlit_ui/README.md`**。

## メンテの要点

- **まず運用**: `prompts/ops/README.md`（note 下書き／シェア短文の2系統）
- レビュー専用: `prompts/review/`。インフォグラフィック: `prompts/infographic/`
- note: 編集は基本的に `prompts/note/sections/`。貼り付け用は `prompts/note/dist/note_writer_prompt.md`。結合は `bash prompts/note/assemble.sh`（ルートで実行）
- 会社コンテンツ→短文: `prompts/ops/share_short_from_company.md`（厚めのレビューループは `prompts/social-company-pipeline/`）

## 名前を変えたい場合

Finder でフォルダ名をリネームしてかまいません。中の `README` に古い絶対パスを書いていない限り、動作に影響しません。
