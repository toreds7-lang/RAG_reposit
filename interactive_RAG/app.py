"""
Interactive RAG — Streamlit application.
Left panel: PDF viewer with clickable element selection + highlight.
Right panel: Chat interface with RAG-powered answers.
"""
from __future__ import annotations

import fitz  # PyMuPDF — imported early to surface any install issues
import streamlit as st

import config
import ingest
import pdf_viewer
import rag
from components.image_coordinates_ext import streamlit_image_coordinates_ext


# Cache page images across Streamlit reruns so clicks don't re-read PNGs from disk.
@st.cache_data(show_spinner=False)
def _cached_page_image(page_no: int):
    return pdf_viewer.get_page_image(page_no)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Interactive RAG — Attention Paper",
    page_icon="📄",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "elements": None,
    "index": None,
    "total_pages": 0,
    "current_page": 1,
    "selected_elements": [],
    "highlight_bboxes": [],
    "chat_history": [],
    "last_click": None,
    "ingestion_done": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Startup: load or build cache (runs once per session)
# ---------------------------------------------------------------------------
if not st.session_state.ingestion_done:
    elements, index = ingest.load_cache()

    if elements is None or index is None:
        st.info(
            "First run: parsing the PDF and building the vector index. "
            "This may take **2–5 minutes** while docling downloads its models (~1 GB). "
            "Subsequent runs will be instant."
        )
        with st.spinner("Parsing PDF with docling …"):
            elements = ingest.parse_pdf()
        with st.spinner("Rendering page images …"):
            ingest.render_page_images()
        with st.spinner("Building FAISS index (embedding with OpenAI) …"):
            index = ingest.build_faiss_index(elements)
        ingest.save_cache(elements, index)

    doc = fitz.open(str(config.PDF_PATH))
    st.session_state.elements = elements
    st.session_state.index = index
    st.session_state.total_pages = doc.page_count
    doc.close()
    st.session_state.ingestion_done = True

elements: list[dict] = st.session_state.elements
index = st.session_state.index
total_pages: int = st.session_state.total_pages

# ---------------------------------------------------------------------------
# Layout: two equal columns
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1, 1], gap="medium")

# ============================================================
# LEFT COLUMN — PDF Viewer
# ============================================================
with col_left:
    st.subheader("PDF Viewer")

    def _reset_selection() -> None:
        st.session_state.selected_elements = []
        st.session_state.highlight_bboxes = []
        st.session_state.last_click = None

    # Page navigation
    nav_left, nav_mid, nav_right = st.columns([1, 3, 1])
    with nav_left:
        if st.button("◀", use_container_width=True):
            if st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                _reset_selection()
    with nav_mid:
        page_input = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.current_page,
            step=1,
            label_visibility="collapsed",
        )
        if page_input != st.session_state.current_page:
            st.session_state.current_page = int(page_input)
            _reset_selection()
    with nav_right:
        if st.button("▶", use_container_width=True):
            if st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                _reset_selection()

    st.caption(f"Page {st.session_state.current_page} / {total_pages}")

    # Render current page image
    current_page = st.session_state.current_page
    try:
        page_img = _cached_page_image(current_page)
    except FileNotFoundError:
        # Render on-the-fly if pre-rendered image is missing
        ingest.render_page_images()
        _cached_page_image.clear()
        page_img = _cached_page_image(current_page)

    # Apply highlight overlay if anything is selected on this page
    if st.session_state.highlight_bboxes:
        display_img = pdf_viewer.draw_highlights(page_img, st.session_state.highlight_bboxes)
    else:
        display_img = page_img

    # Display with click-coordinate capture + modifier keys.
    # Key changes per page so the widget resets its stored click on page nav.
    coords = streamlit_image_coordinates_ext(
        display_img,
        key=f"pdf_viewer_p{current_page}",
        use_column_width=True,
    )

    # Handle click — deduplicate to avoid infinite reruns.
    if coords is not None and coords != st.session_state.last_click:
        st.session_state.last_click = coords
        page_elements = [e for e in elements if e["page_no"] == current_page]
        clicked_elem = pdf_viewer.pixel_to_element(
            coords["x"], coords["y"], page_elements,
        )
        multi = bool(coords.get("shiftKey") or coords.get("ctrlKey"))

        if clicked_elem is None:
            if not multi:
                st.session_state.selected_elements = []
        else:
            existing_ids = {e["element_id"] for e in st.session_state.selected_elements}
            if multi:
                if clicked_elem["element_id"] in existing_ids:
                    st.session_state.selected_elements = [
                        e for e in st.session_state.selected_elements
                        if e["element_id"] != clicked_elem["element_id"]
                    ]
                else:
                    st.session_state.selected_elements.append(clicked_elem)
            else:
                st.session_state.selected_elements = [clicked_elem]

        st.session_state.highlight_bboxes = [
            pdf_viewer.element_pixel_bbox(e)
            for e in st.session_state.selected_elements
            if e["page_no"] == current_page
        ]
        st.rerun()

    # Selected-elements info chip(s)
    selected = st.session_state.selected_elements
    if len(selected) == 0:
        st.caption(
            "Click to select an element. Ctrl or Shift+click to add to the selection."
        )
    elif len(selected) == 1:
        sel = selected[0]
        label = (
            f"**[{sel['element_type'].upper()} — Page {sel['page_no']}]**  "
            f"{sel['text'][:120]}{'…' if len(sel['text']) > 120 else ''}"
        )
        st.info(label)
        if st.button("Clear selection", key="clear_sel"):
            _reset_selection()
            st.rerun()
    else:
        lines = [f"**Selected {len(selected)} elements:**"]
        for i, sel in enumerate(selected, start=1):
            snippet = sel["text"][:60] + ("…" if len(sel["text"]) > 60 else "")
            lines.append(
                f"{i}. `{sel['element_type']}` — Page {sel['page_no']} — {snippet}"
            )
        st.info("\n\n".join(lines))
        if st.button("Clear selection", key="clear_sel"):
            _reset_selection()
            st.rerun()

# ============================================================
# RIGHT COLUMN — Chat Interface
# ============================================================
with col_right:
    st.subheader("Chat")

    # Context indicator
    selected_ctx = st.session_state.selected_elements
    if len(selected_ctx) == 1:
        sel = selected_ctx[0]
        preview = sel["text"][:100] + ("…" if len(sel["text"]) > 100 else "")
        st.info(
            f"Context: **{sel['element_type'].upper()}** — Page {sel['page_no']}\n\n"
            f"_{preview}_"
        )
    elif len(selected_ctx) > 1:
        types = ", ".join(
            sorted({e["element_type"].upper() for e in selected_ctx})
        )
        st.info(
            f"Context: **{len(selected_ctx)} elements** ({types}) will be passed "
            f"to the model alongside retrieved chunks."
        )

    # Chat history display
    chat_container = st.container(height=500)
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown(
                "_No messages yet. Ask a question about the paper, "
                "or click an element in the PDF first to anchor your question._"
            )
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Chat input
    question = st.chat_input("Ask about the paper …")
    if question:
        # Append user message to display history
        st.session_state.chat_history.append({"role": "user", "content": question})

        with st.spinner("Retrieving context and generating answer …"):
            # Build history excluding the current user turn (rag.chat handles injection)
            prior_history = st.session_state.chat_history[:-1]

            retrieved = rag.retrieve(
                question,
                index,
                elements,
                top_k=config.FAISS_TOP_K,
            )
            answer = rag.chat(
                question,
                retrieved,
                st.session_state.selected_elements,
                prior_history,
            )

        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()
