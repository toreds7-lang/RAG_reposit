import os
from pathlib import Path

from state import AgentState


def rag_retriever(state: AgentState) -> dict:
    """Retrieve relevant code from existing codebase via vector search.

    Requires CODEBASE_DIR env var to be set. If not set or empty, skips.
    Uses FAISS + OpenAI-compatible embeddings API (same base_url as LLM).
    """
    codebase_dir = os.getenv("CODEBASE_DIR", "")

    if not codebase_dir or not Path(codebase_dir).exists():
        return {
            "rag_context": None,
            "logs": [{"node": "rag_retriever", "status": "skipped (no CODEBASE_DIR)"}],
        }

    try:
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        # 1. Load .py files from codebase
        loader = DirectoryLoader(
            codebase_dir,
            glob="**/*.py",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        docs = loader.load()

        if not docs:
            return {
                "rag_context": None,
                "logs": [{"node": "rag_retriever", "status": "no .py files found"}],
            }

        # 2. Chunk documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )
        chunks = splitter.split_documents(docs)

        # 3. Embed via OpenAI-compatible API (same server as LLM)
        embeddings = OpenAIEmbeddings(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
        vectorstore = FAISS.from_documents(chunks, embeddings)

        # 4. Search
        query = f"{state['goal']} {state.get('plan', '')}"
        results = vectorstore.similarity_search(query, k=3)

        context = "\n---\n".join([doc.page_content for doc in results])

        return {
            "rag_context": context[:2000],
            "logs": [
                {
                    "node": "rag_retriever",
                    "status": "success",
                    "chunks_indexed": len(chunks),
                    "results_found": len(results),
                }
            ],
        }

    except ImportError as e:
        return {
            "rag_context": None,
            "logs": [{"node": "rag_retriever", "status": f"skipped (missing dep: {e})"}],
        }
    except Exception as e:
        return {
            "rag_context": None,
            "logs": [{"node": "rag_retriever", "status": f"error: {e}"}],
        }
