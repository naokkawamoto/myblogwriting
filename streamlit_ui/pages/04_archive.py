"""保存済みハンドオフログの一覧・閲覧（読むだけ）。"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ot_marketing.paths import repo_root

st.set_page_config(page_title="アーカイブ", layout="wide")

st.title("アーカイブ")
st.caption("`outputs/handoff-sessions/` のフォルダを一覧します（読むだけ）。")

_root = repo_root() / "outputs" / "handoff-sessions"
if not _root.is_dir():
    st.warning("`outputs/handoff-sessions/` がありません。まず各フローで保存してください。")
    st.stop()

_sessions: list[dict[str, object]] = []
for d in sorted(_root.iterdir(), key=lambda p: p.name, reverse=True):
    if not d.is_dir():
        continue
    meta_path = d / "00-meta.json"
    meta: dict[str, object] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    wf = meta.get("workflow")
    if not wf:
        wf = "sns" if d.name.endswith("_sns") else "note"
    scores = meta.get("eval_scores_percent") or meta.get("eval_scores") or {}
    title = meta.get("title", d.name)
    saved = meta.get("saved_at_utc", "")
    note_url = ""
    sr = d / "step09-response-from-web.md"
    if sr.is_file():
        note_url = (sr.read_text(encoding="utf-8") or "").strip()[:400]

    _sessions.append(
        {
            "dir": str(d.relative_to(repo_root())),
            "title": title,
            "workflow": wf,
            "saved_at": saved,
            "scores": scores,
            "url_memo_excerpt": note_url,
        }
    )

if not _sessions:
    st.info("まだセッションがありません。")
    st.stop()

st.dataframe(
    [
        {
            "保存時刻(UTC表記)": str(s["saved_at"])[:19],
            "タイトル": s["title"],
            "ワークフロー": s["workflow"],
            "スコア": str(s["scores"])[:120],
            "フォルダ": s["dir"],
        }
        for s in _sessions
    ],
    use_container_width=True,
)

pick = st.selectbox(
    "詳細を開く",
    options=list(range(len(_sessions))),
    format_func=lambda i: f'{_sessions[i]["title"]} ({_sessions[i]["workflow"]})',
)

sel = _sessions[pick]
st.subheader(sel["title"])
st.text(sel["dir"])
if sel["scores"]:
    st.json(sel["scores"])
if sel["url_memo_excerpt"]:
    with st.expander("ステップ9 貼り付け冒頭（URL メモ）", expanded=False):
        st.text(sel["url_memo_excerpt"])

pdir = repo_root() / str(sel["dir"]).replace("\\", "/")
sub_files = sorted([f for f in pdir.iterdir() if f.is_file()], key=lambda x: x.name)
choice_f = st.selectbox(
    "ファイルを読む",
    options=sub_files,
    format_func=lambda f: f.name,
)
body = choice_f.read_text(encoding="utf-8") if choice_f.is_file() else ""
st.code(body[:200000] or "(空)", language="markdown")
