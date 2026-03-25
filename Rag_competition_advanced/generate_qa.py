"""
generate_qa.py
==============
Automatically generate questions AND ground-truth answers from a PDF.

Usage:
    python generate_qa.py \
        --pdf path/to/document.pdf \
        --num_questions 20 \
        --output qa_dataset.json

Outputs:
    qa_dataset.json  — structured Q&A pairs with metadata
    questions.txt    — plain question list (feed directly into rag_competition.py)

Question types generated:
    - Factual       : specific facts, figures, dates, names
    - Conceptual    : definitions, explanations of ideas
    - Inferential   : reasoning across multiple parts of the document
    - Summary       : high-level overview questions
"""

import os
import json
import time
import argparse
import textwrap
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

LLM_MODEL         = "gpt-4o"
TEMPERATURE       = 0.4       # slight creativity for question diversity
CHUNK_SIZE        = 1500      # larger chunks → richer context per question
CHUNK_OVERLAP     = 200
QUESTIONS_PER_CHUNK = 2       # how many Q&A pairs to generate per chunk
DELAY_SECONDS     = 0.4


QUESTION_TYPES = ["factual", "conceptual", "inferential", "summary", "table"]


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

TABLE_QA_PROMPT = """You are building a RAG evaluation dataset from a document that contains tables.

The chunk below contains tabular data (numbers, metrics, statistics, comparisons).

Document chunk:
\"\"\"
{chunk}
\"\"\"

Rules:
- Generate {n} questions that specifically require reading values FROM the table.
- Questions should ask about specific numbers, years, comparisons, rankings, or trends visible in the table.
- Answers must cite the exact figures from the table.
- Do NOT ask vague questions like "what does the table show?" — ask specific data questions.
- Write ALL questions and answers in Korean (한국어).

Return ONLY a valid JSON array — no markdown fences, no extra text:
[
  {{
    "question": "...",
    "answer": "...",
    "type": "table",
    "chunk_reference": "{page_ref}"
  }},
  ...
]
"""

QA_GENERATION_PROMPT = """You are building a RAG evaluation dataset from a document.

Given the document chunk below, generate {n} high-quality question-answer pairs.

Document chunk:
\"\"\"
{chunk}
\"\"\"

Rules:
- Questions must be answerable using ONLY the information in this chunk.
- Vary question types across: factual, conceptual, inferential.
- Answers must be complete, accurate, and 1–4 sentences long.
- Do NOT generate vague or trivial questions like "What is this document about?"
- Do NOT repeat similar questions.
- Write ALL questions and answers in Korean (한국어).

Return ONLY a valid JSON array — no markdown fences, no extra text:
[
  {{
    "question": "...",
    "answer": "...",
    "type": "factual | conceptual | inferential",
    "chunk_reference": "{chunk_id}"
  }},
  ...
]
"""

SUMMARY_QA_PROMPT = """You are building a RAG evaluation dataset.

Given the full document text below, generate {n} high-level summary and cross-section questions with ideal answers.

Document (truncated to first {max_chars} chars):
\"\"\"
{document}
\"\"\"

Rules:
- Questions should require understanding multiple parts of the document.
- Answers must be accurate, comprehensive, and 2–5 sentences long.
- Include questions about: main topic, key conclusions, important entities, overall structure.
- Write ALL questions and answers in Korean (한국어).

Return ONLY a valid JSON array — no markdown fences, no extra text:
[
  {{
    "question": "...",
    "answer": "...",
    "type": "summary",
    "chunk_reference": "full_document"
  }},
  ...
]
"""

IRRELEVANT_QA_PROMPT = """You are building a RAG evaluation dataset.

The document below is about a specific topic. Your job is to generate {n} questions that seem
plausible but CANNOT be answered using this document — the correct answer is "I don't know from this PDF."

Document summary (first {max_chars} chars):
\"\"\"
{document}
\"\"\"

Rules:
- Questions must look reasonable and on-topic at first glance, but require information NOT present in the document.
- Cover diverse angles: specific statistics not mentioned, events outside the document's scope,
  comparisons with other companies/years not covered, internal details not disclosed, future plans not stated.
- Do NOT generate obviously silly or off-topic questions (e.g. "What is 2+2?").
- Write ALL questions in Korean (한국어).

Return ONLY a valid JSON array — no markdown fences, no extra text:
[
  {{
    "question": "...",
    "answer": "정보가 없음",
    "type": "irrelevant",
    "chunk_reference": "out_of_scope"
  }},
  ...
]
"""

