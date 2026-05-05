# API 連携 Streamlit（ローカル）

OpenAI / Anthropic またはローカル（Ollama 等）へ接続し、note 下書き・シェア短文・自由入力を生成する UI です。手動ハンドオフ（`manual_chain_app.py`）とは別フォルダに分けています。

起動（リポジトリルートで）:

```bash
bash streamlit_ui/run.sh
```

または:

```bash
streamlit run streamlit_ui/api/streamlit_app.py
```

詳細は親の **`streamlit_ui/README.md`** の「API 自動生成 UI」節を参照してください。
