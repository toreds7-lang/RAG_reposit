"""
PDF parsing with docling + OpenAI embeddings + FAISS indexing.
Run directly to build the cache:  python ingest.py
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Optional

import numpy as np

import config


CACHE_SCHEMA_VERSION = 2

# Matches typical display-math fragments: operators, sqrt, sub/superscripts,
# or common symbols seen in the Attention paper (softmax, QK, d_k, ...).
_FORMULA_REGEX = re.compile(
    r"[=√∑∫∂∇∞]|\\sqrt|\^\{|_\{|softmax|\bQK\b|Attention\("
)


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

def parse_pdf() -> list[dict]:
    """Parse PDF with docling and return a list of element dicts."""
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.types.doc import (
        TextItem, TableItem, PictureItem, SectionHeaderItem, DocItemLabel,
    )

    print(f"[ingest] Parsing {config.PDF_PATH} with docling (formula enrichment on) …")
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_formula_enrichment = True
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    result = converter.convert(str(config.PDF_PATH))
    doc = result.document

    # Build a page-size lookup: page_no (1-based) -> (width_pts, height_pts)
    page_sizes: dict[int, tuple[float, float]] = {}
    for page_no, page_obj in doc.pages.items():
        w = page_obj.size.width if page_obj.size else 612.0
        h = page_obj.size.height if page_obj.size else 792.0
        page_sizes[int(page_no)] = (w, h)

    elements: list[dict] = []

    formula_label = DocItemLabel.FORMULA.value
    header_label = DocItemLabel.SECTION_HEADER.value

    for item, _level in doc.iterate_items():
        # Need provenance (page + bbox) to be selectable at all.
        if not getattr(item, "prov", None):
            continue

        label = getattr(item, "label", None)
        label_str = getattr(label, "value", None) or (str(label) if label else "")

        prov = item.prov[0]
        page_no = int(prov.page_no)

        # Classify by type first, then by label, so newly enabled item kinds
        # (formulas, captions, list items, code, …) don't get silently dropped.
        if isinstance(item, TableItem):
            elem_type = "table"
            try:
                text = item.export_to_markdown()
            except Exception:
                text = getattr(item, "text", "") or ""
        elif isinstance(item, PictureItem):
            elem_type = "figure"
            try:
                text = item.caption_text(doc) or ""
            except Exception:
                text = ""
            if not text.strip():
                text = f"[Figure on page {page_no}]"
        elif label_str == formula_label:
            elem_type = "formula"
            text = (getattr(item, "text", "") or "").strip() or "[Formula]"
        elif isinstance(item, SectionHeaderItem) or label_str == header_label:
            elem_type = "section_header"
            text = getattr(item, "text", "") or ""
        elif isinstance(item, TextItem):
            elem_type = label_str or "text"
            text = getattr(item, "text", "") or ""
        else:
            continue

        if elem_type != "figure" and not text.strip():
            continue

        bbox = prov.bbox  # BoundingBox in PDF coordinate space

        page_w, page_h = page_sizes.get(page_no, (612.0, 792.0))

        # Normalise bbox to bottom-left origin (PDF standard)
        # docling may store as TOPLEFT; check coord_origin if available
        try:
            from docling_core.types.doc.page import CoordOrigin
            if hasattr(bbox, "coord_origin") and bbox.coord_origin == CoordOrigin.TOPLEFT:
                # Convert to bottom-left
                real_b = page_h - bbox.b
                real_t = page_h - bbox.t
                bbox_dict = {
                    "l": float(bbox.l),
                    "t": float(real_t),
                    "r": float(bbox.r),
                    "b": float(real_b),
                }
            else:
                bbox_dict = {
                    "l": float(bbox.l),
                    "t": float(bbox.t),
                    "r": float(bbox.r),
                    "b": float(bbox.b),
                }
        except ImportError:
            bbox_dict = {
                "l": float(bbox.l),
                "t": float(bbox.t),
                "r": float(bbox.r),
                "b": float(bbox.b),
            }

        elements.append({
            "element_id": str(getattr(item, "self_ref", id(item))),
            "element_type": elem_type,
            "page_no": page_no,
            "text": text.strip(),
            "bbox_pdf": bbox_dict,
            "page_height_pdf": page_h,
            "page_width_pdf": page_w,
        })

    print(f"[ingest] Extracted {len(elements)} elements (pre-supplement).")

    elements = _supplement_missing_text_blocks(elements, config.PDF_PATH)
    elements = _group_figures(elements)

    print(f"[ingest] Final element count: {len(elements)}.")
    return elements


# ---------------------------------------------------------------------------
# PyMuPDF gap-filling: catch text blocks docling dropped (notably display eqs)
# ---------------------------------------------------------------------------

def _iou(a: dict, b: dict) -> float:
    """IoU of two bboxes in bottom-left PDF coord space (l, b, r, t)."""
    ix_l = max(a["l"], b["l"])
    ix_r = min(a["r"], b["r"])
    iy_b = max(a["b"], b["b"])
    iy_t = min(a["t"], b["t"])
    if ix_r <= ix_l or iy_t <= iy_b:
        return 0.0
    inter = (ix_r - ix_l) * (iy_t - iy_b)
    area_a = max(0.0, (a["r"] - a["l"])) * max(0.0, (a["t"] - a["b"]))
    area_b = max(0.0, (b["r"] - b["l"])) * max(0.0, (b["t"] - b["b"]))
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _contains_centroid(container: dict, inner: dict) -> bool:
    cx = (inner["l"] + inner["r"]) / 2.0
    cy = (inner["b"] + inner["t"]) / 2.0
    return container["l"] <= cx <= container["r"] and container["b"] <= cy <= container["t"]


def _supplement_missing_text_blocks(
    elements: list[dict], pdf_path: Path
) -> list[dict]:
    """
    Use PyMuPDF to find text blocks that docling didn't capture and add them
    to `elements`. Classifies isolated math-like blocks as 'formula'.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    supplements: list[dict] = []

    try:
        for page_idx, page in enumerate(doc):
            page_no = page_idx + 1
            page_w = page.rect.width
            page_h = page.rect.height

            existing_on_page = [e for e in elements if e["page_no"] == page_no]

            raw_blocks = page.get_text("blocks")
            # Normalise to dicts with bottom-left coords and skip margins.
            page_blocks: list[dict] = []
            for x0, y0, x1, y1, text, block_no, block_type in raw_blocks:
                if block_type != 0:
                    continue
                if not text or not text.strip():
                    continue
                # Skip headers/footers/page numbers (within 50 pt of edges).
                if y0 < 50 or y1 > page_h - 50:
                    continue
                # Convert top-left -> bottom-left PDF coords.
                bl_l = float(x0)
                bl_r = float(x1)
                bl_t = float(page_h - y0)
                bl_b = float(page_h - y1)
                page_blocks.append({
                    "l": bl_l, "r": bl_r, "t": bl_t, "b": bl_b,
                    "text": text.strip(),
                    "block_no": block_no,
                })

            # Merge horizontally adjacent blocks that share a baseline
            # (y-range within 4 pt). Handles equations split across columns.
            merged: list[dict] = []
            used = [False] * len(page_blocks)
            for i, bi in enumerate(page_blocks):
                if used[i]:
                    continue
                group = [bi]
                used[i] = True
                for j in range(i + 1, len(page_blocks)):
                    if used[j]:
                        continue
                    bj = page_blocks[j]
                    if abs(bi["t"] - bj["t"]) <= 4 and abs(bi["b"] - bj["b"]) <= 4:
                        group.append(bj)
                        used[j] = True
                if len(group) == 1:
                    merged.append(bi)
                else:
                    group.sort(key=lambda g: g["l"])
                    merged.append({
                        "l": min(g["l"] for g in group),
                        "r": max(g["r"] for g in group),
                        "t": max(g["t"] for g in group),
                        "b": min(g["b"] for g in group),
                        "text": " ".join(g["text"] for g in group),
                        "block_no": group[0]["block_no"],
                    })

            # Filter out blocks already covered by an existing element.
            for mb in merged:
                mb_bbox = {"l": mb["l"], "r": mb["r"], "t": mb["t"], "b": mb["b"]}
                covered = False
                for elem in existing_on_page:
                    eb = elem["bbox_pdf"]
                    if _contains_centroid(eb, mb_bbox) and _iou(eb, mb_bbox) >= 0.30:
                        covered = True
                        break
                if covered:
                    continue

                text = mb["text"]
                width = mb["r"] - mb["l"]
                is_formula = bool(_FORMULA_REGEX.search(text)) and (
                    width < 0.65 * page_w or len(text) < 120
                )
                elem_type = "formula" if is_formula else "text"

                supplements.append({
                    "element_id": f"supp_p{page_no}_b{mb['block_no']}",
                    "element_type": elem_type,
                    "page_no": page_no,
                    "text": text,
                    "bbox_pdf": mb_bbox,
                    "page_height_pdf": float(page_h),
                    "page_width_pdf": float(page_w),
                })
    finally:
        doc.close()

    if supplements:
        n_formula = sum(1 for s in supplements if s["element_type"] == "formula")
        print(
            f"[ingest] Supplemented {len(supplements)} missing text blocks "
            f"({n_formula} classified as formula)."
        )
    return elements + supplements


