import json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()

# ===========================================
# 실제 도구 함수 구현
# ===========================================
def add(a, b): 
    return a + b
def multiply(a, b): 
    return a * b
def subtract(a, b): 
    return a - b

TOOLS_MAP = {
    "add": add,
    "multiply": multiply,
    "subtract": subtract,
}

# ===========================================
# LLM 호출 함수
# ===========================================
def llm_call(prompt: str, model: str = "gpt-4.1") -> str:
    messages = [{"role": "user", "content": prompt}]
    chat_completion = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return chat_completion.choices[0].message.content


PROMPT = """
아래의 도구들만 사용하여 문제를 단계별로 해결하세요.

도구 목록:
- add: 두 수를 더합니다. (매개변수: a: number, b: number)
- multiply: 두 수를 곱합니다. (매개변수: a: number, b: number)
- subtract: 첫 번째 숫자에서 두 번째 숫자를 뺍니다. (매개변수: a: number, b: number)

각 단계에서 반드시 아래 JSON 형식으로 하나의 도구만 호출하세요:

- 아직 최종 답이 아니면 아래와 같이 출력하세요:
  {{
    "final_answer": "no",
    "tool_name": "도구이름",
    "tool_parameters": {{ ...매개변수... (항상 숫자형!) }}
  }}

- 최종 답이면 아래와 같이 출력하세요:
  {{
    "final_answer": "yes",
    "final_response": "질문에 대한 최종 응답을 자연스러운 언어로 표현"
  }}

- 반드시 모든 tool_parameters 값은 숫자여야 합니다. (예: "a": 3, "b": 4.5)
- 반드시 위의 JSON만 출력하세요. 자연어 설명은 쓰지 마세요.

이전 도구 호출 및 결과 이력:
{history}

문제 또는 목표:
{question}
"""


def run_agent(user_question, max_iterations=10):
    history = ""
    last_prompt = None
    for iteration in range(max_iterations):
        prompt = PROMPT.format(
            history=history or "(없음)",
            question=user_question
        )
        last_prompt = prompt  

        llm_response = llm_call(prompt)
        print(f"\n[LLM 응답]\n{llm_response}")
        tool_call = json.loads(llm_response)

        final_answer = tool_call.get("final_answer")
        tool_name = tool_call.get("tool_name")
        tool_parameters = tool_call.get("tool_parameters", {})
        final_response   = tool_call.get("final_response", "")
        if final_answer == "yes":
            print("\n[마지막 프롬프트]\n", last_prompt)
            print(f"\n최종 답: {final_response}")
            return final_response

        # === 여기부터는 final_answer가 "no"인 경우만 ===

        if tool_name in TOOLS_MAP:
            result = TOOLS_MAP[tool_name](**tool_parameters)
            history += f"[{tool_name}] {tool_parameters} -> result={result} (final_answer=no)\n"
        else:
            print(f"알 수 없는 도구 호출: {tool_name}. 루프를 중단합니다.")
            break

# ===========================================
# __main__ SIMPLIFIED
# ===========================================
if __name__ == "__main__":
    user_question = "다음 식을 계산해 주세요: (1 + 1) * 2 - 1. 반드시 각 연산마다 도구만 사용하세요."
    run_agent(user_question)

