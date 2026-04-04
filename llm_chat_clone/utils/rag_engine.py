from typing import Callable, Optional
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import config


def parse_pdf(uploaded_file, filename: str = None) -> list:
    """
    Parse a PDF into a list of Documents.
    Accepts a Streamlit UploadedFile or any file-like object (e.g. BytesIO).
    `filename` overrides the source metadata when the object has no .name attr.
    """
    source_name = filename or getattr(uploaded_file, "name", "dropped_file.pdf")
    reader = PdfReader(uploaded_file)
    docs = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            docs.append(Document(
                page_content=text,
                metadata={"source": source_name, "page": page_num},
            ))
    return docs


def chunk_documents(docs: list) -> list:
    """Split documents into smaller chunks for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def build_or_update_vectorstore(
    existing_vs,
    new_chunks: list,
    progress_callback: Optional[Callable[[float], None]] = None,
):
    """
    Embed new_chunks and merge into existing_vs (or create a fresh store).
    Embeds in batches of 50 and calls progress_callback(0.0–1.0) per batch.
    """
    embeddings = OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        openai_api_key=config.OPENAI_API_KEY,
    )

    batch_size = 50
    total = len(new_chunks)
    new_vs = None

    for i in range(0, total, batch_size):
        batch = new_chunks[i : i + batch_size]
        batch_vs = FAISS.from_documents(batch, embeddings)
        if new_vs is None:
            new_vs = batch_vs
        else:
            new_vs.merge_from(batch_vs)
        if progress_callback:
            progress_callback(min(1.0, (i + batch_size) / total))

    if new_vs is None:
        return existing_vs

    if existing_vs is not None:
        existing_vs.merge_from(new_vs)
        return existing_vs

    return new_vs


def retrieve_context(vectorstore, query: str, k: int = 5) -> str:
    """
    Retrieve the top-k most relevant chunks and format them with citations.
    """
    docs = vectorstore.similarity_search(query, k=k)
    parts = []
    for d in docs:
        src = d.metadata.get("source", "unknown")
        page = d.metadata.get("page", "?")
        parts.append(f"[{src} — p.{page}]\n{d.page_content}")
    return "\n\n---\n\n".join(parts)
