"""
ローカル Web UI（Streamlit・API 経由で生成）。リポジトリルートで:
  streamlit run streamlit_ui/api/streamlit_app.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st

from ot_marketing.env_load import bootstrap_env, secrets_toml_path, write_api_secrets_toml
from ot_marketing.llm import complete, default_model
from ot_marketing.local_llm import complete_openai_compatible_local, normalize_openai_compat_base_url
from ot_marketing.output_store import write_markdown_output
from ot_marketing.paths import repo_root
from ot_marketing.workflows import build_note_user_message, build_share_user_message, dist_note_exists


def _render_api_error(e: BaseException, *, backend: str) -> None:
    """ユーザー向けに API 失敗を説明する（長い Traceback は出さない）。"""
    msg = str(e)
    low = msg.lower()
    if backend == "local":
        extra = ""
        if "connection" in low or "connect" in low or "refused" in low or "name or service" in low:
            extra = (
                "\n**よくある原因**: Ollama が **未起動**（メニューバーに羊アイコンが無い／`ollama serve` が動いていない）、"
                "または **ポート 11434** が別アプリに占有されている。\n"
            )
        st.error(
            "**ローカル（OpenAI互換）接続エラー**です。"
            + extra
            + "\n**確認手順（Ollama）**\n"
            "1. [Ollama](https://ollama.com/) をインストールし、アプリを起動する（またはターミナルで `ollama serve`）。\n"
            "2. ターミナルで `ollama pull llama3.2`（プロファイル A のモデル名に合わせる）。\n"
            "3. サイドバー **「接続テスト（Ollama の場合）」** を押し、成功するか確認する。\n"
            "4. **LM Studio** のときは、ローカルサーバーを起動し、表示された **Base URL** を「A: ベースURL」に貼る。\n\n"
            f"（例外の種類: `{type(e).__name__}`） 技術メッセージ: `{msg}`"
        )
        return
    if backend == "openai" and (
        "insufficient_quota" in low
        or "exceeded your current quota" in low
        or ("429" in msg and "quota" in low)
    ):
        st.error(
            "**OpenAI: 利用枠・課金の問題です**（`429` / `insufficient_quota`）。\n\n"
            "- アカウントの **プラン・請求・クレジット残高** を [OpenAI の Billing](https://platform.openai.com/settings/organization/billing) で確認してください。\n"
            "- 無料枠の消費切れ・支払い未設定・組織の上限に達しているとよく出ます。\n"
            "- **API 無しで試す**: 接続先を **ローカル（OpenAI互換）** に切り替え（Ollama / LM Studio）。"
        )
    elif backend == "openai" and (
        "invalid_api_key" in low or "incorrect api key" in low or "authentication" in low
    ):
        st.error(
            "**OpenAI: APIキーが無効**の可能性です。Platform でキーを再発行し、サイドバーの「APIキーを登録」か `.env` を更新してください。"
        )
    elif backend == "anthropic" and (
        "credit balance is too low" in low
        or "purchase credits" in low
        or "plans & billing" in low
    ):
        st.error(
            "**Anthropic: クレジット残高が不足**しています（`400` / 課金関連）。\n\n"
            "- [Anthropic Console — Plans & Billing](https://console.anthropic.com/settings/plans) で **プランの確認・クレジット購入**を行ってください。\n"
            "- **API 無しで試す**: 接続先を **ローカル（OpenAI互換）** に切り替え（Ollama / LM Studio）。"
        )
    else:
        st.error(f"**{backend}** の API でエラーが返りました。\n\n```\n{msg}\n```")


def _run_llm(
    *,
    user: str,
    system: str,
    tag: str,
    output_basename: str,
    transport: str,
    cloud_provider: str,
    cloud_model_in: str,
    local_base_url: str,
    local_model: str,
    local_api_key: str,
) -> Optional[tuple[str, str, Path]]:
    try:
        if transport == "local":
            root = normalize_openai_compat_base_url(local_base_url)
            m = local_model.strip()
            if not m:
                st.error("ローカル用のモデル名を入力してください。")
                return None
            label = f"local {root} / {m}"
            with st.spinner(f"ローカル推論: {m} …"):
                text = complete_openai_compatible_local(
                    base_url=root,
                    model=m,
                    system=system,
                    user=user,
                    api_key=local_api_key.strip() or "ollama",
                )
        else:
            m = cloud_model_in.strip() or default_model(cloud_provider)  # type: ignore[arg-type]
            label = f"{cloud_provider} / {m}"
            with st.spinner(f"{label} を呼び出しています…"):
                text = complete(
                    provider=cloud_provider,  # type: ignore[arg-type]
                    model=m,
                    system=system,
                    user=user,
                )
    except Exception as e:  # noqa: BLE001
        _render_api_error(e, backend=("local" if transport == "local" else cloud_provider))
        return None
    path = write_markdown_output(
        basename=output_basename or "web-draft",
        body=text,
        extra_header=f"{tag} {label}",
        source="streamlit",
    )
    return text, m, path


bootstrap_env()

st.set_page_config(page_title="OT Marketing（ローカル）", layout="wide")
st.title("One Technology Japan — マーケ下書き（ローカル）")
st.caption(
    "接続先: **クラウド**（OpenAI / Anthropic・APIキー）または **ローカル**（Ollama / LM Studio 等の **OpenAI互換HTTP**・クラウドキー不要）。"
    " ※「ChatGPT / Claude」本体の公式モデルがローカルで動くわけではなく、**お使いのローカルモデル**に置き換えます。"
)

with st.sidebar:
    st.header("接続")
    transport = st.radio(
        "モード",
        ["cloud", "local"],
        index=0,
        format_func=lambda x: (
            "クラウド（OpenAI / Anthropic）" if x == "cloud" else "ローカル（OpenAI互換・APIキー不要）"
        ),
        help="ローカルは Ollama・LM Studio など、OpenAI 互換の `/v1/chat/completions` を提供するサーバ向けです。",
    )

    cloud_provider = "openai"
    cloud_model_in = ""
    local_base_url = "http://127.0.0.1:11434/v1"
    local_model = "llama3.2"
    local_api_key = "ollama"

    if transport == "cloud":
        st.subheader("クラウド API")
        cloud_provider = st.selectbox("プロバイダ", ["openai", "anthropic"], index=0)
        _default_m = default_model(cloud_provider)  # type: ignore[arg-type]
        cloud_model_in = st.text_input(
            "モデル ID（空なら既定）",
            value="",
            placeholder=_default_m,
            help=f"未入力時は `{_default_m}`（環境変数 OTM_*_MODEL で上書き可）",
        )
        _has_oa = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        _has_an = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        st.caption(
            f"キー状態: OpenAI={'設定済み' if _has_oa else '未設定'} / Anthropic={'設定済み' if _has_an else '未設定'}"
        )
        with st.expander("APIキーを登録（このPCに保存）", expanded=not (_has_oa and _has_an)):
            st.markdown(
                f"保存先: `{secrets_toml_path()}`（**.gitignore 済み**。Git に乗りません）"
            )
            _oa_in = st.text_input("OpenAI API Key", type="password", key="reg_openai")
            _an_in = st.text_input("Anthropic API Key", type="password", key="reg_anthropic")
            if st.button("APIキーを保存", type="primary"):
                oa = _oa_in.strip() or None
                an = _an_in.strip() or None
                if oa is None and an is None:
                    st.warning("どちらか一方以上、入力してから保存してください。")
                else:
                    p = write_api_secrets_toml(openai_key=oa, anthropic_key=an)
                    st.success(f"保存しました。次回起動からも有効です: `{p}`")
                    st.rerun()
    else:
        st.subheader("ローカル（OpenAI互換）")
        st.markdown(
            "**プロファイル A / B** で URL・モデルを切り替えます（例: A を対話寄り、B を長文寄りのモデル名にする等）。"
        )
        with st.expander("プロファイル A（例: ChatGPT用ローカル）", expanded=True):
            url_a = st.text_input("A: ベースURL", value="http://127.0.0.1:11434/v1", key="loc_url_a")
            model_a = st.text_input("A: モデル名", value="llama3.2", key="loc_model_a")
        with st.expander("プロファイル B（例: Claude用ローカル）", expanded=False):
            url_b = st.text_input("B: ベースURL", value="http://127.0.0.1:11434/v1", key="loc_url_b")
            model_b = st.text_input("B: モデル名", value="mistral", key="loc_model_b")
        profile = st.radio(
            "いま使うプロファイル",
            ["a", "b"],
            index=0,
            format_func=lambda x: "A（左の設定）" if x == "a" else "B（右の設定）",
            horizontal=True,
        )
        if profile == "a":
            local_base_url, local_model = url_a, model_a
        else:
            local_base_url, local_model = url_b, model_b
        local_api_key = st.text_input(
            "互換サーバ用の API キー欄",
            value="ollama",
            help="Ollama は多くの場合 `ollama` で可。LM Studio の要求に合わせて変更してください。",
        )
        st.caption(f"いまの接続先（推論）: `{normalize_openai_compat_base_url(local_base_url)}` / モデル `{local_model}`")

        if st.button("接続テスト（Ollama の場合）", help="ベースURLのホストへ /api/tags を GET します（LM Studio では失敗することがあります）"):
            import urllib.error
            import urllib.request

            root = normalize_openai_compat_base_url(local_base_url)
            host = root.rsplit("/v1", 1)[0]
            probe = f"{host}/api/tags"
            try:
                with urllib.request.urlopen(probe, timeout=5) as resp:
                    _ = resp.read(2048)
                st.success(f"**Ollama らしき応答**がありました: `{probe}`。このあと「note を生成」を再試行してください。")
            except urllib.error.HTTPError as he:
                st.warning(f"HTTP `{he.code}`: `{probe}`（URL は合っているが Ollama 以外の可能性）")
            except urllib.error.URLError as ue:
                st.error(
                    f"**TCP 接続できません**: `{probe}`\n\n`{ue.reason or ue}`\n\n"
                    "→ Ollama を起動するか、LM Studio なら **ローカルサーバー起動** と **正しいポート** をベースURLに入れてください。"
                )
            except Exception as ex:  # noqa: BLE001
                st.warning(f"確認中の例外: `{type(ex).__name__}: {ex}`")

    output_basename = st.text_input("保存ファイル名の素", value="web-draft")

    st.divider()
    st.markdown(f"**リポジトリ**: `{repo_root()}`")
    if not dist_note_exists():
        st.warning("`prompts/note/dist/note_writer_prompt.md` がありません。ターミナルで `bash prompts/note/assemble.sh` を実行してください。")


def _llm_kwargs() -> dict:
    return dict(
        transport=transport,
        cloud_provider=cloud_provider,
        cloud_model_in=cloud_model_in,
        local_base_url=local_base_url,
        local_model=local_model,
        local_api_key=local_api_key,
        output_basename=output_basename,
    )


tab_note, tab_share, tab_free = st.tabs(["note 下書き", "シェア短文", "自由入力（Call）"])

with tab_note:
    st.markdown("結合プロンプト＋「今回の依頼」をまとめて送ります（`99_task_input.md` 相当をそのまま貼ってください）。")
    task = st.text_area("今回の依頼（本文）", height=260, placeholder="- **テーマ**:\n- **書きたい事実**:\n…")
    if st.button("note を生成", type="primary", disabled=not dist_note_exists()):
        if not task.strip():
            st.error("依頼文を入力してください。")
        else:
            try:
                user = build_note_user_message(task)
                out = _run_llm(user=user, system="", tag="note", **_llm_kwargs())
                if out:
                    text, m, path = out
                    st.success(f"保存しました: `{path}`")
                    st.download_button("Markdown をダウンロード", text, file_name=path.name)
                    st.markdown(text)
            except FileNotFoundError as e:
                st.error(f"ファイルが見つかりません: {e}")

with tab_share:
    st.markdown("`share_short_from_company.md` に、記入済みの依頼内容を続けます。")
    filled = st.text_area("依頼（記入済み）", height=260, placeholder="シェアしたい要点、URL、貼り付けテキスト…")
    if st.button("シェア文案を生成", type="primary"):
        if not filled.strip():
            st.error("依頼内容を入力してください。")
        else:
            try:
                user = build_share_user_message(filled)
                out = _run_llm(user=user, system="", tag="share", **_llm_kwargs())
                if out:
                    text, m, path = out
                    st.success(f"保存しました: `{path}`")
                    st.download_button("Markdown をダウンロード", text, file_name=path.name)
                    st.markdown(text)
            except FileNotFoundError as e:
                st.error(f"ファイルが見つかりません: {e}")

with tab_free:
    st.markdown("任意のプロンプトを1本、または「メイン＋追記」で送ります。")
    system = st.text_input("システムメッセージ（空で可）", value="")
    main_prompt = st.text_area("メイン（プロンプト全文）", height=200)
    extra = st.text_area("追記（空で可）", height=120)
    if st.button("自由入力で生成", type="secondary"):
        if not main_prompt.strip():
            st.error("メインのプロンプトを入力してください。")
        else:
            user = main_prompt if not extra.strip() else main_prompt + "\n\n---\n\n" + extra.strip()
            out = _run_llm(user=user, system=system, tag="call", **_llm_kwargs())
            if out:
                text, m, path = out
                st.success(f"保存しました: `{path}`")
                st.download_button("Markdown をダウンロード", text, file_name=path.name)
                st.markdown(text)