DEDUP_PROMPT = """You are a dataset quality reviewer.

Below is a list of questions from a RAG evaluation dataset. Remove duplicates or near-duplicates 
(same intent, slightly different wording). Keep the better-phrased version of each duplicate pair.

Questions (JSON array):
{questions_json}

Return ONLY a JSON array of the question strings to KEEP — no markdown fences, no extra text:
["question 1", "question 2", ...]
"""


# ══════════════════════════════════════════════════════════════════════════════
# PDF LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_pdf(pdf_path: str) -> tuple[str, list[dict]]:
    """
    Returns:
        full_text  : entire document as a single string
        page_texts : list of {page, text} dicts
    """
    reader = PdfReader(pdf_path)
    page_texts = []
    full_parts = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            page_texts.append({"page": page_num, "text": text})
            full_parts.append(text)

    full_text = "\n\n".join(full_parts)
    print(f"[PDF] {len(reader.pages)} pages, {len(full_text):,} characters extracted")
    return full_text, page_texts


def split_into_chunks(full_text: str, page_texts: list[dict]) -> list[tuple[str, str, str]]:
    """Split full text into chunks. Returns list of (chunk_id, chunk_text, page_ref)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    docs = splitter.create_documents([full_text])

    # Build character offset ranges per page
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
        page_ref  = find_page(start_idx)
        result.append((f"chunk_{i+1}", doc.page_content, page_ref))

    print(f"[Splitter] {len(result)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# JSON PARSING (robust)
# ══════════════════════════════════════════════════════════════════════════════

def safe_parse_json(raw: str, fallback=None):
    """Strip markdown fences and parse JSON safely."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        return fallback if fallback is not None else []


# ══════════════════════════════════════════════════════════════════════════════
# QA GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_chunk_qa(
    chunks: list[tuple[str, str, str]],
    llm,
    questions_per_chunk: int,
    delay: float,
) -> list[dict]:
    """Generate Q&A pairs from individual chunks (factual / conceptual / inferential)."""
    prompt = ChatPromptTemplate.from_template(QA_GENERATION_PROMPT)
    chain  = prompt | llm | StrOutputParser()

    all_pairs = []
    total = len(chunks)

    for i, (chunk_id, chunk_text, page_ref) in enumerate(chunks, start=1):
        print(f"  [Chunk {i}/{total}] ({page_ref}) Generating {questions_per_chunk} Q&A pairs...")
        try:
            raw = chain.invoke({
                "n":        questions_per_chunk,
                "chunk":    chunk_text,
                "chunk_id": chunk_id,
            })
            pairs = safe_parse_json(raw)
            if isinstance(pairs, list):
                for p in pairs:
                    p["chunk_reference"] = page_ref
                all_pairs.extend(pairs)
        except Exception as e:
            print(f"    ⚠️  Error on {chunk_id}: {e}")

        if delay:
            time.sleep(delay)

    print(f"[Chunk QA] Generated {len(all_pairs)} raw Q&A pairs from chunks")
    return all_pairs


