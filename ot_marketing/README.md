# ot-marketing CLI (`otm`)

## UI について（先に読む）

- **ブラウザやボタン式のアプリ画面はありません。** いまあるのは **CLI（コマンドライン）だけ** です。  
  **ターミナル**（macOS の「ターミナル」、または **Cursor 下部の Terminal**）に文字コマンドを打ち、API で生成した文章が **`outputs/` 以下の Markdown ファイル** として保存されます。
- **操作の流れ**: ① セットアップ（初回だけ）→ ② メモ用の `task.md` などをエディタで書く → ③ ターミナルで `otm note ...` を実行 → ④ 表示されたパスの `.md` を開いて読む／note にコピーする。
- **ローカル Web フォーム**は **Streamlit** で用意済みです（`streamlit_ui/README.md`）。CLI と同じく **`outputs/`** に保存されます。

リポジトリ内のプロンプトを読み、**OpenAI** または **Anthropic** の API で1回呼び出し、結果を **`outputs/UTC日付/*.md`** に保存します。Python **3.9+**。

## ローカル Web UI（フォーム）

```bash
source .venv/bin/activate
pip install -e ".[web]"
streamlit run streamlit_ui/api/streamlit_app.py
```

ブラウザで `http://localhost:8501` が開きます。詳細は **`streamlit_ui/README.md`**。

## セットアップ

リポジトリルートで:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[web]"   # Web UI も使う場合
cp .env.example .env
# .env に OPENAI_API_KEY / ANTHROPIC_API_KEY を記入
```

`bash prompts/note/assemble.sh` を実行済みで、`prompts/note/dist/note_writer_prompt.md` が存在していること。

## APIキーの置き場所（登録）

| 方法 | パス | 備考 |
|------|------|------|
| **`.env`** | リポジトリルート | `cp .env.example .env` で作成。**Git にコミットしない** |
| **`.streamlit/secrets.toml`** | リポジトリルート下 | Streamlit の **「APIキーを登録」** または `.streamlit/secrets.toml.example` をコピー。**`.gitignore` 済み** |
| **読み込み順** | — | まず `.env`、次に `secrets.toml` が **同じ変数名を上書き** |

CLI（`otm`）も Web（Streamlit）も、起動時に上記を読み込みます（`ot_marketing.env_load.bootstrap_env`）。

## 環境変数

| 変数 | 必須 | 説明 |
|------|------|------|
| `OPENAI_API_KEY` | `openai` 利用時 | OpenAI API キー |
| `ANTHROPIC_API_KEY` | `anthropic` 利用時 | Anthropic API キー |
| `OTM_OPENAI_MODEL` | 任意 | 既定 `gpt-4o` |
| `OTM_ANTHROPIC_MODEL` | 任意 | 既定 `claude-3-5-sonnet-20241022`（アカウントで使える ID に変更可） |

## コマンド例

### note 下書き

`task.md` に `99_task_input.md` 相当の「今回の依頼」を書いたうえで:

```bash
otm note --task-file task.md --provider openai --output-basename note-2026-0504-theme
otm note --task-file task.md --provider anthropic --model claude-sonnet-4-20250514
```

### シェア短文

`filled.md` に URL・貼り付けテキスト・要点などを書く:

```bash
otm share --filled-file filled.md --provider anthropic --output-basename li-x-ogp-release
```

### 任意プロンプト

```bash
otm call --prompt-file prompts/review/evaluator_scored_generic.md \
  --user-file my_eval_input.md \
  --provider openai \
  --output-basename review-result
```

標準入力を足す場合:

```bash
cat extra.md | otm call --prompt-file prompts/infographic/meta_build_image_prompt.md --stdin --provider openai --output-basename ig-meta
```

## 実行したあとに何が起きるか

1. ターミナルに `Calling openai model=...` のような一行が出る（進行表示）。  
2. 終わると **`/.../outputs/2026-05-04/note-draft.md` のような絶対パスが1行** だけ表示される。  
3. Finder でそのフォルダを開くか、Cursor で **File → Open File** からその `.md` を開く。中身が AI の回答（下書き）です。

Cursor を使う場合: **このフォルダをワークスペースとして開いた状態**で、**ターミナルパネル**（メニュー **Terminal → New Terminal** など）を開く。プロジェクトルートにいれば `cd` は不要。

## 注意

- **APIキーをGitにコミットしない**（`.gitignore` に `.env` あり）。
- 生成物は既定で `outputs/` にあり **Git 除外**。バージョン管理したい場合は `.gitignore` を調整。
