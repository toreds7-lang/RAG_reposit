"""Entry point for PDF deep research — mirrors main.py but targets a single PDF."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from step1_feedback.feedback import generate_feedback
from step2_pdf_research.pdf_ingestion import ingest_pdf
from step2_pdf_research.pdf_search import build_index
from step2_pdf_research.pdf_research import deep_pdf_research
from step3_reporting.reporting import write_final_report
from utils import setup_logging

load_dotenv()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Deep-research a single PDF via hybrid retrieval.")
    p.add_argument("--pdf", default=None, help="Path to the PDF file (prompted if omitted).")
    p.add_argument("--chunk-size", type=int, default=None, help="Override adaptive chunk size (tokens).")
    p.add_argument("--overlap", type=int, default=None, help="Override adaptive chunk overlap (tokens).")
    p.add_argument("--feedback-model", default="gpt-4o-mini")
    p.add_argument("--research-model", default="gpt-4o")
    p.add_argument("--reporting-model", default="gpt-4o")
    p.add_argument("--no-feedback", action="store_true", help="Skip Stage 1 clarifying questions.")
    return p.parse_args()


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== PDF Pipeline started ===")
    args = parse_args()

    pdf_path = args.pdf or input("PDF 파일 경로를 입력하세요: ").strip().strip('"')
    if not os.path.isfile(pdf_path):
        logger.error("PDF not found: %s", pdf_path)
        print(f"오류: PDF 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    query = input("어떤 주제에 대해 PDF를 리서치하시겠습니까?: ")
    logger.info("User query: %.200s", query)

    client = OpenAI()

    # --- Stage 0: Ingest + Index ---
    print("------------------------------------------0단계: PDF 파싱 및 인덱스 구축----------------------------------------------------")
    chunks, cs, ov = ingest_pdf(pdf_path, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"총 {len(chunks)}개 청크 (chunk_size={cs}, overlap={ov})")
    index = build_index(chunks, client, pdf_path, chunk_size=cs, overlap=ov)
    print(f"인덱스 구축 완료: {index.cache_path}")

    # --- Stage 1: Feedback (reused) ---
    if args.no_feedback:
        combined_query = query
        feedback_questions, answers = [], []
    else:
        print("------------------------------------------1단계: 추가 질문 생성----------------------------------------------------")
        feedback_questions = generate_feedback(query, client, args.feedback_model, max_feedbacks=3)
        answers = []
        if feedback_questions:
            print("\n다음 질문에 답변해 주세요:")
            for idx, q in enumerate(feedback_questions, start=1):
                answers.append(input(f"질문 {idx}: {q}\n답변: "))
        else:
            print("추가 질문이 생성되지 않았습니다.")

        combined_query = f"초기 질문: {query}\n"
        for i in range(len(feedback_questions)):
            combined_query += f"\n{i+1}. 질문: {feedback_questions[i]}\n"
            combined_query += f"   답변: {answers[i]}\n"
        print("최종질문:\n")
        print(combined_query)

    # --- Research params ---
    try:
        breadth = int(input("연구 범위를 입력하세요 (예: 2): ") or "2")
    except ValueError:
        breadth = 2
    try:
        depth = int(input("연구 깊이를 입력하세요 (예: 2): ") or "2")
    except ValueError:
        depth = 2
    logger.info("Research params | breadth=%d | depth=%d", breadth, depth)

    # --- Stage 2: PDF Deep Research ---
    print("------------------------------------------2단계: PDF 딥리서치----------------------------------------------------")
    research_results = deep_pdf_research(
        query=combined_query,
        breadth=breadth,
        depth=depth,
        client=client,
        model=args.research_model,
        index=index,
    )

    print("\n연구 결과:")
    for learning in research_results["learnings"]:
        print(f" - {learning}")

    # --- Stage 3: Reporting (reused, source_pages → visited_urls passthrough) ---
    print("------------------------------------------3단계: 보고서 작성----------------------------------------------------")
    report = write_final_report(
        prompt=combined_query,
        learnings=research_results["learnings"],
        visited_urls=research_results["source_pages"],
        client=client,
        model=args.reporting_model,
    )

    os.makedirs("output", exist_ok=True)
    with open("output/output.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n최종 보고서:\n")
    print(report)
    print("\n보고서가 output/output.md 파일에 저장되었습니다.")
    logger.info("PDF Pipeline completed. Report saved to output/output.md")


if __name__ == "__main__":
    main()
