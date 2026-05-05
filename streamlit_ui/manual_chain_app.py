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
        "合格判定・戻り先メモ。",
        "手修正後の確定稿。",
        "画像ツールの結果メモ（なくても可）。",
        "公開した note の URL・日付メモ。",
        "シェア文案（Claude の返答）。",
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
    "9 note公開メモ",
    "10 シェア文案",
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
    "ステップ9　note URL・公開メモ",
    "ステップ10　シェア文案",
]

STEP_OUTPUT_SPEC = [
    "標準プロンプト＋カスタム結合。**Claude** にコピー（ステップ1）。",
    "ChatGPT に貼る「一次評価」依頼の全文（一次記事が埋まります）。",
    "まず ChatGPT 用の評価依頼全文。返答を貼ったあと、条件が揃えば続けて Claude 向けの改稿依頼全文も出ます。",
    "（主に折りたたみ内）Claude 向けの改稿依頼プロンプト（評価・元稿が埋まった状態）。",
    "ChatGPT に貼る「二次評価」依頼の全文。",
    "メモ用テンプレ（コピーは任意）。",
    "画像生成用プロンプト（確定稿が参照されます）。",
    "（テンプレに応じて出る場合のみ）コピー用テキスト。",
    "（テンプレに応じて出る場合のみ）コピー用テキスト。",
    "Claude に貼るシェア文案用プロンプト全文。",
]

DEFAULT_PROMPTS: list[str] = [
    "",
    "## 一次ブログ（Claude の返答全文を貼る運用のメモ）\n",
    (
        "以下に一次ブログがある。採点基準に従い評価し、改善点を箇条書きで。\n\n"
        "---\n{{STEP2}}\n---\n"
    ),
    (
        "あなたは note 記事のライターです。次の「一次評価」の指摘をすべて反映し、"
        "一次ブログを **note 向けに改稿**した**全文のみ**を出力してください（前置きや説明は最小に）。\n\n"
        "### 一次評価（ChatGPT）\n{{STEP3}}\n\n### 一次ブログ（元稿）\n{{STEP2}}\n"
    ),
    "以下を評価（0〜100 の根拠つき）。\n\n---\n{{STEP4}}\n---\n",
    "ステップ3・5 の点数を見て、90 未満ならどこまで戻るかメモ。\n",
    "手修正後の最終稿を貼る。\n",
    (
        "あなたはビジュアルディレクターです。次の確定稿を読み、**note 向けの画像生成用プロンプト**を英語で出力してください。\n\n"
        "## 画像サイズ・比率（note 記事での表示を想定・必ず明記）\n"
        "- **アイキャッチ（タイトル直下）**: **横 1280 × 縦 720 px（16:9）** を既定。横長で、極端な縦長（9:16 等）は使わない。\n"
        "- **本文中の挿絵**が必要な場合は用途ごとに **横 1280 × 縦 853（3:2）** または **1280 × 1280（1:1）** を指定し、どれがアイキャッチか分かるように書く。\n"
        "- 実際の生成ツールの指定に合わせ、末尾に **aspect ratio / --ar 16:9** 等を追記してよい。\n"
        "- 文字・ロゴを載せる場合は四辺に余白（セーフゾーン）。細線・極小文字は避ける。\n\n"
        "### 確定稿（参照）\n{{STEP7}}\n\n"
        "---\n（このプロンプトを画像ツールに貼ったあと、結果メモを下の貼り欄に残す運用でもよい）\n"
    ),
    "記事 URL・公開日メモを貼る。\n",
    "URL: {{STEP9}}\n要約:\n{{STEP7}}\n",
]

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
                responses=_all_responses(),
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

        with R:
            _hdr_app_output()
            _out_spec(STEP_OUTPUT_SPEC[i])
            _copy_block(
                title=f"{tool} に貼る文",
                body=rendered,
                file_name=f"step{i+1:02d}-for-chatgpt.md",
                paste_to=f"**{tool}**（Web）を開いてください。",
                next_step=f"右のブロックをコピーして {tool} に貼り、返答は左列に貼ってください。",
            )
            if i == 2 and rs.strip():
                _out_spec("Claude に貼る改稿依頼（評価・一次記事が埋まった状態）")
                claude_revise = _render_for_step(st.session_state.get("prompt_3", ""), responses_all, 3)
                _copy_block(
                    title="Claude に貼る文（一次評価を反映して改稿）",
                    body=claude_revise,
                    file_name="step04-for-claude.md",
                    paste_to="**Claude**（Web）を開いてください。",
                    next_step="右のブロックをコピーして Claude に貼り、返ってきた改稿全文は **ステップ4 の左列**に貼ってください。",
                    dl_key="_dl_step04_claude_revise",
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

    else:
        pr = st.session_state.get(pk, "")
        rendered = _render_for_step(pr, responses_all, i)
        if i == 7:
            who, cap = "画像ツール", "**画像生成ツール**に貼り付けてください。"
        elif i == 9:
            who, cap = "Claude", "**Claude**（ブラウザ）に貼り付けてください。"
        elif i == 5:
            who, cap = "", ""
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
                elif i in (5, 6):
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
