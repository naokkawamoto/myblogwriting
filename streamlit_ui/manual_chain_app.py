"""
① note記事作成フロー（単体起動可）。ハブは `manual_home.py`。

- ステップ1: `prompts/**/*.md` から標準プロンプト＋カスタム結合。評価は ChatGPT のみ（正本 `prompts/review/evaluator_scored_generic.md`）。
- 9 ステップ構成（旧10→新9: 合格メモ・公開メモを削除、noteタグ生成を追加）。
- ステップ8 画像プロンプトは A 実写 / B イラスト・アニメ / C インフォ図解 の **3 スタイル選択**。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from handoff_common import read_prompt_body_for_copy
from ot_marketing.paths import repo_root

NUM_STEPS = 9
PASS_THRESHOLD = 90
EVAL_STEP_INDICES = frozenset({2, 4})
# 評価ステップ（3・5）で「ウィザードを戻さず」同じ画面から取り直せる回数（1ラウンド目を含めて最大4回）
EVAL_MAX_ROUNDS = 4

def _note_input_specs() -> list[str]:
    s0 = (
        "左で **リポジトリの標準プロンプト（`prompts/` の .md）を選択**し、テーマ・URL などを埋める。"
        " 既定 **`prompts/note/dist/note_writer_prompt.md`**。"
    )
    s1 = (
        "Claude で確定した一次記事の本文だけ。確定ボタンのあと右に ChatGPT 用の評価依頼が出ます。"
    )
    s2 = (
        "ChatGPT の評価全文と総合スコア（0〜100）。"
        f" **{PASS_THRESHOLD} 点以上**で次へ。**再評価ボタン**で同一ステップ内に最大 **{EVAL_MAX_ROUNDS} 回**。"
    )
    s3 = "Claude が返した改稿後の本文。折りたたみに改稿依頼の再掲があります。"
    s4 = (
        "二次評価も ChatGPT。全文とスコア。"
        f" **{PASS_THRESHOLD} 点以上**で次へ。再評価ボタン最大 {EVAL_MAX_ROUNDS} 回。"
    )
    tail = [
        "手修正後の確定稿（本文だけ貼る）。",
        "Claude にタグ案を依頼（確定稿が自動で埋まる）。返ってきたタグを貼る。",
        "スタイル A/B/C を選んで右の英語プロンプトを生成 → 画像ツールへ。",
        "ステップ6の確定稿を **自動引継ぎ**。公開URLを入れて、右のClaudeプロンプトをコピー。返答を貼り付けて業務完了。",
    ]
    return [s0, s1, s2, s3, s4, *tail]


NOTE_NAV_LABELS = [
    "1 希望 → Claude",
    "2 一次記事 → ChatGPT評価",
    "3 一次評価 → Claude改稿",
    "4 改稿を貼る",
    "5 二次評価 → ChatGPT",
    "6 確定稿",
    "7 noteタグ（Claude）",
    "8 画像（A/B/C 選択）",
    "9 シェア（稿＋URL→Claude）",
]

NOTE_HEADINGS = [
    "ステップ1　記事の希望",
    "ステップ2　一次記事（Claude）を貼る",
    "ステップ3　一次評価（ChatGPT）を貼る・採点",
    "ステップ4　改稿（Claude）を貼る",
    "ステップ5　二次評価（ChatGPT）",
    "ステップ6　確定稿",
    "ステップ7　noteタグ作成（Claude）",
    "ステップ8　画像プロンプト → 画像ツール（A/B/C 選択）",
    "ステップ9　シェア文案（最終稿・URL → Claude）",
]

STEP_OUTPUT_SPEC = [
    "標準プロンプト＋カスタム結合。**Claude** にコピー（ステップ1）。",
    "ChatGPT に貼る「一次評価」依頼の全文（一次記事が埋まります）。",
    "一次評価の依頼文は **ステップ2 の右**でコピー。ここでは左に返答を貼ると **Claude 改稿依頼**だけが右に出ます。",
    "左に改稿全文を貼ると、右列に **ChatGPT 二次評価**用のコピー文が出ます。下の折りたたみは Claude 改稿依頼の再掲。",
    "左に ChatGPT の返答を貼り、点数を入れると分岐：**合格**→ステップ6へ。**不合格**→右に Claude 再改稿用。**未採点（0）**→二次評価のコピー文のみ。",
    "確定稿は左に貼るだけ（右はコピー用テキストなし）。",
    "Claude に貼る **noteタグ生成プロンプト**（確定稿が埋まります）。",
    "選択スタイル（A 実写 / B イラスト・アニメ / C インフォ図解）に応じた **英語の画像生成プロンプト**。",
    "ステップ6 の確定稿が **自動で埋まった** Claude 用シェア生成プロンプト（Markdown）。下に Claude の返答を貼って業務完了。",
]


# ===== 画像プロンプト：3 スタイル =====
IMAGE_STYLE_CHOICES = {
    "A": "A. リアル写真風（実写・ドキュメンタリー）",
    "B": "B. イラスト・アニメ風（フラット／日本アニメ・タッチ）",
    "C": "C. インフォグラフィック図解（横長プロ品質・データ可視化）",
}

IMAGE_COMMON_HEAD = (
    "あなたはビジュアルディレクター兼、画像生成AIへのプロンプト設計者です。\n"
    "次の **確定稿** を読み、**note 記事用のアイキャッチ1枚＋必要な本文挿絵**について、"
    "**画像生成ツール（例: DALL·E 3 / GPT-4o image / Imagen 3 / Recraft V3 / Ideogram 2 / Flux 1.1 Pro 等）**"
    "にそのまま貼って画像を生成するための **英語の画像生成プロンプト**だけを出力してください。\n\n"
)

IMAGE_STYLE_A_BODY = (
    "## スタイル既定（A：リアル写真風／実写ドキュメンタリー）\n"
    "- **写真リアリズム**で、建設・リノベ DX の現場（人物・端末・図面）を **ドキュメンタリー風**に切り取る。\n"
    "- 自然光、シネマティック、35〜50mm 相当の焦点距離、被写界深度浅め、空気感のある粒状感。\n"
    "- 人物は **ジェネリック**（実在個人の顔の精密再現は禁止）。実在ブランドロゴ・OS判読可能 UI は描かない。\n"
    "- アイキャッチ内テキストは **最小限**：(a) 記事タイトル相当の短い日本語、(b) 下部の **必須英語締め `WHAT A WONDERFUL DAY TODAY!`** のみ。長文を画面いっぱいに描かない。\n"
    "- 過剰ネオン SF、安物ストック調、刺激的な広告調は避ける。\n\n"
)

IMAGE_STYLE_B_BODY = (
    "## スタイル既定（B：イラスト・アニメ風／フラット～日本アニメ・タッチ）\n"
    "- **フラットイラスト** または **日本のアニメ風タッチ**（やわらかい線、清潔な色面）。建設・DX を親しみやすく表現。\n"
    "- カラーパレットは白〜薄灰＋ブルー／シアンを基調に、アクセント1色まで。\n"
    "- 人物はジェネリックなアニメ／イラスト調キャラクター。**実在人物の似顔絵は禁止**。\n"
    "- 商標ロゴ・実在アプリ UI の精密再現は禁止（汎用スマホ・タブレット）。\n"
    "- 描き文字は控えめ：アイキャッチでは **短い日本語タイトル相当＋下部の必須英語締め `WHAT A WONDERFUL DAY TODAY!`** のみ。本文挿絵は原則テキストなし。\n\n"
)

IMAGE_STYLE_C_BODY = (
    "## スタイル既定（C：インフォグラフィック図解／横長プロ品質）\n"
    "`prompts/infographic/spec_note_dx_workflow_infographic.md` に相当する **横長プロ品質インフォグラフィック**を既定とする。\n"
    "- 白〜薄灰＋ブルー／シアン。**ヘッダー（主タイトル＋サブ）**／**左→右の 5 ステップフロー**"
    "（現場→スキャン可視→点群3D→AI解析→図面＋端末）／**下部にベネフィット 3 点**＋**締めの一文**＋"
    "**右下隅に必須英語締め `WHAT A WONDERFUL DAY TODAY!`**（記事の必須締めとして本図にも含める）。\n"
    "- **読める日本語キャプション** をレイアウトに含める。確定稿から **見出し・数値・コピーを抽出**し、"
    "英語プロンプト内で **その日本語全文を引用符つきで列挙**（画像に焼き付ける文言として）。\n"
    "- アイコン＋やや立体的な現場／端末。商標ロゴ・実在 UI の精密再現は禁止。人物はジェネリック。\n"
    "- 刺激的な広告調・過剰ネオン SF・安物ストック調は避ける。クリーンな **建設／リノベ DX** の信頼感。\n\n"
)

IMAGE_COMMON_RULES = (
    "## 必須ルール（**サイズ厳守 ＋ 必須英語締めの確実描画 ＋ 余計な英文混入の禁止**）\n"
    "- 出力はすべて **画像を生成するための実行指示**であること。記事の要約や感想だけで終わらせない。\n"
    "- 各ブロックの先頭に **日本語で用途**（例: アイキャッチ／本文挿絵）と、**画像生成AIに貼って生成する**旨を一行で書く。\n"
    "- 続けて **生成サイズと最終サイズ（トリミング前提）**を英語で一行：\n"
    "  `Generate at 1792 × 1024 px (DALL·E 3 native landscape). Final crop to 1280 × 670 px (aspect 1.91:1). Top ~172 px and bottom ~172 px will be cropped. note's actual display further trims ~35 px top and bottom, so keep critical content inside an INNER safe area of 1280 × 600 px (centered).`\n"
    "- その直後に **英語の本編プロンプト**。\n"
    "- **画像内テキスト＝(a) 指定した日本語コピー、(b) 必須英語締め `WHAT A WONDERFUL DAY TODAY!` のみ。**\n"
    "- **必須**：アイキャッチには **右下隅または下部中央** に英語のサインオフ `WHAT A WONDERFUL DAY TODAY!` を **1 行・全大文字・感嘆符 1 個**で必ず描く（記事の必須締めコピーで、本図にも含める）。**スペル・大文字小文字・感嘆符の改変禁止**。位置はクロップ後の 1280×670 セーフエリア内（下端から少し内側）。\n"
    "- 以下のような **意図しない英語フレーズの自動挿入は絶対に行わない**（明示的に禁止）：\n"
    "  - `Hello` / `Welcome` / `Lorem ipsum` / 装飾英単語ステッカー / 透かしロゴ / ランダムな西暦 / `AI` の文字単体 / その他のスローガン。\n"
    "- 英語プロンプト本文に必ず以下を含める（コピー&貼り付け可・改変禁止）：\n"
    "  `Render the brand sign-off \"WHAT A WONDERFUL DAY TODAY!\" as a single line near the bottom-right of the eyecatch, in clean sans-serif uppercase with one exclamation mark, smaller than the main title, fully legible, no spelling errors. This sign-off MUST appear. Do NOT add any other English text — no greetings, slogans, decorative English stickers, watermarks, dates, or filler phrases. Only render the Japanese strings explicitly listed in quotes below plus the brand sign-off above.`\n"
    "- アイキャッチに日本語を入れる場合は **読める大きさ**で、**指定の日本語文字列だけ**を引用符で列挙。\n"
    "- **禁止**：実在ブランドロゴ、OS の判読可能 UI、実在個人の顔の精密再現。\n"
    "- 英語ブロックの末尾に **ツール用比率フラグ**（例: `--ar 1.91:1` / `--ar 3:2` / `--ar 1:1`）を必ず付ける。\n"
    "- **モデル指定行を英語プロンプトの直前に入れる**：\n"
    "  例: `Use the latest model with strong Japanese typography support (DALL·E 3 / GPT-4o image / Imagen 3 / Recraft V3 / Ideogram 2 / Flux 1.1 Pro). Avoid legacy Midjourney for in-image Japanese text.`\n"
    "- 英語プロンプト本文の冒頭に以下を必ず含める（コピー&貼り付け可・改変禁止）：\n"
    "  `Render legible Japanese text exactly as quoted (no romanization, no kanji errors).\n"
    "   Generate at 1792 × 1024 px (DALL·E 3 native landscape).\n"
    "   Two-tier safe area:\n"
    "     - Outer thumbnail area (after first crop to 1.91:1): central 1280 × 670 px.\n"
    "     - INNER must-keep area (note's actual visible region after platform trim): central 1280 × 600 px.\n"
    "   Place ALL text, faces, key icons, and the brand sign-off strictly inside the INNER 1280 × 600 px area.\n"
    "   Treat the top ~207 px and the bottom ~207 px as crop margins — they may be cut off in the final note thumbnail; do not place any critical content (text, logos, key subjects, sign-off) there.`\n\n"
    "## サイズ既定（DALL·E 3 を含む実用方針・**2段セーフエリア**）\n"
    "- **生成サイズ**: 1792 × 1024 px（DALL·E 3 の `landscape` プリセット）\n"
    "- **第1トリミング（自分でやる）**: 中央 1280 × 670 を残し、**上下 各 ~172 px** をカット → これが note の OGP / アイキャッチ標準（1.91:1）。\n"
    "- **第2段セーフエリア（note の実表示で切られる分への保険）**: 中央 **1280 × 600 px** を *絶対セーフエリア* とする。テキスト・顔・主要アイコン・サインオフはすべてここに収める。\n"
    "- **クロップマージン**（重要要素を置かない領域）: 1792×1024 の **上下 各 ~207 px**（172 + 35）。ここは背景・グラデーション・薄い装飾のみ。\n"
    "- 横長挿絵: **1280×853・3:2**\n"
    "- 正方形挿絵: **1280×1280・1:1**\n\n"
    "## 出力の見出し構成（このままの見出し名で出力）\n"
    "### アイキャッチ画像用プロンプト（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**・DALL·E 3 想定）\n"
    "Generate / Crop 行 → 英語プロンプト → `--ar 1.91:1`（最終トリミング後）\n\n"
    "### 本文中の挿絵案 1（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**）\n"
    "用途: （日本語1行） / Size 行 → 英語 → `--ar 3:2`\n\n"
    "### 本文中の挿絵案 2（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**）\n"
    "不要なら見出しだけ残し **「挿絵不要」** と一行。必要なら用途・Size・英語・`--ar 1:1` など。\n\n"
    "### 確定稿（参照。本文は繰り返し出力しない）\n{{STEP6}}\n\n"
    "---\n"
    "上記の構成のみを出力し、**このテキストがそのまま画像生成AIの入力欄に入ること**で画像ができるよう、"
    "英語部分を具体的に（被写体・光・構図・禁止事項）書く。**ここでの出力はチャットのみであり、PNG/JPEG は自動では付かない**。"
    "**利用者が DALL·E 等へ英語プロンプトを貼って「生成」を押す運用である**。\n"
    "**生成後、画像編集ソフトで上下 172 px ずつトリミングして 1280×670 にする運用**を、出力の末尾に1行（日本語）で必ず注記する：\n"
    "「※ DALL·E で 1792×1024 を生成 → 上下 172 px ずつトリミングして 1280×670（1.91:1）にしてから note へアップロード。テキスト・サインオフは中央 1280×600 の内側に収めること（note 表示で上下 ~35 px が削られるため）。」\n"
)


def _image_prompt_for_style(style: str) -> str:
    """A/B/C スタイル別の画像プロンプトテンプレを返す。"""
    body = {
        "A": IMAGE_STYLE_A_BODY,
        "B": IMAGE_STYLE_B_BODY,
        "C": IMAGE_STYLE_C_BODY,
    }.get(style, IMAGE_STYLE_C_BODY)
    return IMAGE_COMMON_HEAD + body + IMAGE_COMMON_RULES


# ===== note タグ作成プロンプト（新ステップ7） =====
NOTE_TAG_PROMPT = (
    "あなたは note の編集者兼 SEO/タグ戦略担当です。次の **確定稿** をもとに、\n"
    "note の検索・回遊・SEOで効くタグを **12〜15個** 提案してください。\n\n"
    "## タグ構成（必ずこの割合で出す）\n"
    "- **大テーマ**: 2〜3個（広い分野・カテゴリ）\n"
    "- **中テーマ**: 3〜5個（記事の中心トピック）\n"
    "- **ニッチ・固有名詞**: 4〜6個（具体的な企業名・技術名・地名など）\n"
    "- **トレンド寄り**: 1〜2個（旬の話題・季節性）\n\n"
    "## ルール\n"
    "- **note で実際に使われているタグ（フォロワー数が多い既存タグ）** を優先する。新規タグは最小限。\n"
    "- ハッシュタグ記号（`#`）は **付けない**（note の入力欄では不要）。\n"
    "- **長すぎるタグ（10字以上）は避ける**。短く検索されやすい表記に。\n"
    "- **過剰に汎用すぎる単語**（例: 「日記」「ビジネス」だけ）は避け、組み合わせや具体性で差別化する。\n"
    "- 同じ意味の重複（例: AI と AI活用）は避ける。\n\n"
    "## 出力形式（このままの表で出力）\n"
    "| # | タグ | 区分 | 採用理由（1行） |\n"
    "|---|------|------|------------------|\n"
    "| 1 | … | 大テーマ | … |\n"
    "| 2 | … | 大テーマ | … |\n"
    "| … | … | … | … |\n\n"
    "## 出力末尾に「コピペ用 1行」を必ず付ける\n"
    "コピペ用（カンマ区切り・最大15個）: タグA, タグB, タグC, …\n\n"
    "## 確定稿（参照。本文は繰り返し出力しない）\n"
    "{{STEP6}}\n"
)


DEFAULT_PROMPTS: list[str] = [
    "",  # 0: ステップ1（_build_step1_prompt で動的構築）
    "## 一次ブログ（Claude の返答全文を貼る運用のメモ）\n",  # 1: 一次記事貼り欄のメモ
    (  # 2: 一次評価（_eval_template_from_repo で初期上書き）
        "以下に一次ブログがある。採点基準に従い評価し、改善点を箇条書きで。\n"
        "（文末の **WHAT A WONDERFUL DAY TODAY!** は執筆方針上の必須締めであり、削除は提案しない。接続が弱いときは前置きを足す旨だけを指示する。）\n\n"
        "---\n{{STEP2}}\n---\n"
    ),
    (  # 3: 改稿依頼（Claude）
        "あなたは note 記事のライターです。次の「一次評価」の指摘をすべて反映し、"
        "一次ブログを **note 向けに改稿**した**全文のみ**を出力してください（前置きや説明は最小に）。\n"
        "執筆ガイドラインどおり文末に **WHAT A WONDERFUL DAY TODAY!** を **省略せず残す**。"
        "評価が接続強化を求める場合は、**その英文の直前**に意味のある日本語を足す。**英文の削除や言い換えはしない**。\n\n"
        "### 一次評価（ChatGPT）\n{{STEP3}}\n\n### 一次ブログ（元稿）\n{{STEP2}}\n"
    ),
    (  # 4: 二次評価（_eval_template_from_repo で初期上書き）
        "以下を評価（0〜100 の根拠つき）。\n"
        "（文末の **WHAT A WONDERFUL DAY TODAY!** は必須締め。**削除提案はしない**。接続強化のみ。）\n\n"
        "---\n{{STEP4}}\n---\n"
    ),
    "手修正後の最終稿を貼る。\n",  # 5: 確定稿（左に本文だけ貼る）
    NOTE_TAG_PROMPT,  # 6: noteタグ生成プロンプト
    _image_prompt_for_style("C"),  # 7: 画像プロンプト（既定 C）
    "",  # 8: シェア（_build_step9_claude_share_markdown で動的構築）
]


# ステップ9：シェア用のリポジトリ標準（`read_prompt_body_for_copy` で front matter 除去）
STEP9_SHARE_PROMPT_REL = "prompts/ops/share_short_from_company.md"


def _responses_for_save() -> list[str]:
    """ディスク保存用（合成は不要、そのまま）。"""
    return list(_all_responses())


def _build_step9_claude_share_markdown() -> str:
    base = read_prompt_body_for_copy(STEP9_SHARE_PROMPT_REL).strip()
    # 最終本文はステップ6の確定稿（resp_5）を直接参照する。
    art = (st.session_state.get("resp_5") or "").strip()
    url = (st.session_state.get("step10_note_url") or "").strip()
    parts: list[str] = []
    parts.append("# Claude 用・シェア文案生成（1 メッセージにそのまま貼る）\n\n")
    if base:
        parts.append("## リポジトリ標準テンプレ\n\n")
        parts.append(base + "\n\n---\n\n")
    parts.append("## 今回の入力（この UI から挿入）\n\n")
    parts.append(f"### note の公開 URL\n{url or '（未入力）'}\n\n")
    parts.append("### 最終版の記事全文（本文）\n\n")
    parts.append(f"{art or '（未入力）'}\n\n")
    parts.append(
        "---\n\n## 依頼（必ずすべて出力／注釈・前置きなし）\n\n"
        "上記の **記事全文** と **公開 URL** に忠実に、標準テンプレの **出力形式** に従い、次を **すべて** 出力してください。"
        "**「投稿前チェック」「注釈」「前置き」は一切出さない**。\n\n"
        "1. **X 向け**: **掲載用 URL 付きの投稿案を3通り**（①②③）。**3通すべて**に上記 **公開 URL** を必ず含める。\n"
        "2. **ハッシュタグ（X 向け）**\n"
        "3. **LinkedIn**: 以下の **固定フォーマットそのまま**で 1 本（前後の注釈・解説なし）\n\n"
        "```\n"
        "English Below\n"
        "[日本語本文：1〜2段落、要点→展開→示唆。約250〜350字目安]\n"
        "[公開URL]\n\n"
        "[英語本文：意味対応の英語短文。約280〜360 characters 目安]\n"
        "[公開URL]\n\n"
        "#日本語タグ1 #日本語タグ2 #日本語タグ3 …（3〜5個）\n"
        "#EnglishTag1 #EnglishTag2 #EnglishTag3 …（5〜8個）\n"
        "```\n\n"
        "※ ハッシュタグは **2行構成**：1行目に日本語タグ、2行目に英語タグ。日本語タグもスペース区切りで `#` を付ける。\n"
        "※ 公開 URL が無い場合のみ、掲載用リンクは **`https://onetech.jp` に統一**してよい。ソースにない事実は足さない。\n"
    )
    return "".join(parts)


# ステップ5で総合が合格点に届かなかったとき、右列に出す Claude 再改稿用（STEP4＝改稿・STEP5＝二次評価の貼り戻し）
DEFAULT_PROMPT_SECOND_FAIL_CLAUDE = (
    "あなたは note 記事のライターです。次の「二次評価（ChatGPT）」の指摘をすべて反映し、\n"
    "現状の改稿を **note 向けにさらに改稿**した**全文のみ**を出力してください（前置きや説明は最小に）。\n"
    "文末の **WHAT A WONDERFUL DAY TODAY!** は **省略せず残す**。接続強化は **直前の日本語** で行い、**英文の削除・言い換えはしない**。\n\n"
    "### 二次評価（ChatGPT）\n{{STEP5}}\n\n### 改稿稿（現状）\n{{STEP4}}\n"
)

# ステップ1で Claude に渡す「対話型で記事を組み立てる」運用指示（材料の後に付与）
STEP1_INTERACTIVE_CLAUDE_FLOW = """
---
## 進め方（必ず守る）

