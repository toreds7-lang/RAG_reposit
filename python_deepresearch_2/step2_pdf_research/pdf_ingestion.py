"""
PDF ingestion: parse a PDF file into overlapping, token-counted chunks with metadata.

Known limitations
-----------------
- Tables and figures lose structure via pypdf. For layout-sensitive PDFs (e.g., JEDEC
  specs with dense tables) consider upgrading to pdfplumber or pymupdf.
- Scanned (image-only) PDFs raise ValueError. OCR preprocessing is required
  (e.g., tesseract + pdf2image) before ingestion.
"""

import logging
import os
import re
from typing import List, Optional, Tuple

from pydantic import BaseModel
from pypdf import PdfReader
import tiktoken

logger = logging.getLogger(__name__)

_ENCODER = None
_PAGE_SENTINEL_RE = re.compile(r"^--- PAGE (\d+) ---$")

# Section heading detection (priority order)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z][^\n]{0,100})$", re.MULTILINE)
_ALLCAPS_HEADING_RE = re.compile(r"^([A-Z][A-Z0-9 ]{3,60})$", re.MULTILINE)


class Chunk(BaseModel):
    chunk_id: int
    text: str
    page_start: int
    page_end: int
    section_hint: str
    token_count: int
    source_pdf: str


def _get_encoder():
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def load_pdf_text(pdf_path: str) -> List[Tuple[int, str]]:
    """Return [(page_num_1indexed, page_text), ...]. Raises ValueError on scanned PDFs."""
    reader = PdfReader(pdf_path)
    pages: List[Tuple[int, str]] = []
    total_chars = 0
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning("PDF page %d extraction failed: %s", idx, e)
            text = ""
        pages.append((idx, text))
        total_chars += len(text)
    logger.info("load_pdf_text | pdf=%s | pages=%d | total_chars=%d",
                os.path.basename(pdf_path), len(pages), total_chars)
    if total_chars < 100:
        raise ValueError(
            f"PDF appears to have no text layer (total extracted chars={total_chars}). "
            "Likely a scanned PDF. OCR preprocessing required "
            "(e.g. tesseract + pdf2image) before ingestion."
        )
    return pages


def detect_section_hint(chunk_text: str, page_start: int) -> str:
    """Best-effort heading detection from the first 300 chars of a chunk."""
    head = chunk_text[:300]
    m = _NUMBERED_HEADING_RE.search(head)
    if m:
        return f"{m.group(1)} {m.group(2).strip()}"
    m = _ALLCAPS_HEADING_RE.search(head)
    if m:
        return m.group(1).strip()
    return f"Page {page_start}"


def split_into_sentences(text: str) -> List[str]:
    """Paragraph-first, then sentence-boundary split. Long sentences fall back to 400-char slabs."""
    sentences: List[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        # Split on sentence-ending punctuation followed by whitespace, preserving the punctuation.
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", para)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Fallback: split very long single-line blobs (tables, formula dumps) into fixed slabs.
            if len(part) > 500:
                for i in range(0, len(part), 400):
                    sentences.append(part[i:i + 400])
            else:
                sentences.append(part)
    return sentences


def _build_units(pages: List[Tuple[int, str]]) -> List[Tuple[int, str, int]]:
    """Return [(page_num, sentence, token_count), ...] flattened across all pages."""
    units: List[Tuple[int, str, int]] = []
    for page_num, page_text in pages:
        if not page_text.strip():
            continue
        for sent in split_into_sentences(page_text):
            units.append((page_num, sent, count_tokens(sent)))
    return units


def build_chunks(
    pages: List[Tuple[int, str]],
    source_pdf: str,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    """Greedy sentence accumulation with token-counted overlap."""
    units = _build_units(pages)
    if not units:
        return []

    chunks: List[Chunk] = []
    buf: List[Tuple[int, str, int]] = []
    buf_tokens = 0
    chunk_id = 0

    def emit():
        nonlocal chunk_id
        if not buf:
            return
        text = "\n".join(s for _, s, _ in buf).strip()
        if not text:
            return
        page_start = min(p for p, _, _ in buf)
        page_end = max(p for p, _, _ in buf)
        chunks.append(Chunk(
            chunk_id=chunk_id,
            text=text,
            page_start=page_start,
            page_end=page_end,
            section_hint=detect_section_hint(text, page_start),
            token_count=sum(tc for _, _, tc in buf),
            source_pdf=source_pdf,
        ))
        chunk_id += 1

    for unit in units:
        _, _, utok = unit
        # Single sentence longer than chunk_size: emit whatever we have, then place it alone.
        if utok > chunk_size:
            emit()
            buf = [unit]
            buf_tokens = utok
            emit()
            buf = []
            buf_tokens = 0
            continue

        if buf_tokens + utok > chunk_size and buf:
            emit()
            # Build overlap from the tail of the just-emitted buffer.
            tail: List[Tuple[int, str, int]] = []
            tail_tokens = 0
            for prev in reversed(buf):
                if tail_tokens + prev[2] > overlap:
                    break
                tail.append(prev)
                tail_tokens += prev[2]
            tail.reverse()
            buf = list(tail)
            buf_tokens = tail_tokens

        buf.append(unit)
        buf_tokens += utok

    emit()
    return chunks


def pick_adaptive_defaults(num_pages: int) -> Tuple[int, int]:
    """Return (chunk_size, overlap) defaults based on PDF page count."""
    if num_pages < 50:
        return 400, 60
    return 800, 100


def ingest_pdf(
    pdf_path: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> Tuple[List[Chunk], int, int]:
    """Parse PDF, pick adaptive chunk size if unset, build chunks.

    Returns (chunks, effective_chunk_size, effective_overlap) — callers must pass the
    effective values to build_index() so the cache key matches.
    """
    pages = load_pdf_text(pdf_path)
    num_pages = len(pages)

    auto_cs, auto_ov = pick_adaptive_defaults(num_pages)
    effective_cs = chunk_size if chunk_size is not None else auto_cs
    effective_ov = overlap if overlap is not None else auto_ov

    chunks = build_chunks(
        pages=pages,
        source_pdf=os.path.basename(pdf_path),
        chunk_size=effective_cs,
        overlap=effective_ov,
    )

    if chunks:
        avg_tokens = sum(c.token_count for c in chunks) / len(chunks)
        logger.info(
            "ingest_pdf | pdf=%s | pages=%d | chunks=%d | chunk_size=%d | overlap=%d | avg_tokens=%.1f",
            os.path.basename(pdf_path), num_pages, len(chunks), effective_cs, effective_ov, avg_tokens,
        )
    return chunks, effective_cs, effective_ov
