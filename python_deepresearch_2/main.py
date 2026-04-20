import os
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from step1_feedback.feedback import generate_feedback
from step2_research.research import deep_research
from step3_reporting.reporting import write_final_report
from dotenv import load_dotenv
from utils import setup_logging

load_dotenv()  # .env 파일에서 환경 변수를 불러옵니다.

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Pipeline started ===")

    # 사용자로부터 초기 연구 질문을 입력받음
    query = input("어떤 주제에 대해 리서치하시겠습니까?: ")
    logger.info("User query: %.200s", query)

    # gpt 4o-mini, gpt-4o,o3-mini 로 변경 가능 (structured output 지원되는 모델만 가능 → o1-mini는 불가)
    feedback_model = "gpt-4o-mini"
    research_model = "gpt-4o"

    # "o3-mini, gpt-4o, gpt-4o-mini"로 변경 가능
    reporting_model = "gpt-4o"

    logger.info("Models | feedback=%s | research=%s | reporting=%s",
                feedback_model, research_model, reporting_model)

    # 임베딩 모델 초기화 (필요 시 사용)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # 추가적인 질문을 생성하여 연구 방향을 구체화
    print(f"------------------------------------------1단계: 추가 질문 생성----------------------------------------------------")
    feedback_questions = generate_feedback(query, feedback_model, max_feedbacks=3)
    answers = []
    if feedback_questions:
        print("\n다음 질문에 답변해 주세요:")
        for idx, question in enumerate(feedback_questions, start=1):
            answer = input(f"질문 {idx}: {question}\n답변: ")
            answers.append(answer)
    else:
        print("추가 질문이 생성되지 않았습니다.")

    # 초기 질문과 후속 질문 및 답변을 결합
    combined_query = f"초기 질문: {query}\n"
    for i in range(len(feedback_questions)):
        combined_query += f"\n{i+1}. 질문: {feedback_questions[i]}\n"
        combined_query += f"   답변: {answers[i]}\n"

    print("최종질문 : \n")
    print(combined_query)

    # 연구 범위 및 깊이를 사용자로부터 입력받음
    try:
        breadth = int(input("연구 범위를 입력하세요 (예: 2): ") or "2")
    except ValueError:
        breadth = 2
    try:
        depth = int(input("연구 깊이를 입력하세요 (예: 2): ") or "2")
    except ValueError:
        depth = 2

    logger.info("Research params | breadth=%d | depth=%d", breadth, depth)

    # 심층 연구 수행 (동기적으로 실행)
    print(f"------------------------------------------2단계: 딥리서치----------------------------------------------------")
    research_results = deep_research(
        query=combined_query,
        breadth=breadth,
        depth=depth,
        model=research_model
    )

    # 연구 결과 출력
    print("\n연구 결과:")
    for learning in research_results["learnings"]:
        print(f" - {learning}")

    # 최종 보고서 생성
    print(f"------------------------------------------3단계: 보고서 작성----------------------------------------------------")

    report = write_final_report(
        prompt=combined_query,
        learnings=research_results["learnings"],
        visited_urls=research_results["visited_urls"],
        model=reporting_model
    )

    # 최종 보고서 출력 및 파일 저장
    print("\n최종 보고서:\n")
    print(report)
    with open("output/output.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n보고서가 output/output.md 파일에 저장되었습니다.")
    logger.info("Pipeline completed. Report saved to output/output.md")

if __name__ == "__main__":
    main()
