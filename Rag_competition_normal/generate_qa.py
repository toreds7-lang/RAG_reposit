"""
generate_qa.py
==============
PDF에서 팩트 기반 질문-답변 쌍을 생성합니다.

Usage:
    python generate_qa.py \
        --pdf data/2025_SK하이닉스_지속가능경영보고서.pdf \
        --num_questions 30 \
        --output qa_dataset.json

Outputs:
    qa_dataset.json  — Q&A 쌍 (JSON)
    questions.txt    — 질문 목록 (rag_competition에서 사용)
"""

import os
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

LLM_MODEL           = "gpt-4o-mini"
TEMPERATURE         = 0.3
CHUNK_SIZE          = 1500
CHUNK_OVERLAP       = 200
QUESTIONS_PER_CHUNK = 2
DELAY_SECONDS       = 0.3


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT
# ══════════════════════════════════════════════════════════════════════════════

QA_PROMPT = """아래는 문서의 일부 내용입니다.

문서 내용:
\"\"\"
{chunk}
\"\"\"

위 내용에서 {n}개의 질문-답변 쌍을 만들어주세요.

조건:
- 질문은 문서에 나온 구체적인 사실을 묻는 질문이어야 합니다 (이메일, 숫자, 이름, 날짜, 금액 등).
- 답변은 짧고 명확하게 (1~5단어 이내의 팩트).
- 모든 질문과 답변은 한국어로 작성하세요.
- 모호하거나 주관적인 질문은 만들지 마세요.

JSON 배열 형식으로만 출력하세요 (마크다운 없이):
[
  {{
    "question": "...",
    "answer": "...",
    "chunk_reference": "{chunk_id}"
  }},
  ...
]
"""


# ══════════════════════════════════════════════════════════════════════════════
# PDF LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_pdf(pdf_path: str):
    reader = PdfReader(pdf_path)
    page_texts = []
    full_parts = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            page_texts.append({"page": page_num, "text": text})
            full_parts.append(text)

    full_text = "\n\n".join(full_parts)
    print(f"[PDF] {len(reader.pages)} pages, {len(full_text):,} chars extracted")
    return full_text, page_texts


def split_into_chunks(full_text: str, page_texts: list):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    docs = splitter.create_documents([full_text])

    # 페이지별 오프셋 구축
    page_offsets = []
    pos = 0
    for pt in page_texts:
        start = full_text.find(pt["text"], pos)
        if start == -1:
            start = pos
        end = start + len(pt["text"])
        page_offsets.append((start, end, pt["page"]))
        pos = end

    def find_page(char_idx: int) -> str:
        for start, end, page in page_offsets:
            if start <= char_idx < end:
                return f"p.{page}"
        return "p.?"

    result = []
    for i, doc in enumerate(docs):
        start_idx = doc.metadata.get("start_index", 0)
        page_ref = find_page(start_idx)
        result.append((f"chunk_{i+1}", doc.page_content, page_ref))

    print(f"[Splitter] {len(result)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# JSON PARSING
# ══════════════════════════════════════════════════════════════════════════════

def safe_parse_json(raw: str, fallback=None):
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return fallback if fallback is not None else []


# ══════════════════════════════════════════════════════════════════════════════
# QA GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_qa_pairs(chunks: list, llm, questions_per_chunk: int, delay: float) -> list:
    prompt = ChatPromptTemplate.from_template(QA_PROMPT)
    chain = prompt | llm | StrOutputParser()
    all_pairs = []
    total = len(chunks)

    for i, (chunk_id, chunk_text, page_ref) in enumerate(chunks, start=1):
        print(f"  [Chunk {i}/{total}] ({page_ref}) Generating {questions_per_chunk} Q&A pairs...")
        try:
            raw = chain.invoke({
                "n":        questions_per_chunk,
                "chunk":    chunk_text,
                "chunk_id": page_ref,
            })
            pairs = safe_parse_json(raw)
            if isinstance(pairs, list):
                for p in pairs:
                    p["chunk_reference"] = page_ref
                all_pairs.extend(pairs)
        except Exception as e:
            print(f"    Error on {chunk_id}: {e}")

        if delay:
            time.sleep(delay)

    print(f"[QA] Generated {len(all_pairs)} Q&A pairs")
    return all_pairs


# ══════════════════════════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def save_outputs(qa_pairs: list, pdf_path: str, output_json: str, questions_txt: str):
    for i, pair in enumerate(qa_pairs, start=1):
        pair["id"] = i

    dataset = {
        "metadata": {
            "pdf":             pdf_path,
            "total_qa_pairs":  len(qa_pairs),
            "llm_model":       LLM_MODEL,
        },
        "qa_pairs": qa_pairs,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"\n[Save] Q&A dataset  -> '{output_json}'")

    with open(questions_txt, "w", encoding="utf-8") as f:
        for pair in qa_pairs:
            f.write(pair["question"] + "\n")
    print(f"[Save] Questions     -> '{questions_txt}'")

    print("\n-- Sample Q&A --")
    for pair in qa_pairs[:5]:
        print(f"  Q: {pair['question']}")
        print(f"  A: {pair['answer']}")
        print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PDF에서 팩트 Q&A 데이터셋 생성")
    parser.add_argument("--pdf",           default="data/2025_SK하이닉스_지속가능경영보고서.pdf")
    parser.add_argument("--num_questions", type=int, default=30, help="생성할 Q&A 쌍 수")
    parser.add_argument("--output",        default="qa_dataset.json")
    parser.add_argument("--questions_txt", default="questions.txt")
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    llm = ChatOpenAI(model=LLM_MODEL, temperature=TEMPERATURE)

    # PDF 로드 & 청크 분할
    full_text, page_texts = load_pdf(args.pdf)
    chunks = split_into_chunks(full_text, page_texts)

    # 문서 전체에서 균등하게 청크 샘플링
    max_chunks = -(-args.num_questions // QUESTIONS_PER_CHUNK)  # ceiling division
    if max_chunks >= len(chunks):
        selected_chunks = chunks
    else:
        step = len(chunks) / max_chunks
        selected_chunks = [chunks[int(i * step)] for i in range(max_chunks)]

    print(f"\n[Plan] Target: {args.num_questions} Q&A pairs from {len(selected_chunks)} chunks\n")

    # Q&A 생성
    qa_pairs = generate_qa_pairs(selected_chunks, llm, QUESTIONS_PER_CHUNK, DELAY_SECONDS)

    # 목표 수만큼 자르기
    if len(qa_pairs) > args.num_questions:
        qa_pairs = qa_pairs[:args.num_questions]

    # 저장
    save_outputs(qa_pairs, args.pdf, args.output, args.questions_txt)


if __name__ == "__main__":
    main()