# ---------------------------------------------------------------------------
# Figure grouping: merge side-by-side PictureItems into one figure_group
# ---------------------------------------------------------------------------

def _group_figures(elements: list[dict]) -> list[dict]:
    """
    Cluster adjacent figure elements on the same page into a single
    'figure_group'. Removes the children + their nearest caption text so one
    click selects the whole group.
    """
    by_page: dict[int, list[int]] = {}
    for idx, elem in enumerate(elements):
        if elem["element_type"] == "figure":
            by_page.setdefault(elem["page_no"], []).append(idx)

    removed: set[int] = set()
    new_groups: list[dict] = []

    for page_no, idxs in by_page.items():
        if len(idxs) < 2:
            continue

        # Union-find over the figure indices.
        parent = {i: i for i in idxs}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a = elements[idxs[i]]["bbox_pdf"]
                b = elements[idxs[j]]["bbox_pdf"]
                cxa = (a["l"] + a["r"]) / 2.0
                cxb = (b["l"] + b["r"]) / 2.0
                if abs(cxa - cxb) >= 250:
                    continue
                ha = a["t"] - a["b"]
                hb = b["t"] - b["b"]
                if ha <= 0 or hb <= 0:
                    continue
                overlap = min(a["t"], b["t"]) - max(a["b"], b["b"])
                if overlap <= 0:
                    continue
                if overlap / min(ha, hb) >= 0.40:
                    union(idxs[i], idxs[j])

        # Collect clusters.
        clusters: dict[int, list[int]] = {}
        for i in idxs:
            clusters.setdefault(find(i), []).append(i)

        group_seq = 0
        for root, members in clusters.items():
            if len(members) < 2:
                continue
            group_seq += 1

            bboxes = [elements[m]["bbox_pdf"] for m in members]
            union_bbox = {
                "l": min(b["l"] for b in bboxes) - 2.0,
                "r": max(b["r"] for b in bboxes) + 2.0,
                "t": max(b["t"] for b in bboxes) + 2.0,
                "b": min(b["b"] for b in bboxes) - 2.0,
            }

            # Find a standalone caption element near the union — prefer a
            # dedicated 'caption' type, fall back to 'text' starting with
            # "Figure". Match in both cases so we can delete the duplicate.
            caption_text = ""
            caption_idx: Optional[int] = None
            best_gap = 60.0
            for k, elem in enumerate(elements):
                if elem["page_no"] != page_no:
                    continue
                etype = elem["element_type"]
                if etype not in ("caption", "text"):
                    continue
                text_preview = elem["text"].lstrip()
                if not text_preview.lower().startswith("figure"):
                    continue
                eb = elem["bbox_pdf"]
                gap_below = union_bbox["b"] - eb["t"]
                gap_above = eb["b"] - union_bbox["t"]
                gap = min(
                    gap_below if gap_below >= 0 else float("inf"),
                    gap_above if gap_above >= 0 else float("inf"),
                )
                if gap > best_gap:
                    continue
                hx = min(eb["r"], union_bbox["r"]) - max(eb["l"], union_bbox["l"])
                if hx <= 0:
                    continue
                caption_text = elem["text"]
                caption_idx = k
                best_gap = gap

            # Fall back to any member's non-placeholder caption (not removable).
            if not caption_text:
                for m in members:
                    t = elements[m].get("text", "").strip()
                    if t and not t.startswith("[Figure"):
                        caption_text = t
                        break

            if not caption_text:
                caption_text = f"[Figure group on page {page_no}]"

            page_h = elements[members[0]]["page_height_pdf"]
            page_w = elements[members[0]]["page_width_pdf"]

            new_groups.append({
                "element_id": f"figgroup_p{page_no}_{group_seq}",
                "element_type": "figure_group",
                "page_no": page_no,
                "text": caption_text.strip(),
                "bbox_pdf": union_bbox,
                "page_height_pdf": page_h,
                "page_width_pdf": page_w,
            })

            for m in members:
                removed.add(m)
            if caption_idx is not None:
                removed.add(caption_idx)

    if not new_groups:
        return elements

    kept = [e for i, e in enumerate(elements) if i not in removed]
    print(
        f"[ingest] Grouped {len(removed) - len(new_groups)} figure/caption "
        f"elements into {len(new_groups)} figure_group(s)."
    )
    return kept + new_groups


