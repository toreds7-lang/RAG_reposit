"""
llm_judge.py
============
LLM-as-Judge — Scores answers produced by rag_competition.py

Usage:
    python llm_judge.py \
        --answers answers.json \
        --pdf path/to/document.pdf \
        --output scores.json

Scoring criteria (each 1–5):
    1. Relevance      — Does the answer address the question?
    2. Accuracy       — Is the answer factually correct per the document?
    3. Completeness   — Does it cover the key aspects of the answer?
    4. Conciseness    — Is it free of unnecessary filler or repetition?
    5. Groundedness   — Is it grounded in the document (no hallucination)?

Final score = mean of the five criteria scores (1.0 – 5.0).
"""

import os
import json
import time
import argparse
import statistics
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from pypdf import PdfReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

JUDGE_MODEL   = "gpt-4o"     # Use a strong model for judging
TEMPERATURE   = 0
DELAY_SECONDS = 0.5          # Pause between API calls

JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator assessing the quality of a RAG system's answer.

=== DOCUMENT EXCERPT (ground truth context) ===
{context}
=== END DOCUMENT EXCERPT ===

=== QUESTION ===
{question}

=== ANSWER TO EVALUATE ===
{answer}

=== EVALUATION TASK ===
Score the answer on each of the following criteria from 1 (very poor) to 5 (excellent).
Return your evaluation ONLY as a valid JSON object with this exact structure:

{{
  "relevance":     <1-5>,
  "accuracy":      <1-5>,
  "completeness":  <1-5>,
  "conciseness":   <1-5>,
  "groundedness":  <1-5>,
  "reasoning":     "<one or two sentences explaining the scores>"
}}

Criteria definitions:
- relevance:    Does the answer directly address the question asked?
- accuracy:     Is the answer factually correct based on the document excerpt?
- completeness: Does the answer cover the key aspects required to fully answer the question?
- conciseness:  Is the answer free of unnecessary filler, repetition, or verbosity?
- groundedness: Is the answer grounded in the document with no hallucinated content?

