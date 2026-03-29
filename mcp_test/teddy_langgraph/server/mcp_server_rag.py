from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Any
from pathlib import Path
import os
import sys
import time


_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_rag_debug.log")


def log(msg: str):
    """stderr + 파일로 디버그 로그를 출력합니다 (stdio 전송에서 stdout은 MCP 프로토콜용)."""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with open(_log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


log("[MCP-RAG] Server module loading...")
load_dotenv(override=True)


def create_vectorstore_and_embeddings() -> tuple:
    """PDF 문서에서 Vectorstore와 Embeddings를 생성합니다.

    FAISS 인덱스 캐시가 존재하면 PDF 로딩/분할을 건너뛰고 캐시에서 바로 로드합니다.
    캐시가 없을 때만 PDF를 로드하고 임베딩을 생성합니다.

    Returns:
        (vectorstore, embeddings) 튜플
    """
    t_start = time.time()
    from rag.pdf import PDFRetrievalChain

    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(current_dir, "data", "SPRI_AI_Brief_2023년12월호_F.pdf")
    log(f"[MCP-RAG] create_vectorstore() started | PDF: {pdf_path}")

    # PDFRetrievalChain 인스턴스를 생성하여 캐시 경로를 결정합니다
    pdf_chain = PDFRetrievalChain([pdf_path])
    index_path = str(pdf_chain.index_dir / "faiss_index")
    log(f"[MCP-RAG] Cache index path: {index_path}")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # FAISS 인덱스 캐시가 존재하면 PDF 로딩 없이 바로 로드합니다
    if Path(index_path).is_dir() and (Path(index_path) / "index.faiss").exists():
        log("[MCP-RAG] FAISS cache found! Loading from cache (skipping PDF loading)...")
        t_cache = time.time()
        vectorstore = FAISS.load_local(
            index_path, embeddings, allow_dangerous_deserialization=True
        )
        log(f"[MCP-RAG] Cache loaded in {time.time() - t_cache:.2f}s | Total: {time.time() - t_start:.2f}s")
        return vectorstore, embeddings

    # 캐시가 없으면 PDF를 로드하고 벡터스토어를 생성합니다
    log("[MCP-RAG] No cache found. Building from PDF...")

    t_step = time.time()
    log("[MCP-RAG] Step 1/4: Loading PDF documents...")
    docs = pdf_chain.load_documents(pdf_chain.source_uri)
    log(f"[MCP-RAG] Step 1/4: Done ({len(docs)} docs loaded) in {time.time() - t_step:.2f}s")

    t_step = time.time()
    log("[MCP-RAG] Step 2/4: Creating text splitter...")
    text_splitter = pdf_chain.create_text_splitter()
    log(f"[MCP-RAG] Step 2/4: Done in {time.time() - t_step:.2f}s")

    t_step = time.time()
    log("[MCP-RAG] Step 3/4: Splitting documents...")
    split_docs = pdf_chain.split_documents(docs, text_splitter)
    log(f"[MCP-RAG] Step 3/4: Done ({len(split_docs)} chunks) in {time.time() - t_step:.2f}s")

    t_step = time.time()
    log("[MCP-RAG] Step 4/4: Creating vectorstore (embedding API calls)...")
    vectorstore = pdf_chain.create_vectorstore(split_docs)
    log(f"[MCP-RAG] Step 4/4: Done in {time.time() - t_step:.2f}s")

    log(f"[MCP-RAG] create_vectorstore() completed | Total: {time.time() - t_start:.2f}s")
    return vectorstore, embeddings


# FastMCP 서버 초기화 및 구성
mcp = FastMCP(
    "Retriever",
    instructions="데이터베이스에서 정보를 검색할 수 있는 Retriever입니다.",
)

# 서버 시작 시 Vectorstore와 Embeddings를 한 번만 생성합니다
vectorstore, embeddings = create_vectorstore_and_embeddings()
log("[MCP-RAG] Server ready! Waiting for requests...")


@mcp.tool()
async def retrieve(query: str) -> str:
    """쿼리를 기반으로 문서 데이터베이스에서 정보를 검색합니다.

    이 함수는 Retriever를 사용하여 제공된 쿼리로 검색을 수행한 후,
    검색된 모든 문서의 내용을 연결하여 반환합니다.

    Args:
        query: 관련 정보를 찾기 위한 검색 쿼리

    Returns:
        검색된 모든 문서의 텍스트 내용을 연결한 문자열
    """

    log(f"[MCP-RAG] retrieve() called | query: {query[:80]}...")
    t_query = time.time()

    # Step 1: 쿼리 임베딩 (async OpenAI API 호출)
    log("[MCP-RAG] retrieve() step 1: Embedding query (async)...")
    t_step = time.time()
    query_vector = await embeddings.aembed_query(query)
    log(f"[MCP-RAG] retrieve() step 1: Done in {time.time() - t_step:.2f}s")

    # Step 2: FAISS 유사도 검색 (CPU 연산, 즉시 완료)
    log("[MCP-RAG] retrieve() step 2: FAISS similarity search...")
    t_step = time.time()
    retrieved_docs = vectorstore.similarity_search_by_vector(query_vector, k=8)
    log(f"[MCP-RAG] retrieve() step 2: Done in {time.time() - t_step:.2f}s")

    log(f"[MCP-RAG] retrieve() done | {len(retrieved_docs)} docs retrieved in {time.time() - t_query:.2f}s")

    # 모든 문서 내용을 줄바꿈으로 연결하여 단일 문자열로 반환합니다
    return "\n".join([doc.page_content for doc in retrieved_docs])


if __name__ == "__main__":
    # MCP 클라이언트와의 통합을 위해 stdio 전송 방식으로 서버를 실행합니다
    mcp.run(transport="stdio")
