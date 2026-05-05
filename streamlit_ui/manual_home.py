"""
マーケ作成ハブ。サイドバーまたは下のリンクから各ページへ。

起動: streamlit run streamlit_ui/manual_home.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="マーケ作成ハブ", layout="wide")

st.title("マーケ作成ハブ")
st.caption("個人用。①note と②SNS は別ページ。")

st.page_link("pages/01_note_handoff.py", label="① note記事作成（評価・10ステップ）", icon="📝")
st.page_link("pages/02_sns_share.py", label="② SNSシェア文案（評価なし・Claudeのみ）", icon="📣")
st.page_link("pages/03_prompt_admin.py", label="プロンプト管理（一覧・編集・プレビュー）", icon="📂")
st.page_link("pages/04_archive.py", label="アーカイブ（保存ログ一覧・閲覧）", icon="🗃️")

st.divider()
st.markdown("ショートカット: ①だけ開くときは `streamlit run streamlit_ui/manual_chain_app.py` でも可。")
