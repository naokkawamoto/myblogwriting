# マーケ「仕組み」化ロードマップ

いまある **プロンプト資産**（`prompts/`）を正とし、その上に **入力→生成物の保存→（任意）レビュー** を薄く載せていくのが安全です。最初から会員制ポータルを作らなくてよい。

## 先に決める3つ

1. **主な実行場所**: Cursor のチャットだけで十分か、ブラウザ／CLIでも回したいか。  
2. **LLM のAPI**: 社内で使うキー（OpenAI / Anthropic 等）を **どこに置くか**（環境変数・1Password・GitHub Secrets）。リポジトリにコミットしない。  
3. **成果物の置き場**: まずは **`outputs/YYYY-MM-DD/` に Markdown で保存** で足りるか。後から Notion / Google Drive 連携でもよい。

## 段階案（おすすめ順）

### フェーズ0（すぐ・コストゼロ）

- **運用の型を固定**: `prompts/ops/README.md` の2系統＋ `review/` の check as LLM。  
- **命名規則**: 生成物ファイル名を `note-テーマの短いslug.md` のようにルール化。  
- **人の関所**: 投稿前は必ず人間（現状方針のまま）。
- **個人用／Teacher 向けの別リポ**: 会社用ワークスペースと履歴を分けたい場合は **`teacher/README.md`**（例: [myblogwriting](https://github.com/naokkawamoto/myblogwriting) を `teacher/myblogwriting` にクローン。親 `.gitignore` でクローン先のみ除外）。

### フェーズ1（実装済み：Python CLI）

- パッケージ **`ot_marketing`**、コマンド **`otm`**（`pyproject.toml`）。  
- サブコマンド: **`note`**（結合プロンプト＋タスクファイル）、**`share`**（シェア用テンプレ＋記入ファイル）、**`call`**（任意プロンプトファイル）。  
- **OpenAI / Anthropic** 両対応（`--provider` と API キー）。既定モデルは環境変数で上書き可。  
- **ローカル Web フォーム（API）**: `pip install -e ".[web]"` のあと `streamlit run streamlit_ui/api/streamlit_app.py`（**`streamlit_ui/README.md`**）。  
- 詳細: **`ot_marketing/README.md`**。

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
bash prompts/note/assemble.sh
otm note --task-file task.md --provider openai --output-basename my-note
```

### フェーズ2（運用が回ってから）

- **テンプレ入力**: Google フォームや Notion のDB → CSV / JSON をスクリプトが読む。  
- **レビューループ**: `review/evaluator_scored_generic.md` の出力を同じスレッドで続け、`social-company-pipeline/03` に渡す、までをスクリプトで連結。  
- **インフォ**: `meta_build_image_prompt.md` の出力をファイル保存 → 人が画像生成に貼る（画像バイナリはリポジトリに入れない運用が無難）。

### フェーズ3（本当に必要になったら）

- 小さな **Web UI**（社内のみ・認証付き）や **GitHub Actions** の `workflow_dispatch`（手動ボタン）でキーをサーバ側に閉じる。  
- 監査ログ・ロール分離（CEO と担当でプロンプト編集権限を分ける等）。

## 技術選定の目安

| 要件 | 向きやすい選択 |
|------|----------------|
| いまのリポジトリに寄せたい | Python + Typer、または Node + `tsx` / 小さめ npm script |
| Cursor 中心でよい | フェーズ0〜1は **チャット＋@ファイル** で十分。スクリプトは「保存と再現性」用 |
| 将来ベンダー差し替え | スクリプト内で **プロバイダを1関数に隔離**（OpenAI互換APIに寄せる手もあり） |

## 最初の一歩（具体）

1. リポジトリルートに **`outputs/` を作り**、`.gitignore` で除外するか方針決め。  
2. **フェーズ1のスクリプト**を1本追加するか、まず **Makefile** で `assemble` と「今日の出力フォルダ作成」だけ自動化する。  
3. 1週間運用して、「毎回コピペが辛い箇所」だけをスクリプト化する（全部を一度に自動化しない）。

## このドキュメントの扱い

進んだら **フェーズ番号と日付** を追記し、採用したAPI名・実行コマンドだけを残す。長い議事録は別紙にする。
