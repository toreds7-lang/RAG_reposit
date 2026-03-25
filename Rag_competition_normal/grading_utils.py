from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


def grade_predictions(questions, predicted_answers, answers, model_name="gpt-4o-mini"):
    """
    questions        : 질문 리스트
    predicted_answers: 모델 예측 답변 리스트
    answers          : 정답 리스트 (qa_dataset.json에서 로드)
    """
    grading_prompt = ChatPromptTemplate.from_template("""
너는 자동 채점 시스템이야. 아래는 사용자의 질문, 모델이 예측한 답변, 그리고 정답이야.

각 항목마다 다음 기준으로 점수를 매겨줘:
- 정확히 일치하면 1점
- 수치가 아닐 경우 부분적으로 맞지만 누락, 오탈자 등이 있으면 0.5점
- 수치가 조금이라도 틀리거나 전혀 다르면 0점

항목별 점수와 간단한 설명만 출력해줘. 총점은 계산하지 마.
출력 형식은 다음과 같아야 해:
1번: 1점 (설명)
2번: 0점 (설명)
...

질문-답변 리스트:
{qa_pairs}
""")

    llm = ChatOpenAI(model=model_name, temperature=0)
    parser = StrOutputParser()

    qa_string = "\n".join(
        [f"{i+1}. 질문: {questions[i]}\n예측: {predicted_answers[i]}\n정답: {answers[i]}"
         for i in range(len(questions))]
    )

    grading_chain = grading_prompt | llm | parser
    return grading_chain.invoke({"qa_pairs": qa_string})