Important:
- Do NOT include markdown fences or any text outside the JSON object.
- Base accuracy and groundedness judgements solely on the document excerpt above.
"""


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def load_pdf_text(pdf_path: str, max_chars: int = 12_000) -> str:
    """
    Extract full text from PDF, capped at max_chars to stay within
    the judge's context window. The cap is applied from the beginning,
    which is usually the most information-dense part of a document.
    """
    reader = PdfReader(pdf_path)
    pages_text = []
    total = 0
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages_text.append(text)
            total += len(text)
            if total >= max_chars:
                break

    full_text = "\n\n".join(pages_text)
    return full_text[:max_chars]


def load_answers(answers_path: str) -> dict:
    with open(answers_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_scores(raw: str) -> dict:
    """
    Parse JSON from the LLM judge response.
    Strips markdown fences if the model adds them despite instructions.
    """
    raw = raw.strip()
    # Strip ```json ... ``` fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    return json.loads(raw)


SCORE_KEYS = ["relevance", "accuracy", "completeness", "conciseness", "groundedness"]


def compute_final_score(scores: dict) -> float:
    values = [float(scores[k]) for k in SCORE_KEYS if k in scores]
    return round(statistics.mean(values), 2) if values else 0.0


def letter_grade(score: float) -> str:
    if score >= 4.5: return "A"
    if score >= 4.0: return "B+"
    if score >= 3.5: return "B"
    if score >= 3.0: return "C+"
    if score >= 2.5: return "C"
    if score >= 2.0: return "D"
    return "F"


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE CHAIN
# ══════════════════════════════════════════════════════════════════════════════

def build_judge_chain():
    llm    = ChatOpenAI(model=JUDGE_MODEL, temperature=TEMPERATURE)
    prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT_TEMPLATE)
    chain  = prompt | llm | StrOutputParser()
    return chain


# ══════════════════════════════════════════════════════════════════════════════
# SCORING LOOP
# ══════════════════════════════════════════════════════════════════════════════

def score_answers(
    results: list[dict],
    context: str,
    judge_chain,
    delay: float = DELAY_SECONDS,
) -> list[dict]:
    """
    Run each question/answer pair through the LLM judge.
    Returns list of enriched result dicts with scores appended.
    """
    scored = []
    total  = len(results)

    for item in results:
        qid      = item["id"]
        question = item["question"]
        answer   = item["answer"]

        print(f"[Judge {qid}/{total}] Scoring: {question[:70]}...")

        try:
            raw_response = judge_chain.invoke({
                "context":  context,
                "question": question,
                "answer":   answer,
            })
            scores       = parse_scores(raw_response)
            final_score  = compute_final_score(scores)
            grade        = letter_grade(final_score)
            error        = None
        except Exception as e:
            print(f"  ⚠️  Judge error on Q{qid}: {e}")
            scores      = {k: None for k in SCORE_KEYS}
            scores["reasoning"] = f"Judge error: {e}"
            final_score = None
            grade       = "N/A"
            error       = str(e)

        scored.append({
            **item,
            "scores":      scores,
            "final_score": final_score,
            "grade":       grade,
            "error":       error,
        })

        if delay:
            time.sleep(delay)

    return scored


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def compute_summary(scored: list[dict]) -> dict:
    valid_scores = [s["final_score"] for s in scored if s["final_score"] is not None]

    if not valid_scores:
        return {"error": "No valid scores computed."}

    per_criterion = {}
    for key in SCORE_KEYS:
        vals = [s["scores"][key] for s in scored
                if s["scores"].get(key) is not None]
        per_criterion[key] = round(statistics.mean(vals), 2) if vals else None

    return {
        "total_questions":   len(scored),
        "scored_questions":  len(valid_scores),
        "mean_final_score":  round(statistics.mean(valid_scores), 2),
        "median_final_score": round(statistics.median(valid_scores), 2),
        "min_final_score":   round(min(valid_scores), 2),
        "max_final_score":   round(max(valid_scores), 2),
        "overall_grade":     letter_grade(statistics.mean(valid_scores)),
        "per_criterion_avg": per_criterion,
        "score_distribution": {
            "A  (≥4.5)":  sum(1 for s in valid_scores if s >= 4.5),
            "B+ (≥4.0)":  sum(1 for s in valid_scores if 4.0 <= s < 4.5),
            "B  (≥3.5)":  sum(1 for s in valid_scores if 3.5 <= s < 4.0),
            "C  (≥2.5)":  sum(1 for s in valid_scores if 2.5 <= s < 3.5),
            "D/F (<2.5)":  sum(1 for s in valid_scores if s < 2.5),
        },
    }


def print_summary(summary: dict):
    print("\n" + "═" * 55)
    print("  LLM JUDGE — EVALUATION SUMMARY")
    print("═" * 55)
    print(f"  Questions scored  : {summary['scored_questions']} / {summary['total_questions']}")
    print(f"  Mean score        : {summary['mean_final_score']} / 5.0  ({summary['overall_grade']})")
    print(f"  Median score      : {summary['median_final_score']}")
    print(f"  Range             : {summary['min_final_score']} – {summary['max_final_score']}")
    print()
    print("  Per-Criterion Averages:")
    for criterion, avg in summary["per_criterion_avg"].items():
        bar = "█" * int(avg) + "░" * (5 - int(avg))
        print(f"    {criterion:<14} {bar}  {avg}")
    print()
    print("  Grade Distribution:")
    for grade, count in summary["score_distribution"].items():
        print(f"    {grade}  → {count} question(s)")
    print("═" * 55)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge — Score RAG answers")
    parser.add_argument("--answers", required=True,  help="Path to answers.json from rag_competition.py")
    parser.add_argument("--pdf",     default="data/2025_SK하이닉스_지속가능경영보고서.pdf",  help="Path to the original PDF (used as ground truth)")
    parser.add_argument("--output",  default="scores.json", help="Output JSON file path")
    args = parser.parse_args()

    # Validate
    if not Path(args.answers).exists():
        raise FileNotFoundError(f"Answers file not found: {args.answers}")
    if not Path(args.pdf).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

    # Load inputs
    answers_data = load_answers(args.answers)
    results      = answers_data.get("results", [])
    print(f"[Judge] Loaded {len(results)} answers from '{args.answers}'")

    context      = load_pdf_text(args.pdf)
    print(f"[Judge] Loaded {len(context):,} chars of PDF context from '{args.pdf}'")

    # Judge
    judge_chain  = build_judge_chain()
    scored       = score_answers(results, context, judge_chain)

    # Summary
    summary      = compute_summary(scored)
    print_summary(summary)

    # Save
    output = {
        "metadata": {
            "answers_file": args.answers,
            "pdf":          args.pdf,
            "judge_model":  JUDGE_MODEL,
            "criteria":     SCORE_KEYS,
            "scale":        "1 (very poor) – 5 (excellent)",
        },
        "summary": summary,
        "scored_results": scored,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Scores saved to '{args.output}'")


if __name__ == "__main__":
    main()