# ---------------------------------------------------------------------------
# Page image rendering
# ---------------------------------------------------------------------------

def render_page_images(
    pdf_path: Path = config.PDF_PATH,
    output_dir: Path = config.PAGE_IMAGES_DIR,
    dpi: int = config.RENDER_DPI,
) -> int:
    """Render each PDF page as a PNG. Returns number of pages rendered."""
    import fitz  # PyMuPDF

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    rendered = 0
    for i, page in enumerate(doc):
        out_path = output_dir / f"page_{i + 1:03d}.png"
        if out_path.exists():
            continue
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(out_path))
        rendered += 1
    doc.close()
    print(f"[ingest] Rendered {rendered} new page images (total {i + 1} pages).")
    return i + 1  # total pages


# ---------------------------------------------------------------------------
# FAISS indexing
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts with OpenAI in batches."""
    import openai

    kwargs: dict = {"api_key": config.OPENAI_API_KEY}
    if config.EMBEDDING_BASE_URL:
        kwargs["base_url"] = config.EMBEDDING_BASE_URL
    client = openai.OpenAI(**kwargs)

    all_embeddings: list[list[float]] = []
    batch_size = config.EMBED_BATCH_SIZE
    for start in range(0, len(texts), batch_size):
        batch = texts[start: start + batch_size]
        response = client.embeddings.create(input=batch, model=config.EMBEDDING_MODEL)
        all_embeddings.extend([r.embedding for r in response.data])
        print(f"[ingest] Embedded {min(start + batch_size, len(texts))}/{len(texts)} texts …")
    return all_embeddings


def build_faiss_index(elements: list[dict]):
    """Build and return a FAISS IndexFlatL2 from element texts."""
    import faiss

    texts = [e["text"] for e in elements]
    print(f"[ingest] Generating embeddings for {len(texts)} elements …")
    embeddings = _embed_texts(texts)

    vectors = np.array(embeddings, dtype=np.float32)
    index = faiss.IndexFlatL2(config.EMBED_DIM)
    index.add(vectors)
    print(f"[ingest] FAISS index built: {index.ntotal} vectors.")
    return index


# ---------------------------------------------------------------------------
# Cache persistence
# ---------------------------------------------------------------------------

def save_cache(elements: list[dict], index) -> None:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": CACHE_SCHEMA_VERSION, "elements": elements}
    with open(config.ELEMENTS_CACHE, "wb") as f:
        pickle.dump(payload, f)
    import faiss
    faiss.write_index(index, str(config.FAISS_INDEX_CACHE))
    print(f"[ingest] Cache saved to {config.CACHE_DIR} (schema v{CACHE_SCHEMA_VERSION}).")


def load_cache() -> tuple[Optional[list[dict]], Optional[object]]:
    """Return (elements, index) from disk, or (None, None) if cache missing/stale."""
    if not config.ELEMENTS_CACHE.exists() or not config.FAISS_INDEX_CACHE.exists():
        return None, None
    with open(config.ELEMENTS_CACHE, "rb") as f:
        payload = pickle.load(f)
    if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA_VERSION:
        print(
            f"[ingest] Cache schema mismatch (expected v{CACHE_SCHEMA_VERSION}); "
            f"rebuilding."
        )
        return None, None
    elements = payload["elements"]
    import faiss
    index = faiss.read_index(str(config.FAISS_INDEX_CACHE))
    print(f"[ingest] Cache loaded: {len(elements)} elements, {index.ntotal} vectors.")
    return elements, index


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    elements = parse_pdf()
    render_page_images()
    index = build_faiss_index(elements)
    save_cache(elements, index)
    print("[ingest] Done.")


if __name__ == "__main__":
    main()