def detect_table_chunks(chunks: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Return chunks that are likely to contain tabular data."""
    import re
    table_chunks = []
    for chunk_id, text, page_ref in chunks:
        # Heuristic: many digits/numbers or repeated whitespace-separated columns
        digit_density = len(re.findall(r'\d+', text)) / max(len(text.split()), 1)
        has_numbers   = digit_density > 0.15
        has_columns   = bool(re.search(r'(\S+\s{2,}\S+){2,}', text))  # multiple wide-spaced tokens
        has_units     = bool(re.search(r'(톤|MWh|tCO2|%|억|천|만|명|건|개|GWh|kWh)', text))
        if (has_numbers and has_units) or (has_columns and has_numbers):
            table_chunks.append((chunk_id, text, page_ref))
    print(f"[Table Detection] Found {len(table_chunks)} table-like chunks")
    return table_chunks


def generate_table_qa(
    chunks: list[tuple[str, str, str]],
    llm,
    n_total: int,
    delay: float,
) -> list[dict]:
    """Generate Q&A pairs that require reading specific values from tables."""
    if not chunks:
        print("  [Table QA] No table chunks found — skipping")
        return []

    prompt = ChatPromptTemplate.from_template(TABLE_QA_PROMPT)
    chain  = prompt | llm | StrOutputParser()

    # Distribute questions across table chunks
    import math
    qpc   = math.ceil(n_total / len(chunks))
    pairs = []

    for i, (chunk_id, text, page_ref) in enumerate(chunks, start=1):
        need = n_total - len(pairs)
        if need <= 0:
            break
        n = min(qpc, need)
        print(f"  [Table QA {i}/{len(chunks)}] ({page_ref}) Generating {n} table Q&A pairs...")
        try:
            raw = chain.invoke({"n": n, "chunk": text, "page_ref": page_ref})
            batch = safe_parse_json(raw)
            if isinstance(batch, list):
                for p in batch:
                    p["type"] = "table"
                    p["chunk_reference"] = page_ref
                pairs.extend(batch)
        except Exception as e:
            print(f"    Warning: Table QA error: {e}")
        if delay:
            time.sleep(delay)

    print(f"[Table QA] Generated {len(pairs)} table Q&A pairs")
    return pairs


def generate_summary_qa(
    full_text: str,
    llm,
    n: int = 5,
    max_chars: int = 10_000,
) -> list[dict]:
    """Generate high-level summary/cross-section Q&A pairs from the full document."""
    prompt = ChatPromptTemplate.from_template(SUMMARY_QA_PROMPT)
    chain  = prompt | llm | StrOutputParser()

    print(f"  [Summary QA] Generating {n} summary questions...")
    try:
        raw = chain.invoke({
            "n":         n,
            "document":  full_text[:max_chars],
            "max_chars": max_chars,
        })
        pairs = safe_parse_json(raw)
        if isinstance(pairs, list):
            print(f"[Summary QA] Generated {len(pairs)} summary Q&A pairs")
            return pairs
    except Exception as e:
        print(f"  ⚠️  Summary QA error: {e}")

    return []


def generate_irrelevant_qa(
    full_text: str,
    llm,
    n: int = 5,
    max_chars: int = 6_000,
) -> list[dict]:
    """Generate out-of-scope questions whose correct answer is 'I don't know from this PDF'."""
    prompt = ChatPromptTemplate.from_template(IRRELEVANT_QA_PROMPT)
    chain  = prompt | llm | StrOutputParser()

    print(f"  [Irrelevant QA] Generating {n} out-of-scope questions...")
    try:
        raw = chain.invoke({
            "n":         n,
            "document":  full_text[:max_chars],
            "max_chars": max_chars,
        })
        pairs = safe_parse_json(raw)
        if isinstance(pairs, list):
            for p in pairs:
                p["type"] = "irrelevant"
                p["chunk_reference"] = "out_of_scope"
                p["answer"] = "정보가 없음"
            print(f"[Irrelevant QA] Generated {len(pairs)} irrelevant Q&A pairs")
            return pairs
    except Exception as e:
        print(f"  Warning: Irrelevant QA error: {e}")

    return []


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def deduplicate_questions(qa_pairs: list[dict], llm) -> list[dict]:
    """Use the LLM to remove duplicate or near-duplicate questions."""
    if len(qa_pairs) <= 1:
        return qa_pairs

    questions = [p["question"] for p in qa_pairs]
    prompt    = ChatPromptTemplate.from_template(DEDUP_PROMPT)
    chain     = prompt | llm | StrOutputParser()

    print(f"[Dedup] Deduplicating {len(questions)} questions...")
    try:
        raw  = chain.invoke({"questions_json": json.dumps(questions, ensure_ascii=False)})
        keep = safe_parse_json(raw, fallback=questions)

        keep_set    = set(keep)
        deduped     = [p for p in qa_pairs if p["question"] in keep_set]
        removed     = len(qa_pairs) - len(deduped)
        print(f"[Dedup] Removed {removed} duplicates → {len(deduped)} unique Q&A pairs")
        return deduped
    except Exception as e:
        print(f"  ⚠️  Dedup error: {e}. Skipping deduplication.")
        return qa_pairs


# ══════════════════════════════════════════════════════════════════════════════
# QUESTION TYPE BALANCING
# ══════════════════════════════════════════════════════════════════════════════

def balance_and_trim(qa_pairs: list[dict], target: int) -> list[dict]:
    """
    Keep a balanced mix of question types up to the target count.
    Irrelevant questions are always kept as-is; remaining slots are balanced
    across factual, conceptual, inferential, summary.
    """
    from collections import defaultdict
    import math

    irrelevant = [p for p in qa_pairs if p.get("type", "").lower() == "irrelevant"]
    table      = [p for p in qa_pairs if p.get("type", "").lower() == "table"]
    relevant   = [p for p in qa_pairs if p.get("type", "").lower() not in ("irrelevant", "table")]

    reserved        = irrelevant + table
    relevant_target = max(0, target - len(reserved))

    by_type = defaultdict(list)
    for pair in relevant:
        qtype = pair.get("type", "factual").lower()
        by_type[qtype].append(pair)

    types_present = list(by_type.keys())
    per_type      = math.ceil(relevant_target / max(len(types_present), 1))

    balanced = []
    for qtype in QUESTION_TYPES:
        items = by_type.get(qtype, [])
        balanced.extend(items[:per_type])

    # Fill remaining slots if some types had fewer items
    seen_ids = {id(p) for p in balanced}
    for pair in relevant:
        if len(balanced) >= relevant_target:
            break
        if id(pair) not in seen_ids:
            balanced.append(pair)
            seen_ids.add(id(pair))

    result = balanced[:relevant_target] + reserved
    print(f"[Balance] Trimmed to {len(result)} Q&A pairs (target={target}, table={len(table)}, irrelevant={len(irrelevant)})")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def save_outputs(
    qa_pairs:     list[dict],
    pdf_path:     str,
    output_json:  str,
    questions_txt: str,
):
    # Assign final IDs
    for i, pair in enumerate(qa_pairs, start=1):
        pair["id"] = i

    # Count type distribution
    from collections import Counter
    type_dist = dict(Counter(p.get("type", "unknown") for p in qa_pairs))

    # JSON dataset
    dataset = {
        "metadata": {
            "pdf":              pdf_path,
            "total_qa_pairs":  len(qa_pairs),
            "llm_model":        LLM_MODEL,
            "type_distribution": type_dist,
        },
        "qa_pairs": qa_pairs,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Q&A dataset saved   → '{output_json}'")

    # Plain questions.txt for rag_competition.py
    with open(questions_txt, "w", encoding="utf-8") as f:
        for pair in qa_pairs:
            f.write(pair["question"] + "\n")
    print(f"✅ Questions file saved → '{questions_txt}'")

    # Print a preview
    print("\n── Sample Q&A pairs ──────────────────────────────────────────")
    for pair in qa_pairs[:3]:
        print(f"\n[{pair['id']}] [{pair.get('type','?').upper()}]")
        print(f"  Q: {textwrap.fill(pair['question'], width=70, subsequent_indent='     ')}")
        print(f"  A: {textwrap.fill(pair['answer'],   width=70, subsequent_indent='     ')}")
    print("──────────────────────────────────────────────────────────────")
    print(f"\nType distribution: {type_dist}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate Q&A dataset from a PDF for RAG evaluation"
    )
    parser.add_argument("--pdf",             default="data/2025_SK하이닉스_지속가능경영보고서.pdf",  help="Path to the PDF file")
    parser.add_argument("--num_questions",   type=int, default=30,           help="Target total number of Q&A pairs")
    parser.add_argument("--num_irrelevant",  type=int, default=3,            help="How many out-of-scope '정보가 없음' questions to include")
    parser.add_argument("--num_table",       type=int, default=4,            help="Minimum number of table-based questions to include")
    parser.add_argument("--output",          default="qa_dataset.json",      help="Output JSON dataset path")
    parser.add_argument("--questions_txt",   default="questions.txt",        help="Output plain questions file")
    parser.add_argument("--no_dedup",        action="store_true",            help="Skip LLM deduplication step")
    args = parser.parse_args()

    # Validate
    if not Path(args.pdf).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

    llm = ChatOpenAI(model=LLM_MODEL, temperature=TEMPERATURE)

    # ── Load PDF ───────────────────────────────────────────────────────────────
    full_text, page_texts = load_pdf(args.pdf)
    chunks                = split_into_chunks(full_text, page_texts)

    # ── How many chunks to use ─────────────────────────────────────────────────
    # Reserve quota for table + irrelevant; rest split between chunk and summary
    table_count      = args.num_table
    irrelevant_count = args.num_irrelevant
    relevant_target  = args.num_questions - irrelevant_count - table_count
    summary_count    = max(3, relevant_target // 4)
    chunk_target     = relevant_target - summary_count
    qpc              = QUESTIONS_PER_CHUNK

    # Evenly sample chunks across the entire document so questions span all pages
    max_chunks = -(-chunk_target // qpc)   # ceiling division
    if max_chunks >= len(chunks):
        selected_chunks = chunks
    else:
        step = len(chunks) / max_chunks
        selected_chunks = [chunks[int(i * step)] for i in range(max_chunks)]

    print(f"\n[Plan] Target: {args.num_questions} Q&A pairs total")
    print(f"       Chunk Q&A:      {chunk_target} from {len(selected_chunks)} chunks")
    print(f"       Summary Q&A:    {summary_count}")
    print(f"       Table Q&A:      {table_count}")
    print(f"       Irrelevant Q&A: {irrelevant_count}\n")

    # ── Generate ───────────────────────────────────────────────────────────────
    print("── Step 1: Generating chunk-level Q&A pairs ──────────────────")
    chunk_pairs = generate_chunk_qa(selected_chunks, llm, qpc, DELAY_SECONDS)

    print("\n── Step 2: Generating summary Q&A pairs ──────────────────────")
    summary_pairs = generate_summary_qa(full_text, llm, n=summary_count)

    print("\n── Step 3: Generating table Q&A pairs ────────────────────────")
    table_chunks = detect_table_chunks(chunks)
    table_pairs  = generate_table_qa(table_chunks, llm, n_total=table_count, delay=DELAY_SECONDS)

    print("\n── Step 4: Generating irrelevant (out-of-scope) Q&A pairs ────")
    irrelevant_pairs = generate_irrelevant_qa(full_text, llm, n=irrelevant_count)

    all_relevant = chunk_pairs + summary_pairs
    print(f"\n[Total] {len(all_relevant)} relevant + {len(table_pairs)} table + {len(irrelevant_pairs)} irrelevant pairs before dedup/trim")

    # ── Deduplicate (relevant only) ────────────────────────────────────────────
    if not args.no_dedup and len(all_relevant) > 1:
        print("\n── Step 5: Deduplicating relevant pairs ──────────────────────")
        all_relevant = deduplicate_questions(all_relevant, llm)

    all_pairs = all_relevant + table_pairs + irrelevant_pairs

    # ── Balance & trim ─────────────────────────────────────────────────────────
    print("\n── Step 6: Balancing & trimming ──────────────────────────────")
    final_pairs = balance_and_trim(all_pairs, args.num_questions)

    # ── Save ───────────────────────────────────────────────────────────────────
    print("\n── Saving outputs ────────────────────────────────────────────")
    save_outputs(final_pairs, args.pdf, args.output, args.questions_txt)


if __name__ == "__main__":
    main()
