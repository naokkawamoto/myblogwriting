"""プロンプト一覧・編集・プレビュー（ディスク同期）。"""

from __future__ import annotations

import subprocess

import streamlit as st

from handoff_common import list_selectable_prompt_files, parse_front_matter, read_repo_prompt
from ot_marketing.paths import repo_root

st.set_page_config(page_title="プロンプト管理", layout="wide")

st.title("プロンプト管理")
st.caption("`prompts/` の `.md` を一覧・編集します（sections/README/CHANGELOG は一覧対象外と同じルール）。")

_opts = [p for p in list_selectable_prompt_files() if p]
if not _opts:
    st.error("`prompts/` が見つかりません。")
    st.stop()

st.session_state.setdefault("prompt_admin_rel", _opts[0])


def _reload_editor() -> None:
    rel = st.session_state.get("prompt_admin_rel") or _opts[0]
    body = read_repo_prompt(rel)
    st.session_state["prompt_admin_edit_box"] = body


rel_sel = st.selectbox(
    "ファイル",
    options=_opts,
    key="prompt_admin_rel",
    on_change=_reload_editor,
)

# 初回ロード
if "prompt_admin_edit_box" not in st.session_state or st.session_state.get("_prompt_admin_last_rel") != rel_sel:
    st.session_state["prompt_admin_edit_box"] = read_repo_prompt(rel_sel)
    st.session_state["_prompt_admin_last_rel"] = rel_sel

raw_edit = st.text_area(
    "編集（UTF-8）",
    height=420,
    key="prompt_admin_edit_box",
)

meta, body_only = parse_front_matter(raw_edit)
if meta:
    with st.expander("Front matter（ざっくりパース）", expanded=False):
        st.json({k: (list(v) if isinstance(v, list) else v) for k, v in meta.items()})

col_a, col_b = st.columns(2)
with col_a:

    def _save_file() -> None:
        text = st.session_state.get("prompt_admin_edit_box") or ""
        p = repo_root() / rel_sel.replace("\\", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        st.session_state["_prompt_admin_saved"] = str(p)

    st.button("ディスクに保存", type="primary", on_click=_save_file)

with col_b:
    if cmd_out := st.session_state.pop("_prompt_admin_saved", None):
        st.success(f"保存しました `{cmd_out}`")

hist_md = ""
try:
    r = subprocess.run(
        ["git", "log", "-n", "5", "--oneline", "--", rel_sel],
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if r.stdout.strip():
        hist_md = "```text\n" + r.stdout.strip() + "\n```"
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass

with st.expander("プレビュー（本文のみ・front matter 除去後）", expanded=False):
    st.markdown(body_only[:120000] or "_(空)_")

with st.expander("git log（直近・このファイル）", expanded=False):
    if hist_md:
        st.markdown(hist_md)
    else:
        st.caption("git が無い、または履歴がありません。")

st.markdown(
    "- **タグ・①②**: 各 `.md` の YAML front matter に `workflows: [note]` のように書く運用を推奨。\n"
    "- **`WORKFLOW_PROMPTS.md` の再生成**: `python scripts/gen_workflow_prompts.py`"
)
