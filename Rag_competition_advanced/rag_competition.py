"""
rag_competition.py
==================
RAG Competition Entry — PDF-based Question Answering

Usage:
    python rag_competition.py \
        --pdf path/to/document.pdf \
        --questions questions.txt \
        --output answers.json

questions.txt format (one question per line):
    What is the main topic of the document?
    Who are the key stakeholders mentioned?
    ...
"""

import os
import json
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── PDF text extraction ────────────────────────────────────────────────────────
from pypdf import PdfReader

# ── Text splitting ─────────────────────────────────────────────────────────────
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Embeddings & vector store ──────────────────────────────────────────────────
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS

# ── LangChain core ─────────────────────────────────────────────────────────────
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL       = "gpt-4o-mini"
CHUNK_SIZE      = 800
CHUNK_OVERLAP   = 150
TOP_K           = 5   # Number of chunks retrieved per question

RAG_PROMPT_TEMPLATE = """You are an expert assistant answering questions based strictly on the provided context.

Context:
{context}

Question: {question}

Instructions:
- Answer concisely and accurately using only the context above.
- If the answer is not in the context, say "Not found in the document."
- Do not hallucinate or add external knowledge.

Answer:"""


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load & parse PDF
# ══════════════════════════════════════════════════════════════════════════════

def load_pdf(pdf_path: str) -> list[Document]:
    """Extract text from each page of the PDF and return as LangChain Documents."""
    reader = PdfReader(pdf_path)
    docs = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            docs.append(Document(
                page_content=text,
                metadata={"source": pdf_path, "page": page_num}
            ))
    print(f"[PDF] Loaded {len(reader.pages)} pages → {len(docs)} non-empty pages")
    return docs


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Chunk documents
# ══════════════════════════════════════════════════════════════════════════════

def split_documents(docs: list[Document]) -> list[Document]:
    """Split documents into overlapping chunks for better retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"[Splitter] {len(docs)} pages → {len(chunks)} chunks "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Build FAISS vector store
# ══════════════════════════════════════════════════════════════════════════════

def build_vectorstore(chunks: list[Document]) -> FAISS:
    """Embed chunks and store in FAISS."""
    print(f"[Embeddings] Embedding {len(chunks)} chunks with '{EMBEDDING_MODEL}'...")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    print("[Embeddings] Vector store ready.")
    return vectorstore


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Build RAG chain
# ══════════════════════════════════════════════════════════════════════════════

def build_rag_chain(vectorstore: FAISS):
    """Construct the retrieval-augmented generation chain."""
    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

    def format_docs(docs: list[Document]) -> str:
        return "\n\n---\n\n".join(
            f"[Page {d.metadata.get('page', '?')}]\n{d.page_content}"
            for d in docs
        )

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain, retriever


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Answer questions
# ══════════════════════════════════════════════════════════════════════════════

def answer_questions(
    questions: list[str],
    chain,
    retriever,
    delay: float = 0.3,
) -> list[dict]:
    """
    Run each question through the RAG chain and collect results.

    Returns a list of dicts with keys:
        id, question, answer, retrieved_pages
    """
    results = []
    total = len(questions)

    for i, question in enumerate(questions, start=1):
        question = question.strip()
        if not question:
            continue

        print(f"[Q {i}/{total}] {question[:80]}...")

        # Retrieve context (also logged for transparency)
        retrieved_docs = retriever.invoke(question)
        retrieved_pages = [d.metadata.get("page", "?") for d in retrieved_docs]

        # Generate answer
        answer = chain.invoke(question)

        results.append({
            "id": i,
            "question": question,
            "answer": answer.strip(),
            "retrieved_pages": retrieved_pages,
        })

        if delay:
            time.sleep(delay)   # rate-limit guard

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="RAG Competition — PDF Q&A")
    parser.add_argument("--pdf",       default="data/2025_SK하이닉스_지속가능경영보고서.pdf",  help="Path to the PDF file")
    parser.add_argument("--questions", required=True,  help="Path to questions file (one per line)")
    parser.add_argument("--output",    default="answers.json", help="Output JSON file path")
    args = parser.parse_args()

    # Validate inputs
    if not Path(args.pdf).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    if not Path(args.questions).exists():
        raise FileNotFoundError(f"Questions file not found: {args.questions}")
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

    # Load questions
    with open(args.questions, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]
    print(f"[Questions] Loaded {len(questions)} questions from '{args.questions}'")

    # Pipeline
    docs        = load_pdf(args.pdf)
    chunks      = split_documents(docs)
    vectorstore = build_vectorstore(chunks)
    chain, retriever = build_rag_chain(vectorstore)
    results     = answer_questions(questions, chain, retriever)

    # Save
    output = {
        "metadata": {
            "pdf":           args.pdf,
            "questions_file": args.questions,
            "llm_model":     LLM_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "chunk_size":    CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "top_k":         TOP_K,
            "total_questions": len(results),
        },
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(results)} answers saved to '{args.output}'")


if __name__ == "__main__":
    main()
