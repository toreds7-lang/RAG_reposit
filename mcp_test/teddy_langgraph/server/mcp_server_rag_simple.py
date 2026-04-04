from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from pathlib import Path
import os
import sys
import time


# ── 디버그 로깅 ──────────────────────────────────────────────────────────────
_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_rag_simple_debug.log")


def log(msg: str):
    """stderr + 파일로 디버그 로그를 출력합니다 (stdio 전송에서 stdout은 MCP 프로토콜용)."""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with open(_log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


log("[MCP-RAG-SIMPLE] Server module loading...")
load_dotenv(override=True)


# ── 경로 설정 ────────────────────────────────────────────────────────────────
_current_dir = os.path.dirname(os.path.abspath(__file__))
_pdf_path = os.path.join(_current_dir, "data", "SPRI_AI_Brief_2023년12월호_F.pdf")
_cache_path = os.path.join(_current_dir, "data", "faiss_cache_simple")


# ── Vectorstore 생성 (캐시 우선) ─────────────────────────────────────────────
def create_vectorstore() -> tuple:
    """PDF에서 FAISS 벡터스토어를 생성하거나 캐시에서 로드합니다.

    Returns:
        (vectorstore, embeddings) 튜플
    """
    t_start = time.time()
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # 캐시가 있으면 바로 로드
    if Path(_cache_path).is_dir() and (Path(_cache_path) / "index.faiss").exists():
        log("[MCP-RAG-SIMPLE] FAISS cache found! Loading from cache...")
        vectorstore = FAISS.load_local(
            _cache_path, embeddings, allow_dangerous_deserialization=True
        )
        log(f"[MCP-RAG-SIMPLE] Cache loaded in {time.time() - t_start:.2f}s")
        return vectorstore, embeddings

    # 캐시 없으면 PDF 로드 → 분할 → 임베딩
    log(f"[MCP-RAG-SIMPLE] No cache. Building from PDF: {_pdf_path}")

    log("[MCP-RAG-SIMPLE] Step 1/3: Loading PDF...")
    t_step = time.time()
    docs = PDFPlumberLoader(_pdf_path).load()
    log(f"[MCP-RAG-SIMPLE] Step 1/3: Done ({len(docs)} pages) in {time.time() - t_step:.2f}s")

    log("[MCP-RAG-SIMPLE] Step 2/3: Splitting documents...")
    t_step = time.time()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = splitter.split_documents(docs)
    log(f"[MCP-RAG-SIMPLE] Step 2/3: Done ({len(split_docs)} chunks) in {time.time() - t_step:.2f}s")

    log("[MCP-RAG-SIMPLE] Step 3/3: Creating FAISS vectorstore (embedding API calls)...")
    t_step = time.time()
    vectorstore = FAISS.from_documents(split_docs, embeddings)
    vectorstore.save_local(_cache_path)
    log(f"[MCP-RAG-SIMPLE] Step 3/3: Done in {time.time() - t_step:.2f}s")

    log(f"[MCP-RAG-SIMPLE] Vectorstore ready | Total: {time.time() - t_start:.2f}s")
    return vectorstore, embeddings


# ── FastMCP 서버 초기화 ──────────────────────────────────────────────────────
mcp = FastMCP(
    "Retriever",
    instructions="데이터베이스에서 정보를 검색할 수 있는 Retriever입니다.",
)

# 서버 시작 시 한 번만 생성
vectorstore, embeddings = create_vectorstore()
log("[MCP-RAG-SIMPLE] Server ready! Waiting for requests...")


# ── retrieve 도구 ────────────────────────────────────────────────────────────
@mcp.tool()
async def retrieve(query: str) -> str:
    """쿼리를 기반으로 문서 데이터베이스에서 정보를 검색합니다.

    Args:
        query: 관련 정보를 찾기 위한 검색 쿼리

    Returns:
        검색된 문서를 XML 형식으로 연결한 문자열 (content, source, page 포함)
    """
    log(f"[MCP-RAG-SIMPLE] retrieve() called | query: {query[:80]}...")
    t_query = time.time()

    # 쿼리 임베딩 (async)
    query_vector = await embeddings.aembed_query(query)

    # FAISS 유사도 검색
    retrieved_docs = vectorstore.similarity_search_by_vector(query_vector, k=8)

    log(f"[MCP-RAG-SIMPLE] retrieve() done | {len(retrieved_docs)} docs in {time.time() - t_query:.2f}s")

    # XML 형식으로 반환 (source, page 메타데이터 포함)
    from rag.utils import format_docs
    return format_docs(retrieved_docs)


if __name__ == "__main__":
    mcp.run(transport="stdio")
