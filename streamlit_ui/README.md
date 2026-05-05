# ローカル Web UI（Streamlit）

## 手動ハンドオフ（Web の Claude / ChatGPT だけ使う・API 不要）

サブスクのブラウザ版に **コピペだけ**で渡し、返答を貼って次へ進み、最後に **`outputs/handoff-sessions/`** にログ保存する UI です。

```bash
bash streamlit_ui/run_manual_chain.sh
```

またはルートで:

```bash
source .venv/bin/activate
streamlit run streamlit_ui/manual_home.py
```

- **ハブ**（`manual_home.py`）から **① note記事作成** / **② SNSシェア** / **プロンプト管理** / **アーカイブ** を開きます。①では **ブログ採点 90 点クリア**まで、改稿と再評価を **最大 4 周**まで想定した案内（ステップ **3・5** の「再評価」）。②は評価なし。**プロンプト索引**: **`prompts/WORKFLOW_PROMPTS.md`**（自動一覧ドラフトは **`WORKFLOW_PROMPTS.generated.md`**）。
- ステップは **10段**。テンプレは `{{STEP1}}` / `{{前の出力}}` など。
- 既存の **API 自動生成** UI は `streamlit run streamlit_ui/api/streamlit_app.py`（または `bash streamlit_ui/run.sh`）。配置は **`streamlit_ui/api/`**。

---

# 以下: API 自動生成 UI（`api/streamlit_app.py`）

ブラウザで **簡単なフォーム** から `note` / シェア短文 / 自由入力を実行します。データは外部サーバに送らず、**お使いの PC 上** で API（OpenAI / Anthropic）へリクエストし、結果は **`outputs/`** にも保存されます。

## 前提

- リポジトリルートで venv を有効化し、`pip install -e ".[web]"` 済み
- **ローカル（APIキー不要）**: サイドバーで「ローカル（OpenAI互換）」を選ぶ。**Ollama**（`ollama serve`）や **LM Studio** のローカルサーバが、OpenAI 互換の `.../v1` エンドポイントを出している必要があります。プロファイル A/B で別 URL・別モデルに切り替え可能（例: A を対話用、B を別モデル）。
- API キー（クラウド用）: **どちらか**（または併用）
  - **`.env`** に `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` を書く、または
  - **`.streamlit/secrets.toml`** に保存（`secrets.toml.example` をコピーして編集、または Streamlit サイドバーの **「APIキーを登録」** から保存）
  - 同じ変数名がある場合は **`secrets.toml` が `.env` より優先**（後から上書き）
- note 用は `bash prompts/note/assemble.sh` 実行済み（`dist/note_writer_prompt.md` があること）

## 起動

**推奨（cd 先を間違えにくい）**: リポジトリのルートにいて

```bash
bash streamlit_ui/run.sh
```

（`run.sh` が自動でルートに `cd` してから起動します。）

またはリポジトリ **ルート** で、**1行ずつ**（改行を入れて）実行:

```bash
cd /Users/kawamotonaoki/onetech-marketing-workspace
source .venv/bin/activate
pip install -e ".[web]"
streamlit run streamlit_ui/api/streamlit_app.py
```

> **注意**: `cd ...source .venv` のように **改行なしで貼ると失敗**します。必ず Enter で区切ってください。

表示された URL（通常 `http://localhost:8501`）をブラウザで開く。終了はターミナルで `Ctrl+C`。

### 真っ白・ImportError が出るとき

1. 上の `cd` が **このリポジトリのルート**（`prompts/` や `ot_marketing/` があるフォルダ）になっているか確認する。  
2. `pip install -e ".[web]"` をもう一度。  
3. それでもダメなら、ルートで `rm -rf ot_marketing/__pycache__ streamlit_ui/__pycache__` のあと再起動。

## セキュリティ

- **localhost のみ**で待ち受けます（同じ PC からのみアクセス想定）。
- 社内ネットワークに開放する場合は Streamlit の設定変更が必要です。既定のまま運用してください。
