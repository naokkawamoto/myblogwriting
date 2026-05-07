"""
① note記事作成フロー（単体起動可）。ハブは `manual_home.py`。

- ステップ1: `prompts/**/*.md` から標準プロンプト＋カスタム結合。評価は ChatGPT のみ（正本 `prompts/review/evaluator_scored_generic.md`）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from handoff_common import read_prompt_body_for_copy
from ot_marketing.paths import repo_root

NUM_STEPS = 10
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
        "公開前ゲート（**3軸**チェック＋1〜5評価／必須軸の見落とし防止）。",
        "手修正後の確定稿。",
        "画像ツールの結果メモ（なくても可）。",
        "公開直後メモなど（任意・URL メイン運用ならステップ10で記録でも可）。",
        "最終記事・公開 URL・Claude のシェア文案（返答貼り付け）。",
    ]
    return [s0, s1, s2, s3, s4, *tail]


NOTE_NAV_LABELS = [
    "1 希望 → Claude",
    "2 一次記事 → ChatGPT評価",
    "3 一次評価 → Claude改稿",
    "4 改稿を貼る",
    "5 二次評価 → ChatGPT",
    "6 合格メモ",
    "7 確定稿",
    "8 画像",
    "9 公開メモ（任意・短い記録）",
    "10 シェア（稿＋URL→Claude）",
]

NOTE_HEADINGS = [
    "ステップ1　記事の希望",
    "ステップ2　一次記事（Claude）を貼る",
    "ステップ3　一次評価（ChatGPT）を貼る・採点",
    "ステップ4　改稿（Claude）を貼る",
    "ステップ5　二次評価（ChatGPT）",
    "ステップ6　合格判定メモ",
    "ステップ7　確定稿",
    "ステップ8　画像プロンプト → 画像ツール",
    "ステップ9　公開メモ（任意・URL は主にステップ10でも可）",
    "ステップ10　シェア文案（最終稿・URL → Claude）",
]

STEP_OUTPUT_SPEC = [
    "標準プロンプト＋カスタム結合。**Claude** にコピー（ステップ1）。",
    "ChatGPT に貼る「一次評価」依頼の全文（一次記事が埋まります）。",
    "一次評価の依頼文は **ステップ2 の右**でコピー。ここでは左に返答を貼ると **Claude 改稿依頼**だけが右に出ます。",
    "左に改稿全文を貼ると、右列に **ChatGPT 二次評価**用のコピー文が出ます。下の折りたたみは Claude 改稿依頼の再掲。",
    "左に ChatGPT の返答を貼り、点数を入れると分岐：**合格**→ステップ6へ。**不合格**→右に Claude 再改稿用。**未採点（0）**→二次評価のコピー文のみ。",
    "人の **合格判定**：左で **3軸**ごとにチェック＋5段階評価（保存時に表形式で合成）。",
    "画像生成AIに貼る**英語プロンプト**（確定稿参照・生成実行前提の指示）。",
    "（テンプレに応じて出る場合のみ）コピー用テキスト。",
    "（テンプレに応じて出る場合のみ）コピー用テキスト。",
    "左に最終記事＋note URL。右に **Claude 用シェア生成プロンプト（Markdown）**。下に Claude の返答を貼って業務完了。",
]

DEFAULT_PROMPTS: list[str] = [
    "",
    "## 一次ブログ（Claude の返答全文を貼る運用のメモ）\n",
    (
        "以下に一次ブログがある。採点基準に従い評価し、改善点を箇条書きで。\n"
        "（文末の **WHAT A WONDERFUL DAY TODAY!** は執筆方針上の必須締めであり、削除は提案しない。接続が弱いときは前置きを足す旨だけを指示する。）\n\n"
        "---\n{{STEP2}}\n---\n"
    ),
    (
        "あなたは note 記事のライターです。次の「一次評価」の指摘をすべて反映し、"
        "一次ブログを **note 向けに改稿**した**全文のみ**を出力してください（前置きや説明は最小に）。\n"
        "執筆ガイドラインどおり文末に **WHAT A WONDERFUL DAY TODAY!** を **省略せず残す**。"
        "評価が接続強化を求める場合は、**その英文の直前**に意味のある日本語を足す。**英文の削除や言い換えはしない**。\n\n"
        "### 一次評価（ChatGPT）\n{{STEP3}}\n\n### 一次ブログ（元稿）\n{{STEP2}}\n"
    ),
    (
        "以下を評価（0〜100 の根拠つき）。\n"
        "（文末の **WHAT A WONDERFUL DAY TODAY!** は必須締め。**削除提案はしない**。接続強化のみ。）\n\n"
        "---\n{{STEP4}}\n---\n"
    ),
    "ステップ3・5 の点数を見て、90 未満ならどこまで戻るかメモ。\n",
    "手修正後の最終稿を貼る。\n",
    (
        "あなたはビジュアルディレクター兼、画像生成AIへのプロンプト設計者です。\n"
        "次の **確定稿**を読み、**note 記事用のアイキャッチ1枚＋必要な本文挿絵**について、"
        "**画像生成ツール（例: Midjourney / DALL·E / Firefly / SDXL / Imagen 等）にそのまま貼って画像を生成する**ための"
        "**英語の画像生成プロンプト**だけを出力してください。\n\n"
        "## 既定のビジュアル方針（アイキャッチ＝モード C）\n"
        "**アイキャッチ 1 枚は**、`prompts/infographic/spec_note_dx_workflow_infographic.md` に相当する "
        "**横長プロ品質インフォグラフィック**を既定とする（白〜薄灰＋ブルー／シアン、**ヘッダー（主タイトル＋サブ）**／"
        "**左→右の 5 ステップフロー**（現場→スキャン可視→点群3D→AI解析→図面＋端末）／"
        "**下部にベネフィット 3 点**＋**締めの一文**。**読める日本語キャプション**をレイアウトに含める。\n"
        "- 確定稿から **見出し・数値・コピーを抽出**し、英語プロンプト内で **その日本語全文を引用符つきで列挙**（画像に焼き付ける文言として）。\n"
        "- アイコン＋やや立体的な現場／端末。**商標ロゴ・実在アプリ UI の精密再現は禁止**（汎用スマホ・タブレット）。人物はジェネリック（特定の実在個人の顔にしない）。\n"
        "- **刺激的な広告調・過剰ネオンSF・安物ストック調**は避ける。クリーンな **建設／リノベ DX** の信頼感。\n"
        "**本文挿絵**が **シネマティックな一枚絵**向きなら、`spec_note_editorial_cinematic.md` のトーンでもよい（英語プロンプトで明示）。"
        "**汎用 OGP のフラット一枚**がよい場合はユーザーが伝えたときだけ `spec_hero_ogp_infographic.md` に寄せる。\n\n"
        "## 日本語テキスト描画と推奨モデル（重要）\n"
        "- **画像内に読める日本語**を含めるため、**日本語テキスト描画に強いモデル**を最優先で使う：\n"
        "  - **OpenAI ChatGPT の最新画像生成（DALL·E 3 / GPT-4o 画像）**、**Google Imagen 3 以降**、**Recraft V3**、**Ideogram 2.0 以降**、**Flux 1.1 Pro 以降**。\n"
        "  - **Midjourney（〜v6.1）は日本語を文字化けさせやすい**ため、文字焼き付けが必要なアイキャッチには非推奨。Midjourney を使う場合は英語キャプションのみ、または文字なしビジュアルに切り替える。\n"
        "- **必ず各サービスの「最新版モデル」**で生成する（GPT は最新の画像モデル、Midjourney は v7 以降、SD は SD3 以降、Firefly は Image 3 以降）。古いバージョンは選ばない。\n\n"
        "## 必須ルール\n"
        "- 出力はすべて **画像を生成するための実行指示**であること。記事の要約や感想だけで終わらせない。\n"
        "- 各ブロックの先頭に **日本語で用途**（例: アイキャッチ／本文挿絵の説明箇所）と、**画像生成AIに貼って生成する**旨を一行で書く。\n"
        "- 続けて **ピクセルサイズとアスペクト比**を英語で一行（例: `Size: 1280 × 720 px, aspect ratio 16:9`）。\n"
        "- その直後に **英語の本編プロンプト**。アイキャッチ（モード C）では **すべての日本語見出し・数値コピーを引用符で明示**し、読めるタイポサイズとするよう書く。\n"
        "- **禁止**：実在ブランドロゴ、OS の判読可能 UI、実在個人の顔の精密再現。アイキャッチでは **むやみに日本語を省かない**（C 既定）。シネマ挿絵では画像内テキスト原則なしと明記する。\n"
        "- 英語ブロックの末尾に **ツール用比率フラグ**（例: `--ar 16:9` / `--ar 3:2` / `--ar 1:1`）を必ず付ける。\n"
        "- セーフゾーン（四辺の余白）・極小UI禁止を英語で指示する。\n"
        "- **モデル指定行を英語プロンプトの直前に入れる**：例: `Use the latest model with strong Japanese typography support (DALL·E 3 / Imagen 3 / Recraft V3 / Ideogram 2 / Flux 1.1 Pro). Avoid legacy Midjourney for in-image Japanese text.`\n"
        "- 英語プロンプト本文の冒頭に **`Render legible Japanese text exactly as quoted (no romanization, no kanji errors).`** を含める。\n\n"
        "## 出力の見出し構成（このままの見出し名で出力）\n"
        "### アイキャッチ画像用プロンプト（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**）\n"
        "Size 行 → 英語プロンプト → `--ar 16:9`\n\n"
        "### 本文中の挿絵案 1（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**）\n"
        "用途: （日本語1行） / Size 行 → 英語 → `--ar 3:2`\n\n"
        "### 本文中の挿絵案 2（画像生成AIへ貼る・**日本語対応モデル推奨・最新版**）\n"
        "不要なら見出しだけ残し **「挿絵不要」** と一行。必要なら用途・Size・英語・`--ar 1:1` など。\n\n"
        "## サイズの既定（これに合わせる）\n"
        "- アイキャッチ: **1280×720・16:9**\n"
        "- 横長挿絵: **1280×853・3:2**\n"
        "- 正方形挿絵: **1280×1280・1:1**\n\n"
        "### 確定稿（参照。本文は繰り返し出力しない）\n{{STEP7}}\n\n"
        "---\n"
        "上記の構成のみを出力し、**このテキストがそのまま画像生成AIの入力欄に入ること**で画像ができるよう、"
        "英語部分を具体的に（被写体・光・構図・禁止事項）書く。**ここでの出力はチャットのみであり、PNG/JPEG は自動では付かない**。"
        "**利用者が Midjourney 等へ英語プロンプトを貼って「生成」を押す運用である**。\n"
    ),
    "記事 URL・公開日メモを貼る。\n",
    "",
]

# ステップ6：人による公開前ゲート（LLM の採点とは別レイヤ）
# (key, 表示ラベル, ログ保存時「必須」欄／未チェック時の警告対象)
# 運用しやすいよう **3 軸**（④運用・承認はワークフロー外のため省略）
STEP6_GATE_ITEMS = [
    (
        "axis_accuracy",
        "① **正確性・表記** — 事実・数値・固有名詞とソースの整合／誇大・未検証の有無／推測の明示／免責・広告・アフィ等の掲載要件",
        True,
    ),
    (
        "axis_brand_rights",
        "② **ブランド・権利** — トーン・禁則（特定モデル名の露骨指名、不適切な他社言及等）／引用・画像・その他の権利・出典",
        True,
    ),
    (
        "axis_reader",
        "③ **読者・構成** — 読者の誤解がないか／リード・見出し・結論・CTA が本文と整合しているか",
        True,
    ),
]

STEP6_LV_LABELS = {1: "要対応", 2: "不安あり", 3: "継続注意", 4: "概ねOK", 5: "問題なし"}

# ステップ10：シェア用のリポジトリ標準（`read_prompt_body_for_copy` で front matter 除去）
STEP10_SHARE_PROMPT_REL = "prompts/ops/share_short_from_company.md"


def _step6_gate_defaults() -> None:
    for key, _, _ in STEP6_GATE_ITEMS:
        st.session_state.setdefault(f"gate6_chk_{key}", False)
        st.session_state.setdefault(f"gate6_lv_{key}", 3)
    st.session_state.setdefault("step6_extra", "")


def _step6_critical_blockers() -> list[str]:
    """必須扱いの項目で未チェックのラベルを返す（見落とし防止）。"""
    out: list[str] = []
    for key, lbl, mandatory in STEP6_GATE_ITEMS:
        if not mandatory:
            continue
        if not st.session_state.get(f"gate6_chk_{key}", False):
            short = lbl.split("—", 1)[0].strip() if "—" in lbl else lbl[:40]
            out.append(short)
    return out


def _step6_combined_response_text() -> str:
    rows: list[str] = [
        "# ステップ6 合格判定（人チェック結果）",
        "",
        "| 確認 | 評価(1〜5) | 軸（3項目） |",
        "|------|-----------|--------------|",
    ]
    lv_fmt = STEP6_LV_LABELS
    for key, lbl, mandatory in STEP6_GATE_ITEMS:
        ok = bool(st.session_state.get(f"gate6_chk_{key}", False))
        lv = int(st.session_state.get(f"gate6_lv_{key}", 3))
        chk = "☑ 確認済" if ok else "☐ 未確認"
        m = "**必須**" if mandatory else "参考"
        lab = lbl.replace("|", "\\|")
        lv_s = lv_fmt.get(lv, str(lv))
        rows.append(f"| {chk} | {lv}（{lv_s}） [{m}] | {lab} |")
    extras = (st.session_state.get("step6_extra") or "").strip()
    rows.extend(["", "## 追加メモ（自由記述）", extras or "_（なし）_"])
    return "\n".join(rows)


def _responses_for_save() -> list[str]:
    """ディスク保存用。ステップ6はチェックリスト＋追加メモを合成して書き出す。"""
    r = list(_all_responses())
    r[5] = _step6_combined_response_text()
    return r


def _build_step10_claude_share_markdown() -> str:
    base = read_prompt_body_for_copy(STEP10_SHARE_PROMPT_REL).strip()
    art = (st.session_state.get("step10_article") or "").strip()
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
        "---\n\n## 依頼（必ずすべて出力）\n\n"
        "上記の **記事全文** と **公開 URL** に忠実に、標準テンプレの **出力形式**に従い、次を **すべて** 出力してください。\n"
        "1. **X 向け**: **掲載用URL付きの投稿案を3通り**（①②③）。**3通すべて**に上記 **公開 URL** を必ず含める。"
        "　2. **ハッシュタグ（X 向け）**　"
        "3. **LinkedIn 日本語**: **約300字前後**（250〜350字目安）＋必要ならURL1行　"
        "4. **LinkedIn 英語**: **約280〜360 characters** の短文（日本語と意味対応）＋必要ならURL1行　"
        "5. **ハッシュタグ（LinkedIn 向け）**　6. **投稿前チェック**（最大3項）\n"
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
    t10a = st.session_state.get("step10_article", "") or ""
    t10u = st.session_state.get("step10_note_url", "") or ""
    (base / "step10-share-inputs.md").write_text(
        f"# ステップ10 入力（シェア前）\n\n## note 公開 URL\n{t10u}\n\n## 最終版記事全文\n\n{t10a}\n",
        encoding="utf-8",
    )
    (base / "99-evaluation.md").write_text(evaluation, encoding="utf-8")
    (base / "README.txt").write_text(
        "手動ハンドオフのログ（10段）。\n"
        f"- 評価3・5のスコア: 合格ライン {PASS_THRESHOLD}%。\n",
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


def _pull_step7_to_step10() -> None:
    st.session_state["step10_article"] = (st.session_state.get("resp_6") or "").strip()


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
    _step6_gate_defaults()

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
                    title="ChatGPT に貼る文（一次評価の依頼）",
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
                            "ウィザードの ▶ で **ステップ6** に進み、編集・メモを残してください。"
                        )
                    else:
                        st.success(
                            f"{sc} 点で合格ライン（{PASS_THRESHOLD} 点以上）です。"
                            "ウィザードの ▶ で **ステップ6** に進み、あなたの編集・評価メモを記入してください。"
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
                        5,
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
                            f" **{PASS_THRESHOLD} 点以上**でステップ6の案内、未満で Claude 再改稿用がメイン表示になります。"
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
        _step6_gate_defaults()
        L, R = _two_cols()
        blockers = _step6_critical_blockers()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[5])
            st.caption(
                "★ の **3 軸すべて**が公開前の必確認です（未チェックで警告。**保存はブロックしません**）。"
                " 1〜5 は各軸の自己評価（残リスクの把握用）。"
            )
            if blockers:
                st.error(
                    "**必須確認が未チェックです（見落とし防止）**: "
                    + "、".join(blockers)
                    + "。問題なければ左のチェックを入れてください。"
                )
            for key, lbl, mandatory in STEP6_GATE_ITEMS:
                st.divider()
                st.markdown("★ " + lbl)
                st.checkbox("上記を確認した", key=f"gate6_chk_{key}")
                st.select_slider(
                    "自己評価（1〜5）",
                    options=[1, 2, 3, 4, 5],
                    format_func=lambda x, _m=STEP6_LV_LABELS: _m[x],
                    key=f"gate6_lv_{key}",
                )
            st.text_area("追加メモ（自由記述・任意）", height=140, key="step6_extra")
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[5])
            st.info(
                "**人による最終ゲート**です（ChatGPT の点数合格とは別レイヤ）。"
                " **ログ保存**で左の内容が `step06-response-from-web.md` に表形式でまとまります。"
            )
            st.markdown("**保存時プレビュー（合成メモ）**")
            st.code(_step6_combined_response_text(), language="markdown")
            with st.expander("定型以外のメモテンプレを編集（任意・上級者）", expanded=False):
                st.text_area("prompt_5 テンプレ", height=120, key=pk, label_visibility="collapsed")

    elif i == 9:
        L, R = _two_cols()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[9])
            st.caption("未入力なら **ステップ7 の確定稿**をコピーして貼っても構いません。")
            st.button(
                "ステップ7の確定稿をここに取り込む",
                key="btn_step10_pull_step7",
                on_click=_pull_step7_to_step10,
            )
            st.text_area(
                "最終版の記事全文",
                height=260,
                key="step10_article",
                placeholder="公開前の最終本文を貼る",
            )
            st.text_input(
                "note の公開 URL",
                key="step10_note_url",
                placeholder="https://note.com/...",
            )
            st.markdown("##### 業務完了：シェア文案の保存")
            st.text_area(
                "**Claude** の返答（X / LinkedIn 文案・ハッシュタグなど）全文",
                height=200,
                key=rk,
                placeholder="Claude の出力をそのまま貼るとログ保存時に残ります",
            )
        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[9])
            share_md = _build_step10_claude_share_markdown()
            _copy_block(
                title="Claude に貼る文（シェア文案・Markdown 1本）",
                body=share_md,
                file_name="step10-claude-share.md",
                paste_to="**Claude**（Web）を開いてください。",
                next_step="右をすべてコピーし、1 メッセージとして Claude に貼り、返答を左下に貼って **ログ保存**すれば完了です。",
                dl_key="_dl_step10_claude_share_md",
            )

    else:
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, i)
        if i == 7:
            who, cap = "画像ツール", "**画像生成AI**に順に貼り、**画像を生成**してください（英語ブロック＝生成指示）。"
        elif i == 6:
            who, cap = "", ""
        elif i == 8:
            who, cap = "", "公開した note の URL などを左列に貼ってください。"
        else:
            who, cap = "", ""

        L, R = _two_cols()
        with L:
            _hdr_input()
            _in_spec(_in_spec_list[i])
            if i == 8:
                st.caption(
                    "**任意ステップ**です。URL を正本として残すなら **ステップ10** で十分な場合もあります。"
                    " ここでは公開日時・短い所感・社内向け一行メモなどに使えます。"
                )
            st.text_area(
                "返答・メモ",
                height=220,
                key=rk,
                placeholder="Web の返答やメモをここに",
            )
            with st.expander("このステップのテンプレを編集", expanded=False):
                st.text_area("テンプレ", height=160, key=pk, label_visibility="collapsed")
        with R:
            _hdr_app_output()
            if i == 7:
                st.warning(
                    "**このアプリは画像ファイルを生成しません。** 右に出るのは、画像生成サービスへ渡す **英語プロンプト（テキスト）** だけです。"
                    " **Midjourney / DALL·E / Adobe Firefly / Gemini / その他**のプロンプト入力欄にコピーし、"
                    "各ツールで **生成（Generate）** を実行してください。PNG/JPEG が欲しい場合は必ず外部ツールが必要です。"
                )
            if rendered.strip():
                _out_spec(STEP_OUTPUT_SPEC[i])
                if who:
                    _copy_block(
                        title=f"{who} に貼る文",
                        body=rendered,
                        file_name=f"step{i+1:02d}-for-web.md",
                        paste_to=cap,
                        next_step=f"右をコピーして {who} に貼り、結果は左列に貼ってください。",
                    )
                elif i == 6:
                    _copy_block(
                        title="コピー用（任意）",
                        body=rendered,
                        file_name=f"step{i+1:02d}-for-web.md",
                        paste_to="",
                        next_step="必要ならコピーし、左列のメモと照らし合わせてください。",
                    )
                elif i == 8:
                    _copy_block(
                        title="コピー用テキスト（任意）",
                        body=rendered,
                        file_name=f"step{i+1:02d}-for-web.md",
                        paste_to="",
                        next_step="左列に note の URL などを貼ってください。",
                    )
                else:
                    _copy_block(
                        title="コピー用テキスト",
                        body=rendered,
                        file_name=f"step{i+1:02d}-for-web.md",
                        paste_to="",
                        next_step=cap or "右をコピーして使う Web サービスに貼ってください。",
                    )
            elif cap:
                st.caption(cap)
                st.info("このステップでは右にコピー用テキストは出ません。左列だけで進めます。")
            else:
                st.info("このステップでは右にコピー用テキストは出ません。左列だけで進めます。")



if __name__ == "__main__":
    st.set_page_config(page_title="① note記事作成", layout="wide")
    main()
