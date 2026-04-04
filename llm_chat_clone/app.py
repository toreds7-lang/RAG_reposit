import base64
import io
import os

import streamlit as st
import streamlit.components.v1 as components

import config
from utils.session_manager import (
    init_sessions,
    create_new_session,
    get_active_session,
    add_message,
    switch_session,
)
from utils.llm_client import fetch_available_models, get_local_client, get_openai_client, stream_chat
from utils.rag_engine import (
    parse_pdf,
    chunk_documents,
    build_or_update_vectorstore,
    retrieve_context,
)

# ── Register global PDF drop-zone component ────────────────────────────────────
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "components", "pdf_dropzone")
_pdf_dropzone = components.declare_component("pdf_dropzone", path=_COMPONENT_DIR)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LLM Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Minimal CSS: hide Streamlit menu, tighten column padding
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    div[data-testid="column"] {padding: 0 0.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── State initialization ───────────────────────────────────────────────────────
init_sessions()

ss = st.session_state

# ── Three-column layout ────────────────────────────────────────────────────────
col_left, col_center, col_right = st.columns([1, 3, 1.2], gap="medium")

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — LLM Parameters (rendered first so params are ready for center)
# ══════════════════════════════════════════════════════════════════════════════
with col_right:
    st.markdown("### ⚙️ Parameters")

    if config.USE_OPENAI_API:
        models = config.OPENAI_MODELS
        selected_model = st.selectbox("Model", models,
                                      index=models.index(config.OPENAI_CHAT_MODEL),
                                      key="selected_model")
    else:
        models = fetch_available_models(config.LOCAL_LLM_BASE_URL, config.LOCAL_LLM_API_KEY)
        selected_model = st.selectbox("Model", models, key="selected_model")

    st.divider()

    temperature = st.slider(
        "Temperature", 0.0, 2.0, config.DEFAULT_TEMPERATURE, 0.05, key="slider_temp"
    )
    top_p = st.slider(
        "Top-P", 0.0, 1.0, config.DEFAULT_TOP_P, 0.01, key="slider_top_p"
    )
    top_k = st.slider(
        "Top-K", 1, 100, config.DEFAULT_TOP_K, key="slider_top_k"
    )
    max_tokens = st.slider(
        "Max Tokens", 128, 8192, config.DEFAULT_MAX_TOKENS, 128, key="slider_max_tokens"
    )

    st.divider()
    st.markdown("**RAG Settings**")
    rag_enabled = st.checkbox("Enable RAG", value=True, key="rag_enabled")
    rag_k = st.slider(
        "Retrieved chunks (k)", 1, 10, config.TOP_K, key="slider_rag_k"
    )

    # Show local server URL for info
    st.divider()
    if config.USE_OPENAI_API:
        st.caption(f"API: `OpenAI` · model: `{config.OPENAI_CHAT_MODEL}`")
    else:
        st.caption(f"Local API: `{config.LOCAL_LLM_BASE_URL}`")

params = {
    "temperature": temperature,
    "top_p": top_p,
    "top_k": top_k,
    "max_tokens": max_tokens,
}

# ══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — Session Management
# ══════════════════════════════════════════════════════════════════════════════
with col_left:
    st.markdown("### 💬 Sessions")

    if st.button("＋ New Session", use_container_width=True, type="primary"):
        create_new_session()
        st.rerun()

    st.divider()

    active_sid = ss["active_session_id"]
    for sid, session in ss["sessions"].items():
        is_active = sid == active_sid
        label = f"{'▶ ' if is_active else '   '}{session['name']}\n{session['created_at']}"
        btn_type = "primary" if is_active else "secondary"
        if st.button(
            label,
            key=f"sess_btn_{sid}",
            use_container_width=True,
            type=btn_type,
        ):
            if not is_active:
                switch_session(sid)
                st.rerun()

    # Show PDF summary for active session
    active = get_active_session()
    if active["pdf_names"]:
        st.divider()
        st.markdown("**Indexed PDFs**")
        for name in active["pdf_names"]:
            st.caption(f"📄 {name}")

# ══════════════════════════════════════════════════════════════════════════════
# CENTER PANEL — Chat Interface
# ══════════════════════════════════════════════════════════════════════════════
with col_center:
    active = get_active_session()

    # Header
    col_title, col_model_tag = st.columns([3, 1])
    with col_title:
        st.markdown(f"### {active['name']}")
    with col_model_tag:
        st.markdown(
            f"<div style='text-align:right; padding-top:0.6rem; color:gray; font-size:0.8rem'>"
            f"🤖 {selected_model}</div>",
            unsafe_allow_html=True,
        )

    # ── PDF Upload ─────────────────────────────────────────────────────────────
    with st.expander(
        "📎 Upload PDFs for RAG"
        + (f"  ({len(active['pdf_names'])} indexed)" if active["pdf_names"] else ""),
        expanded=(len(active["pdf_names"]) == 0),
    ):
        uploaded_files = st.file_uploader(
            "Drag and drop PDF files here",
            type=["pdf"],
            accept_multiple_files=True,
            key=f"pdf_uploader_{ss['active_session_id']}",
            label_visibility="collapsed",
        )

        if uploaded_files:
            new_files = [
                f for f in uploaded_files if f.name not in active["pdf_names"]
            ]
            if new_files:
                total_chunks = 0
                progress_bar = st.progress(0.0, text="Processing PDFs…")

                all_chunks = []
                for uf in new_files:
                    docs = parse_pdf(uf)
                    chunks = chunk_documents(docs)
                    all_chunks.extend(chunks)
                    total_chunks += len(chunks)

                def _progress(p: float):
                    progress_bar.progress(p, text=f"Embedding… {int(p*100)}%")

                active["vectorstore"] = build_or_update_vectorstore(
                    active["vectorstore"],
                    all_chunks,
                    progress_callback=_progress,
                )
                active["pdf_names"].extend([f.name for f in new_files])
                progress_bar.empty()
                st.success(
                    f"Indexed {len(new_files)} file(s) — "
                    f"{total_chunks} chunks embedded."
                )

        if active["pdf_names"]:
            st.caption("Indexed: " + " · ".join(active["pdf_names"]))

    # ── Global PDF drop-zone (invisible iframe, listens on parent document) ─────
    if "last_drop_id" not in ss:
        ss["last_drop_id"] = None

    drop_result = _pdf_dropzone(key="global_pdf_drop", default=None)

    if drop_result is not None:
        if "error" in drop_result:
            if drop_result["error"] == "not_pdf":
                st.toast("Only PDF files can be dropped here.", icon="⚠️")
            else:
                st.toast(f"Drop read error: {drop_result.get('name', 'file')}", icon="❌")
        elif drop_result.get("id") and drop_result["id"] != ss["last_drop_id"]:
            ss["last_drop_id"] = drop_result["id"]  # set first to prevent retry loops
            if ss.get("is_streaming"):
                st.toast("PDF drop ignored — generation in progress.", icon="⏳")
            else:
                pdf_name = drop_result["name"]
                active = get_active_session()
                if pdf_name in active["pdf_names"]:
                    st.toast(f'"{pdf_name}" is already indexed.', icon="ℹ️")
                else:
                    try:
                        pdf_bytes = base64.b64decode(drop_result["data"])
                        pdf_io = io.BytesIO(pdf_bytes)
                        with st.spinner(f'Indexing "{pdf_name}"…'):
                            docs = parse_pdf(pdf_io, filename=pdf_name)
                            chunks = chunk_documents(docs)
                            active["vectorstore"] = build_or_update_vectorstore(
                                active["vectorstore"], chunks
                            )
                            active["pdf_names"].append(pdf_name)
                        st.toast(
                            f'"{pdf_name}" indexed — {len(chunks)} chunks.',
                            icon="✅",
                        )
                        st.rerun()
                    except Exception as exc:
                        st.toast(f"Failed to index PDF: {exc}", icon="❌")

    # ── Chat message display ───────────────────────────────────────────────────
    chat_container = st.container(height=480)
    with chat_container:
        if not active["messages"]:
            st.markdown(
                "<div style='color:gray; text-align:center; margin-top:6rem;'>"
                "No messages yet. Start a conversation below."
                "</div>",
                unsafe_allow_html=True,
            )
        for msg in active["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── Stop button (shown while streaming) ───────────────────────────────────
    if ss["is_streaming"]:
        if st.button(
            "⏹ Stop Generating",
            key="stop_btn",
            type="secondary",
            use_container_width=True,
        ):
            ss["stop_requested"] = True

    # ── Chat input ────────────────────────────────────────────────────────────
    user_input = st.chat_input(
        "Ask anything… (Enter to send)",
        disabled=ss["is_streaming"],
        key="chat_input",
    )

    if user_input:
        add_message("user", user_input)
        ss["pending_input"] = user_input
        ss["is_streaming"] = True
        ss["stop_requested"] = False
        st.rerun()

    # ── Streaming execution ───────────────────────────────────────────────────
    if (
        ss["is_streaming"]
        and active["messages"]
        and active["messages"][-1]["role"] == "user"
    ):
        last_user_msg = active["messages"][-1]["content"]

        # Build system message — inject RAG context if available
        if rag_enabled and active["vectorstore"] is not None:
            context = retrieve_context(active["vectorstore"], last_user_msg, k=rag_k)
            system_content = (
                "You are a helpful assistant. Answer based on the provided document context.\n\n"
                f"Context:\n{context}\n\n"
                "If the answer is not in the context, say so and answer from your general knowledge."
            )
        else:
            system_content = "You are a helpful assistant."

        messages_for_llm = [{"role": "system", "content": system_content}]
        messages_for_llm += [
            {"role": m["role"], "content": m["content"]}
            for m in active["messages"]
        ]

        with chat_container:
            with st.chat_message("assistant"):
                try:
                    client = get_openai_client() if config.USE_OPENAI_API else get_local_client()
                    generator = stream_chat(client, selected_model, messages_for_llm, params)
                    full_response = st.write_stream(generator)
                except Exception as e:
                    full_response = f"Error: {e}"
                    st.error(full_response)

        add_message("assistant", full_response or "(stopped)")
        ss["is_streaming"] = False
        ss["stop_requested"] = False
        ss["pending_input"] = None
        st.rerun()