記事本文をいきなり一気に書かないでください。**対話を細かく分けて**、ユーザーの返答を待ってから次へ進んでください。

### 1. タイトル案
- 記事の方向性に沿った**タイトル案をちょうど3つ**提示する。
- それぞれに短いワンポイント（誰向けか・切り口）を付ける。
- ユーザーが **1 / 2 / 3** のいずれかで選ぶまで待つ。選ばれた案を確定タイトルとして以降使う。

### 2. 構成案
- 確定タイトルに基づき、**見出しレベルの構成**（目次相当）を提示する。
- ユーザーが **「OK」** と言うか、修正希望を返すまで待つ。
- 修正があれば構成を直し、再度 OK を取る。

### 3. 追加の打ち合わせ（必要なら）
- トーン（です・ます / である）、想定読者、冒頭のフック、CT の有無など、**判断が割れそうな点を 2〜4 個の選択肢**にして質問する。
- ユーザーが選ぶ（または短く指示する）まで待つ。複数項目ある場合は項目ごとに順に聞いてもよい。

### 4. 本文執筆
- 上記がすべて揃ってから、**一度に全文**を書く。文字数目標があれば尊重する。
- 最後に「この内容で一次記事として確定してよいか」一言確認する。

（ユーザーがこのアプリのステップ2に貼れるよう、**最終的な一次記事全文**をチャット上で提示すること。）
"""

# 評価プロンプトのリポジトリ正本（無いときは DEFAULT_PROMPTS の短文にフォールバック）
_EVAL_REPO_REL = "prompts/review/evaluator_scored_generic.md"


def _prompts_dir() -> Path:
    return repo_root() / "prompts"


def _list_selectable_prompt_files() -> list[str]:
    """標準プロンプト一覧（`sections/` 下の断片は除外して一覧を簡潔に）。"""
    root = _prompts_dir()
    if not root.is_dir():
        return [""]
    found: set[str] = set()
    for p in root.rglob("*.md"):
        if "sections" in p.parts:
            continue
        if p.name in ("README.md", "CHANGELOG.md"):
            continue
        found.add(str(p.relative_to(repo_root())).replace("\\", "/"))
    ordered = sorted(found, key=str.lower)
    return [""] + ordered


def _read_repo_prompt(rel: str) -> str:
    return read_prompt_body_for_copy(rel)


def _default_step1_prompt_rel() -> str:
    order = (
        "prompts/note/dist/note_writer_prompt.md",
        "prompts/social-company-pipeline/01_writer_draft.md",
        "prompts/ops/share_short_from_company.md",
    )
    for cand in order:
        if (repo_root() / cand).is_file():
            return cand
    opts = [x for x in _list_selectable_prompt_files() if x]
    return opts[0] if opts else ""


def _eval_template_from_repo(*, step_macro: str) -> str:
    """リポジトリの評価プロンプト + 評価対象マクロ。"""
    body = _read_repo_prompt(_EVAL_REPO_REL).strip()
    if not body:
        if step_macro == "STEP2":
            return DEFAULT_PROMPTS[2] if len(DEFAULT_PROMPTS) > 2 else ""
        return DEFAULT_PROMPTS[4] if len(DEFAULT_PROMPTS) > 4 else ""
    return (
        body
        + "\n\n---\n\n## 評価対象テキスト（このアプリから自動挿入）\n\n"
        + f"{{{{{step_macro}}}}}\n"
    )


def _slug(s: str) -> str:
    s = (s or "session").strip()
    out = "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:60].strip("-")
    return out or "session"


def _render_for_step(template: str, responses_all: list[str], step_index: int) -> str:
    text = template
    for j in range(len(responses_all)):
        n = j + 1
        text = text.replace(f"{{{{STEP{n}}}}}", responses_all[j] or "")
    prev = responses_all[step_index - 1] if step_index > 0 else ""
    text = text.replace("{{前の出力}}", prev)
    return text


def _all_responses() -> list[str]:
    return [st.session_state.get(f"resp_{j}", "") for j in range(NUM_STEPS)]


def _all_prompts() -> list[str]:
    return [st.session_state.get(f"prompt_{j}", "") for j in range(NUM_STEPS)]


def _save_session(
    *,
    title: str,
    prompts: list[str],
    responses: list[str],
    evaluation: str,
    scores: dict[str, int | None],
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    base = repo_root() / "outputs" / "handoff-sessions" / f"{ts}_{_slug(title)}"
    base.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": title,
        "workflow": "note",
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "steps": NUM_STEPS,
        "pass_threshold_percent": PASS_THRESHOLD,
        "eval_scores_percent": scores,
        "image_style": st.session_state.get("step8_image_style", "C"),
    }
    (base / "00-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    for i in range(NUM_STEPS):
        n = i + 1
        rendered = _render_for_step(prompts[i], responses, i)
        (base / f"step{n:02d}-prompt-template.md").write_text(prompts[i], encoding="utf-8")
        (base / f"step{n:02d}-prompt-for-web.md").write_text(rendered, encoding="utf-8")
        (base / f"step{n:02d}-response-from-web.md").write_text(responses[i], encoding="utf-8")
    if scores:
        (base / "00-scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    # 最終本文はステップ6の確定稿（resp_5）を引き継ぐ。
    confirmed_for_share = (st.session_state.get("resp_5", "") or "")
    t10u = st.session_state.get("step10_note_url", "") or ""
    (base / "step09-share-inputs.md").write_text(
        f"# ステップ9 入力（シェア前・確定稿はステップ6から自動引継ぎ）\n\n"
        f"## note 公開 URL\n{t10u}\n\n"
        f"## 最終版記事全文（= ステップ6 の確定稿）\n\n{confirmed_for_share}\n",
        encoding="utf-8",
    )
    (base / "99-evaluation.md").write_text(evaluation, encoding="utf-8")
    (base / "README.txt").write_text(
        "手動ハンドオフのログ（9段）。\n"
        f"- 評価3・5のスコア: 合格ライン {PASS_THRESHOLD}%。\n"
        "- ステップ7: noteタグ、ステップ8: 画像（A/B/C 選択）、ステップ9: シェア。\n",
        encoding="utf-8",
    )
    return base


def _wiz_step_prev() -> None:
    s = int(st.session_state.get("wiz_step", 0))
    st.session_state["wiz_step"] = max(0, s - 1)


def _wiz_step_next() -> None:
    s = int(st.session_state.get("wiz_step", 0))
    st.session_state["wiz_step"] = min(NUM_STEPS - 1, s + 1)


def _hc_init() -> None:
    st.session_state.setdefault("session_title", "note記事-ワークフロー")
    if st.session_state.get("hc_init"):
        return
    for i in range(NUM_STEPS):
        if i == 2:
            st.session_state["prompt_2"] = _eval_template_from_repo(step_macro="STEP2")
        elif i == 4:
            st.session_state["prompt_4"] = _eval_template_from_repo(step_macro="STEP4")
        elif i == 7:
            st.session_state.setdefault("step8_image_style", "C")
            st.session_state["prompt_7"] = _image_prompt_for_style(
                st.session_state["step8_image_style"]
            )
        else:
            st.session_state[f"prompt_{i}"] = DEFAULT_PROMPTS[i] if i < len(DEFAULT_PROMPTS) else ""
        st.session_state[f"resp_{i}"] = ""
    for i in EVAL_STEP_INDICES:
        st.session_state[f"score_{i}"] = 0
    st.session_state["hc_init"] = True
    st.session_state["wiz_step"] = 0
    st.session_state["evaluation_text"] = ""
    for idx in EVAL_STEP_INDICES:
        st.session_state[f"eval_attempt_{idx}"] = 1
        st.session_state[f"eval_override_{idx}"] = False


def _eval_state_defaults() -> None:
    for idx in EVAL_STEP_INDICES:
        st.session_state.setdefault(f"eval_attempt_{idx}", 1)
        st.session_state.setdefault(f"eval_override_{idx}", False)


def _step1_ui_defaults() -> None:
    st.session_state.setdefault("step1_prompt_rel", _default_step1_prompt_rel())
    st.session_state.setdefault("step1_append_note_interactive", True)
    opts = _list_selectable_prompt_files()
    cur = st.session_state.get("step1_prompt_rel", "")
    if cur and cur not in opts:
        st.session_state["step1_prompt_rel"] = _default_step1_prompt_rel()


def _retry_eval(step_i: int) -> None:
    k = f"eval_attempt_{step_i}"
    cur = int(st.session_state.get(k, 1))
    if cur >= EVAL_MAX_ROUNDS:
        return
    st.session_state[k] = cur + 1
    st.session_state[f"resp_{step_i}"] = ""
    st.session_state[f"score_{step_i}"] = 0


def _override_eval(step_i: int) -> None:
    st.session_state[f"eval_override_{step_i}"] = True


def _build_step1_prompt() -> None:
    """リポジトリの標準プロンプト（選択）＋本UIのカスタム値を結合して LLM に渡す1本の文にする。"""
    rel = (st.session_state.get("step1_prompt_rel") or "").strip()
    base = _read_repo_prompt(rel).strip()
    wish = (st.session_state.get("step1_wishes") or "").strip()
    urls = (st.session_state.get("step1_urls") or "").strip()
    chars = (st.session_state.get("step1_chars") or "").strip()
    article_src = (st.session_state.get("step1_article_source") or "").strip()
    youtube = (st.session_state.get("step1_youtube") or "").strip()
    official = (st.session_state.get("step1_official_url") or "").strip()
    extra = (st.session_state.get("step1_extra_append") or "").strip()
    append_note = bool(st.session_state.get("step1_append_note_interactive", True))

    parts: list[str] = []
    if base:
        parts.append("# 標準プロンプト（リポジトリ `prompts/` の定義）\n\n")
        parts.append(base + "\n\n")
        parts.append("---\n\n")
    parts.append("# 依頼者が本UIで指定した値（自動挿入）\n\n")
    parts.append(f"## テーマ・希望\n{wish or '（未入力）'}\n\n")
    if chars:
        parts.append(f"## 文字数目標\n{chars}\n\n")
    if urls:
        parts.append(f"## 参考URL・リンク\n{urls}\n\n")
    if official:
        parts.append(f"## 公式誘導URL\n{official}\n\n")
    if article_src:
        parts.append(f"## 記事ソース（HTML またはプレーンテキスト）\n\n{article_src}\n\n")
    if youtube:
        parts.append(f"## YouTube（URL またはディスクリプション）\n\n{youtube}\n\n")
    if extra:
        parts.append(f"## 追記の指示（任意）\n\n{extra}\n\n")
    if append_note:
        parts.append("---\n\n# 運用メモ（note 一次記事を対話で進める場合）\n\n")
        parts.append(STEP1_INTERACTIVE_CLAUDE_FLOW.strip() + "\n")
    st.session_state["prompt_0"] = "".join(parts)


def _flash_step2_ok() -> None:
    st.session_state["_flash_ok"] = "一次記事を反映しました。下の文を ChatGPT に貼ってください。"


def _clear_resp3() -> None:
    """貼り欄を空にする（on_click はウィジェット生成前に実行される）。"""
    st.session_state["resp_3"] = ""


def _pull_confirmed_to_share() -> None:
    """確定稿（新ステップ6 = resp_5）をシェア欄の記事全文に取り込む。"""
    st.session_state["step10_article"] = (st.session_state.get("resp_5") or "").strip()


def _save_confirmed_to_resp_5() -> None:
    """ステップ6 の確定稿 widget (_w_resp_5) の値を永続キー resp_5 に同期。
    Streamlit は widget が描画されないステップに移動すると widget key が消えるため、
    永続キー側に保存しておかないと ステップ7/8/9 で「確定稿が空」と誤判定される。
    """
    st.session_state["resp_5"] = st.session_state.get("_w_resp_5", "")


def _on_image_style_change() -> None:
    """画像プロンプトのスタイル切替（A/B/C）。"""
    style = st.session_state.get("step8_image_style", "C")
    st.session_state["prompt_7"] = _image_prompt_for_style(style)


def _hdr_input() -> None:
    st.markdown("#### あなたが入力する")


def _hdr_app_output() -> None:
    st.markdown("#### コピー用の出力")


def _in_spec(text: str) -> None:
    st.caption(f"入力: {text}")


def _out_spec(text: str) -> None:
    st.caption(f"出力: {text}")


def _two_cols():
    return st.columns([1, 1], gap="large")


def _copy_block(
    *,
    title: str,
    body: str,
    file_name: str,
    paste_to: str,
    dl_key: str | None = None,
    next_step: str | None = None,
) -> None:
    """コピーはコード枠のドラッグ選択かダウンロードで。ウィジェット key の削除は行わない（ステップ移動時の不整合を避ける）。"""
    st.markdown(f"**{title}**")
    st.code(body, language="markdown")
    dl_k = dl_key if dl_key else "_dl_" + file_name.replace(".", "_").replace("-", "_")
    st.download_button(
        label=f"{file_name} をダウンロード",
        data=body,
        file_name=file_name,
        key=dl_k,
    )
    if paste_to:
        st.caption(paste_to)
    if next_step:
        st.info(f"**次の作業** — {next_step}")


def main() -> None:
    _hc_init()
    _eval_state_defaults()
    _step1_ui_defaults()
    st.session_state.setdefault("prompt_second_fail_claude", DEFAULT_PROMPT_SECOND_FAIL_CLAUDE)
    st.session_state.setdefault("step10_article", "")
    st.session_state.setdefault("step10_note_url", "")
    st.session_state.setdefault("step8_image_style", "C")

    _flash = st.session_state.pop("_flash_ok", None)
    if _flash:
        st.success(_flash)

    # --- サイドバー（メイン画面とは別ルートでディスク保存） ---
    with st.sidebar:
        st.markdown("### セッション保存")
        st.caption(
            "`outputs/handoff-sessions/` に、各ステップのプロンプト・貼り付け・スコア・メモを書き出します。"
        )
        st.text_input("保存フォルダ名に使うタイトル", key="session_title", placeholder="例: note記事-5月")
        st.text_area(
            "全体メモ（任意・99-evaluation.md）",
            height=96,
            key="evaluation_text",
            help="保存時に同フォルダへ書き込み。未入力でも保存可。",
        )
        if st.button("ログを保存", type="primary", use_container_width=True):
            scores: dict[str, int | None] = {}
            for j in EVAL_STEP_INDICES:
                sk = f"score_{j}"
                if sk in st.session_state:
                    scores[f"step_{j + 1}"] = int(st.session_state[sk])
            path = _save_session(
                title=st.session_state.get("session_title", "") or "session",
                prompts=_all_prompts(),
                responses=_responses_for_save(),
                evaluation=st.session_state.get("evaluation_text", "") or "",
                scores=scores,
            )
            st.success(f"保存しました\n`{path}`")
        with st.expander("テンプレのマクロ（上級）", expanded=False):
            st.caption(
                "各ステップの「テンプレを編集」で使う記法。保存ログにそのまま残ります。"
            )
            st.markdown(
                "| 記法 | 意味 |\n|------|------|\n"
                "| `{{STEP1}}` | ステップ1の貼り戻し |\n"
                "| `{{STEPn}}` | ステップ n の貼り戻し |\n"
                "| `{{前の出力}}` | 直前ステップの貼り戻し |\n"
            )

    st.title("① note記事作成")
    st.info(
        f"評価は **ChatGPT のみ**。合格 **{PASS_THRESHOLD} 点以上**。"
        f" **再評価ボタン**は同一評価ステップで最大 **{EVAL_MAX_ROUNDS} 回**。"
        " ② SNS はハブの別ページ。"
    )
    _in_spec_list = _note_input_specs()
    _nav_list = NOTE_NAV_LABELS
    _head_list = NOTE_HEADINGS

    # --- ステップ移動（コンパクト） ---
    nav = st.columns([4, 1, 1])
    with nav[0]:
        i = st.selectbox(
            "作業中のステップ",
            options=list(range(NUM_STEPS)),
            format_func=lambda j: _nav_list[j],
            key="wiz_step",
            label_visibility="collapsed",
        )
    cur = int(st.session_state.get("wiz_step", 0))
    with nav[1]:
        st.button("◀", disabled=cur <= 0, on_click=_wiz_step_prev, help="記事の上流を直すときなどに戻る")
    with nav[2]:
        st.button("▶", disabled=cur >= NUM_STEPS - 1, on_click=_wiz_step_next, help="次のステップ")

    st.markdown("### " + _head_list[i])
    responses_all = _all_responses()
    pk, rk = f"prompt_{i}", f"resp_{i}"

    # ----- ステップ別 UI（左＝入力、右＝アプリ出力） -----
    if i == 0:
        L, R = _two_cols()
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, 0)
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[0])
            _opts = _list_selectable_prompt_files()
            st.selectbox(
                "標準プロンプト（リポジトリ `prompts/` の .md）",
                options=_opts,
                format_func=lambda p: "（標準ファイルを使わず、下のカスタムだけ）" if not p else p,
                key="step1_prompt_rel",
                help="例: `prompts/social-company-pipeline/01_writer_draft.md` や `prompts/note/dist/note_writer_prompt.md`。ここで選んだファイルの全文が、右に出るプロンプトの土台になります。",
            )
            st.text_area(
                "テーマ・記事に込めたい希望",
                height=100,
                placeholder="例: 〇〇の導入記事／読者は技術責任者／禁則は…",
                key="step1_wishes",
            )
            st.text_input("文字数目標（任意）", placeholder="例: 3000字前後", key="step1_chars")
            st.text_area("参考 URL（任意・1行に1つ）", height=56, key="step1_urls")
            st.text_input("公式誘導 URL（任意）", placeholder="例: https://onetech.jp", key="step1_official_url")
            st.text_area(
                "記事ソース（HTML またはプレーンテキスト・任意）",
                height=80,
                placeholder="評価や執筆の根拠にする記事本文など",
                key="step1_article_source",
            )
            st.text_area(
                "YouTube（URL またはディスクリプション・任意）",
                height=56,
                placeholder="動画 URL またはディスクリプション全文",
                key="step1_youtube",
            )
            st.text_area(
                "追記の指示（任意）",
                height=56,
                placeholder="標準プロンプトに足したい一文や制約",
                key="step1_extra_append",
            )
            st.checkbox(
                "末尾に「note 一次記事・対話モード」の運用指示を付ける",
                key="step1_append_note_interactive",
                help="通常オン。オフにすると対話用の追記指示が付きません。",
            )
            st.button("プロンプトを生成（標準＋カスタムを結合）", type="primary", on_click=_build_step1_prompt)
            with st.expander("結合後のプロンプト全文を直接編集（上級者）", expanded=False):
                st.caption(
                    "ここは `prompt_0`（右列のコードブロックの元テキスト）です。"
                    " 「プロンプトを生成」を押すと **上書き**されるので、直すなら **生成のあと**に触ってください。"
                )
                st.text_area("prompt_0 生テキスト", height=160, key=pk, label_visibility="collapsed")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[0])
            if pr.strip():
                _copy_block(
                    title="Claude に貼る文（標準プロンプト＋カスタム・結合済み）",
                    body=rendered,
                    file_name="step01-for-llm.md",
                    paste_to="**Claude** を開いてください。",
                    next_step="右をすべてコピーし、最初のメッセージとして貼る。一次記事が出たら **ステップ2 左列**に貼る。",
                )
            else:
                st.info("左のフォームを埋め、「プロンプトを生成」を押すと、ここに Claude 用の文が出ます。")

    elif i == 1:
        L, R = _two_cols()
        rs = st.session_state.get(rk, "") or ""
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[1])
            st.caption(
                "ステップ1では Claude と何度かやり取りしてから全文が出ます。確定した一次記事の**本文だけ**を貼ってください。"
            )
            st.text_area(
                "一次記事（Claude の返答全文）",
                height=280,
                key=rk,
                placeholder="ここに貼り付け",
            )
            st.button("一次記事を反映", type="primary", on_click=_flash_step2_ok)
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[1])
            if rs.strip():
                gpt_body = _render_for_step(st.session_state.get("prompt_2", ""), responses_all, 2)
                _copy_block(
                    title="ChatGPT に貼る文(一次評価の依頼)",
                    body=gpt_body,
                    file_name="step03-for-chatgpt.md",
                    paste_to="**ChatGPT**（Web）を開いてください。",
                    next_step="右のブロックをコピーして ChatGPT に貼り、返ってきた評価は **ステップ3 の左列**に貼ります。",
                )
            else:
                st.info("左に一次記事を貼って「一次記事を反映」を押すと、ここに ChatGPT 用の文が出ます。")

    elif i in EVAL_STEP_INDICES:
        tool = "ChatGPT"
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, i)
        sk = f"score_{i}"
        if sk not in st.session_state:
            st.session_state[sk] = 0
        rs = st.session_state.get(rk, "") or ""
        sc = int(st.session_state.get(sk, 0))
        att = int(st.session_state.get(f"eval_attempt_{i}", 1))
        ov = bool(st.session_state.get(f"eval_override_{i}", False))
        if rs.strip() and sc >= PASS_THRESHOLD:
            st.session_state[f"eval_attempt_{i}"] = 1
            st.session_state[f"eval_override_{i}"] = False
        passed = (rs.strip() and sc >= PASS_THRESHOLD) or ov

        L, R = _two_cols()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[i])
            st.caption(
                f"評価ラウンド **{att}** / {EVAL_MAX_ROUNDS}（**再評価ボタン**でカウント）。"
                f" **{PASS_THRESHOLD} 点以上**で次へ。◀ は上流修正用。"
            )
            st.text_area(
                f"{tool} の返答を貼る",
                height=220,
                key=rk,
                placeholder="評価コメントなど全文",
            )
            st.number_input(
                "総合スコア（0〜100）※未採点は 0",
                min_value=0,
                max_value=100,
                step=1,
                key=sk,
            )
            if rs.strip() and sc > 0 and sc < PASS_THRESHOLD and not ov:
                st.warning(
                    f"{PASS_THRESHOLD} 点未満（{sc} 点）です。"
                    f" 同じステップであと **{max(0, EVAL_MAX_ROUNDS - att)}** ラウンド再評価できます。"
                )
                if att < EVAL_MAX_ROUNDS:
                    st.button(
                        "貼り欄と点数をクリアして、ChatGPT で再評価する",
                        on_click=_retry_eval,
                        args=(i,),
                        key=f"btn_retry_eval_{i}",
                    )
                else:
                    st.error(f"{EVAL_MAX_ROUNDS} ラウンド試しても {PASS_THRESHOLD} 点未満です。")
                    st.button(
                        f"{PASS_THRESHOLD} 点未満のまま次に進む（自己責任・ログに残ります）",
                        on_click=_override_eval,
                        args=(i,),
                        key=f"btn_override_eval_{i}",
                    )
            elif passed:
                if ov:
                    st.success("オーバーライドで次に進めます（ウィザードの ▶）。ログに記録されます。")
                else:
                    st.success(f"{sc} 点で合格ラインです。ウィザードの ▶ で次へ進めます。")
            with st.expander("ChatGPT 評価依頼のテンプレを編集（上級者）", expanded=False):
                _m = "{{STEP2}}" if i == 2 else "{{STEP4}}"
                _mv = "一次記事" if i == 2 else "二次ブログ（改稿）"
                st.caption(
                    f"正本はリポジトリ **`{_EVAL_REPO_REL}`** を初期表示しています。"
                    f" マクロ `{_m}` は{_mv}の貼り戻しで置換されます。"
                )
                st.text_area("テンプレ", height=160, key=pk, label_visibility="collapsed")
            if i == 4:
                with st.expander("Claude 再改稿テンプレ（不合格時・右列に表示）", expanded=False):
                    st.caption("`{{STEP4}}`＝ステップ4の改稿、`{{STEP5}}`＝このステップ左に貼った ChatGPT の評価全文")
                    st.text_area(
                        "テンプレ",
                        height=160,
                        key="prompt_second_fail_claude",
                        label_visibility="collapsed",
                    )

        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[i])

            if i == 2:
                if rs.strip():
                    _out_spec("Claude に貼る改稿依頼（一次評価・一次記事が埋まった状態）")
                    claude_revise = _render_for_step(st.session_state.get("prompt_3", ""), responses_all, 3)
                    _copy_block(
                        title="Claude に貼る文（一次評価を反映して改稿）",
                        body=claude_revise,
                        file_name="step04-for-claude.md",
                        paste_to="**Claude**（Web）を開いてください。",
                        next_step="右をコピーして Claude に貼り、返ってきた改稿全文は **ステップ4 の左列**に貼ってください。",
                        dl_key="_dl_step04_claude_revise",
                    )
                else:
                    st.info(
                        "左に ChatGPT の返答を貼ると、ここに **Claude 改稿依頼**が表示されます。"
                        " **一次評価を ChatGPT に依頼する文**は **ステップ2 の右列**からコピーしてください。"
                    )

            elif i == 4:
                ra_r = _all_responses()
                gpt_rendered = _render_for_step(pr, ra_r, i)

                if passed and rs.strip():
                    if ov:
                        st.warning(
                            "オーバーライドにより合格として扱っています。"
                            "ウィザードの ▶ で **ステップ6（確定稿）** に進み、本文を貼ってください。"
                        )
                    else:
                        st.success(
                            f"{sc} 点で合格ライン（{PASS_THRESHOLD} 点以上）です。"
                            "ウィザードの ▶ で **ステップ6（確定稿）** に進み、本文を貼ってください。"
                        )
                    with st.expander("ChatGPT 二次評価の依頼文を再コピー（任意）", expanded=False):
                        _copy_block(
                            title=f"{tool} に貼る文（二次評価・テンプレ）",
                            body=gpt_rendered,
                            file_name="step05-for-chatgpt.md",
                            paste_to=f"必要なときだけ **{tool}** に貼り直してください。",
                            next_step="このステップ左に返答と総合スコアがすでにある場合は再評価不要です。",
                            dl_key="_dl_step05_chatgpt_repeat_passed",
                        )

                elif rs.strip() and sc > 0 and sc < PASS_THRESHOLD and not ov:
                    _out_spec(f"{PASS_THRESHOLD} 点未満：**Claude** に貼って再改稿し、**ステップ4** を差し替えてから再度評価してください")
                    claude_retry = _render_for_step(
                        st.session_state.get("prompt_second_fail_claude", DEFAULT_PROMPT_SECOND_FAIL_CLAUDE),
                        ra_r,
                        4,
                    )
                    _copy_block(
                        title="Claude に貼る文（二次評価を反映して再改稿）",
                        body=claude_retry,
                        file_name="step05-for-claude-revise.md",
                        paste_to="**Claude**（Web）を開いてください。",
                        next_step="返ってきた全文で **ステップ4 左列**を上書きし、再度このステップで ChatGPT に評価してもらってください。",
                        dl_key="_dl_step05_claude_after_fail",
                    )
                    with st.expander("ChatGPT に貼る文（二次評価・テンプレ再コピー）", expanded=False):
                        _copy_block(
                            title=f"{tool} に貼る文",
                            body=gpt_rendered,
                            file_name="step05-for-chatgpt.md",
                            paste_to=f"**{tool}**（Web）を開いてください。",
                            next_step=f"右のブロックをコピーして {tool} に貼り、返答は左列に貼ってください。",
                            dl_key="_dl_step05_chatgpt_repeat_failed",
                        )
                else:
                    _copy_block(
                        title=f"{tool} に貼る文（二次評価）",
                        body=gpt_rendered,
                        file_name="step05-for-chatgpt.md",
                        paste_to=f"**{tool}**（Web）を開いてください。",
                        next_step=f"右のブロックをコピーして {tool} に貼り、返答は左列に貼ってください。",
                        dl_key="_dl_step05_for_chatgpt_main",
                    )
                    if rs.strip() and sc == 0:
                        st.caption(
                            f"総合スコア（右の数値入力）を **1〜100** で入力すると表示が切り替わります。"
                            f" **{PASS_THRESHOLD} 点以上**でステップ6（確定稿）の案内、未満で Claude 再改稿用がメイン表示になります。"
                        )

    elif i == 3:
        L, R = _two_cols()
        pr3 = st.session_state.get("prompt_3", "")
        rendered3 = _render_for_step(pr3, responses_all, 3)
        r1 = (st.session_state.get("resp_1") or "").strip()
        r3 = (st.session_state.get("resp_3") or "").strip()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[3])
            st.caption("**Claude が返した改稿後の本文だけ** を貼ってください（一次記事のまま貼らないでください）。")
            st.button("貼り欄を空にする", on_click=_clear_resp3, key="btn_clear_resp3")
            st.text_area(
                "改稿後の記事全文",
                height=280,
                key=rk,
                placeholder="改稿後の本文をここに貼る",
            )
            if r1 and r3 and r1 == r3:
                st.warning("内容が一次記事（ステップ2）と同じです。改稿後の本文に差し替えてください。")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[3])
            rev_full = (st.session_state.get("resp_3") or "").strip()
            if rev_full:
                # 左列の text_area 実行後の最新の resp_* を使う
                ra_fresh = _all_responses()
                gpt_second = _render_for_step(
                    st.session_state.get("prompt_4", ""),
                    ra_fresh,
                    4,
                )
                _copy_block(
                    title="ChatGPT に貼る文（二次評価・改稿後の記事）",
                    body=gpt_second,
                    file_name="step05-for-chatgpt.md",
                    paste_to="**ChatGPT**（Web）を開いてください。",
                    next_step="右をコピーして ChatGPT に貼り、返答と総合スコアは **ステップ5 の左列**に入力してください。",
                    dl_key="_dl_step04_right_chatgpt_second_eval",
                )
            else:
                st.info("左に **改稿後の記事全文** を貼ると、ここに **ChatGPT 二次評価**用のコピー文が表示されます。")
            with st.expander("Claude 向け・改稿依頼プロンプト（コピー用・再掲）", expanded=False):
                _copy_block(
                    title="Claude に貼る文（一次評価を反映した依頼）",
                    body=rendered3,
                    file_name="step04-for-claude.md",
                    paste_to="未貼のときはここからコピーし、**Claude** に貼ってください。",
                    next_step="改稿がまだなら **Claude** に貼り直し、できた全文を左列に貼ってください。",
                    dl_key="_dl_step04_claude_repeat",
                )
            with st.expander("このステップのテンプレを編集", expanded=False):
                st.text_area("テンプレ", height=160, key=pk, label_visibility="collapsed")

    elif i == 5:
        # ===== ステップ6：確定稿（本文を貼るだけ） =====
        # widget key (_w_resp_5) は描画されない期間に消えるため、永続キー resp_5 を別管理。
        # ステップ6を再訪したら永続キーから widget を復元。
        if "_w_resp_5" not in st.session_state:
            st.session_state["_w_resp_5"] = st.session_state.get("resp_5", "")
        L, R = _two_cols()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[5])
            st.caption("手修正後の **確定稿の本文だけ** を貼ってください。ここから先（タグ・画像・シェア）はこの本文を参照します。")
            st.text_area(
                "確定稿（本文）",
                height=300,
                key="_w_resp_5",
                on_change=_save_confirmed_to_resp_5,
                placeholder="ここに公開前の最終本文を貼る",
            )
            # 貼った直後に永続キーへ同期（on_change が走らないペースト直後対策）。
            _save_confirmed_to_resp_5()
            with st.expander("このステップのテンプレを編集（任意・上級者）", expanded=False):
                st.text_area("prompt_5 テンプレ", height=120, key=pk, label_visibility="collapsed")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[5])
            cur_len = len((st.session_state.get("resp_5") or "").strip())
            if cur_len > 0:
                st.success(f"確定稿を取り込みました（{cur_len} 文字）。ウィザードの ▶ で次へ進めます。")
            st.info(
                "確定稿は右に **コピー用テキストを出しません**。"
                " 次の **ステップ7（noteタグ）** に進むと、ここに貼った本文が自動で組み込まれた Claude 用プロンプトが出ます。"
            )

    elif i == 6:
        # ===== ステップ7：noteタグ作成 =====
        L, R = _two_cols()
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, i)
        confirmed = (st.session_state.get("resp_5") or "").strip()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[6])
            if not confirmed:
                st.warning("**ステップ6 の確定稿が空です。** 先に確定稿を貼ってください。")
            st.text_area(
                "Claude の返答（タグ表とコピペ用1行）",
                height=240,
                key=rk,
                placeholder="Claude が返したタグ表全文を貼る（保存時のログに残ります）",
            )
            with st.expander("このステップのテンプレを編集（任意・上級者）", expanded=False):
                st.caption("`{{STEP6}}` は確定稿の貼り戻しです。")
                st.text_area("テンプレ", height=160, key=pk, label_visibility="collapsed")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[6])
            if confirmed:
                _copy_block(
                    title="Claude に貼る文（noteタグ生成・確定稿が埋まった状態）",
                    body=rendered,
                    file_name="step07-for-claude-tags.md",
                    paste_to="**Claude**（Web）を開いてください。",
                    next_step="右をコピーして Claude に貼り、返ってきたタグ表を左列に貼ってください。コピペ用1行が note の入力欄にそのまま使えます。",
                )
            else:
                st.info("ステップ6 の確定稿が入ると、ここに Claude 用のタグ生成プロンプトが出ます。")

    elif i == 7:
        # ===== ステップ8：画像プロンプト（A/B/C 選択） =====
        # 古い版のテンプレが session に残っている場合は最新版へ自動更新（既存セッション救済）。
        # 「INNER must-keep area」は 2段セーフエリア導入時の固有キーワード。
        cur_prompt_7 = st.session_state.get("prompt_7", "")
        if "INNER must-keep area" not in cur_prompt_7:
            st.session_state["prompt_7"] = _image_prompt_for_style(
                st.session_state.get("step8_image_style", "C")
            )
        L, R = _two_cols()
        confirmed = (st.session_state.get("resp_5") or "").strip()
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, i)
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[7])
            if not confirmed:
                st.warning("**ステップ6 の確定稿が空です。** 先に確定稿を貼ってください。")
            st.radio(
                "画像スタイルを選択",
                options=list(IMAGE_STYLE_CHOICES.keys()),
                format_func=lambda k: IMAGE_STYLE_CHOICES[k],
                key="step8_image_style",
                on_change=_on_image_style_change,
                horizontal=False,
                help="A 実写ドキュメンタリー／B イラスト・アニメ／C インフォ図解（既定）。切り替えると右の英語プロンプトが入れ替わります。",
            )
            st.text_area(
                "返答・メモ（任意：生成したURL や所感）",
                height=160,
                key=rk,
                placeholder="生成した画像のURLや所感など",
            )
            with st.expander("このステップのテンプレを編集（上級者）", expanded=False):
                st.caption("`{{STEP6}}` は確定稿の貼り戻し。スタイルを切り替えるとここも上書きされます。")
                st.text_area("テンプレ", height=200, key=pk, label_visibility="collapsed")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[7])
            st.warning(
                "**このアプリは画像ファイルを生成しません。** 右に出るのは、画像生成サービスへ渡す **英語プロンプト（テキスト）** だけです。"
                " **DALL·E 3 / GPT-4o image / Imagen 3 / Recraft V3 / Ideogram 2 / Flux 1.1 Pro** のプロンプト入力欄にコピーし、"
                "各ツールで **生成（Generate）** を実行してください。PNG/JPEG が欲しい場合は必ず外部ツールが必要です。"
            )
            if rendered.strip() and confirmed:
                style = st.session_state.get("step8_image_style", "C")
                _copy_block(
                    title=f"画像ツールに貼る文（選択: {IMAGE_STYLE_CHOICES[style]}）",
                    body=rendered,
                    file_name=f"step08-for-image-{style}.md",
                    paste_to="画像生成サービスを開いてください（DALL·E 3 推奨）。",
                    next_step="右をコピーして画像ツールに貼り、生成。所感や URL があれば左にメモ。",
                )
            elif not confirmed:
                st.info("ステップ6 の確定稿が入ると、ここに英語プロンプトが出ます。")
            else:
                st.info("スタイルを選ぶと、ここに英語プロンプトが出ます。")

    elif i == 8:
        # ===== ステップ9：シェア文案（確定稿は自動引継ぎ・URL → Claude） =====
        L, R = _two_cols()
        confirmed = (st.session_state.get("resp_5") or "").strip()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[8])
            if confirmed:
                st.success(
                    f"ステップ6 の確定稿（{len(confirmed)} 文字）を自動で引き継ぎました。"
                    "右の Claude プロンプトに埋め込まれます。"
                )
                with st.expander("引き継いだ確定稿の先頭をプレビュー", expanded=False):
                    st.code(confirmed[:600] + ("…" if len(confirmed) > 600 else ""), language="markdown")
            else:
                st.error(
                    "ステップ6 の確定稿が空です。先に **ステップ6** に戻り、確定稿の本文を貼ってください。"
                )
            st.text_input(
                "note の公開 URL",
                key="step10_note_url",
                placeholder="https://note.com/...",
            )
            st.markdown("##### 業務完了：シェア文案の保存")
            st.text_area(
                "**Claude** の返答（X / LinkedIn 文案・ハッシュタグ）全文",
                height=200,
                key=rk,
                placeholder="Claude の出力をそのまま貼るとログ保存時に残ります",
            )
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[8])
            share_md = _build_step9_claude_share_markdown()
            _copy_block(
                title="Claude に貼る文（シェア文案・Markdown 1本／注釈なし）",
                body=share_md,
                file_name="step09-claude-share.md",
                paste_to="**Claude**（Web）を開いてください。",
                next_step="右をすべてコピーし、1 メッセージとして Claude に貼り、返答を左下に貼って **ログ保存**すれば完了です。",
                dl_key="_dl_step09_claude_share_md",
            )


if __name__ == "__main__":
    st.set_page_config(page_title="① note記事作成", layout="wide")
    main()
