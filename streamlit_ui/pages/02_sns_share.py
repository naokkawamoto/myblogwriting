"""② SNSシェア文案（評価なし・Claudeのみ）。"""

from __future__ import annotations

import streamlit as st

from handoff_common import (
    list_selectable_prompt_files,
    read_prompt_body_for_copy,
    save_sns_session,
)

st.set_page_config(page_title="② SNSシェア", layout="wide")

DEFAULT_PROMPT_REL = "prompts/ops/share_short_from_company.md"


def _build_prompt() -> None:
    rel = (st.session_state.get("sns_prompt_rel") or "").strip() or DEFAULT_PROMPT_REL
    base = read_prompt_body_for_copy(rel).strip()
    pts = (st.session_state.get("sns_share_points") or "").strip()
    url = (st.session_state.get("sns_content_url") or "").strip()
    body = (st.session_state.get("sns_content_body") or "").strip()
    yt_url = (st.session_state.get("sns_yt_url") or "").strip()
    yt_txt = (st.session_state.get("sns_yt_text") or "").strip()

    parts: list[str] = []
    if base:
        parts.append("# 標準プロンプト（リポジトリ）\n\n")
        parts.append(base + "\n\n")
        parts.append("---\n\n")
    parts.append("# 依頼者が本UIで指定した値\n\n")
    parts.append(f"## シェアしたい要点（1〜3文）\n{pts or '（未入力）'}\n\n")
    parts.append(f"## URL（あれば）\n{url or '（未入力）'}\n\n")
    parts.append(f"## テキスト／HTML（URLが無い場合など）\n\n{body or '（未入力）'}\n\n")
    parts.append("## YouTube\n")
    parts.append(f"- 動画URL: {yt_url or 'なし'}\n")
    parts.append(f"- ディスクリプション等:\n\n{yt_txt or '（未入力）'}\n\n")
    parts.append(
        "---\n\n## 出力の指定（漏れなく）\n"
        "- **X**: 投稿文＋掲載用URL\n"
        "- **LinkedIn**: **日本語** と **英語** のシェア文それぞれ＋URL\n"
        "- **ハッシュタグ**: X用・LinkedIn用を別ブロックで（標準プロンプトの指示に従う）\n"
    )
    st.session_state["sns_prompt_built"] = "".join(parts)


def _save_sns_clicked() -> None:
    title = (st.session_state.get("sns_session_title") or "sns-session").strip()
    prompt_text = st.session_state.get("sns_prompt_built") or ""
    resp = st.session_state.get("sns_claude_response") or ""
    memo = st.session_state.get("sns_eval_memo") or ""
    if not prompt_text.strip():
        st.session_state["_sns_flash"] = "先にプロンプトを生成してください。"
        return
    path = save_sns_session(
        title=title,
        prompt_text=prompt_text,
        response_text=resp,
        evaluation=memo,
    )
    st.session_state["_sns_flash_ok"] = str(path)


st.title("② SNSシェア文案")
st.caption("評価なし。**Claude** にだけコピペ。**note の評価・改稿テンプレは使いません**。")

_flash_ok = st.session_state.pop("_sns_flash_ok", None)
_flash_er = st.session_state.pop("_sns_flash", None)
if _flash_ok:
    st.success(f"保存しました\n`{_flash_ok}`")
if _flash_er:
    st.warning(_flash_er)

st.session_state.setdefault("sns_prompt_rel", DEFAULT_PROMPT_REL)

_opts = list_selectable_prompt_files()
cur_rel = st.session_state.get("sns_prompt_rel", "")
if cur_rel not in _opts and _opts:
    st.session_state["sns_prompt_rel"] = DEFAULT_PROMPT_REL if DEFAULT_PROMPT_REL in _opts else _opts[1]

with st.sidebar:
    st.markdown("### SNSセッション保存")
    st.caption("`outputs/handoff-sessions/` の `_sns` サフィックス付きフォルダへ。")
    st.text_input("保存タイトル", key="sns_session_title", placeholder="例: ニュースシェア-5月")
    st.text_area("メモ（任意・99-evaluation.md）", height=72, key="sns_eval_memo")
    st.button("ログを保存", type="primary", on_click=_save_sns_clicked, use_container_width=True)

col_l, col_r = st.columns(2, gap="large")

with col_l:
    st.markdown("#### 入力")
    st.selectbox(
        "標準プロンプト `.md`",
        options=[x for x in _opts if x],
        format_func=lambda p: p,
        key="sns_prompt_rel",
    )
    st.text_area(
        "シェアしたい要点（1〜3文）",
        height=100,
        key="sns_share_points",
        placeholder="今回伝えたいこと・読者・トーン",
    )
    st.text_input("コンテンツ URL（任意）", key="sns_content_url", placeholder="https://…")
    st.text_area("記事テキスト／HTML（任意）", height=120, key="sns_content_body")
    st.text_input("YouTube URL（任意）", key="sns_yt_url")
    st.text_area("YouTube ディスクリプション（任意）", height=72, key="sns_yt_text")
    st.button("プロンプトを生成", type="primary", on_click=_build_prompt)

with col_r:
    st.markdown("#### Claude に貼るプロンプト")
    pb = st.session_state.get("sns_prompt_built") or ""
    if pb.strip():
        st.code(pb, language="markdown")
        st.download_button("prompt をダウンロード", pb, file_name="sns-for-claude.md")
    else:
        st.info("左で入力して「プロンプトを生成」")

st.divider()
st.text_area(
    "Claude の返答（X／LinkedIn 文案・URL・ハッシュタグなど全文）",
    height=320,
    key="sns_claude_response",
    placeholder="ここに Claude の出力全文を貼る",
)
