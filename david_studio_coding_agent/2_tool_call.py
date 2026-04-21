import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def add(a, b):
    return a + b

# 실제 사용할 도구 맵
TOOLS_MAP = {
    "add": add,
}

# 아주 심플한 프롬프트 템플릿
PROMPT = """
다음의 도구만 사용해서 문제를 해결하세요.

도구 목록:
- add: 두 수를 더합니다. (매개변수: a: number, b: number)

문제:
{question}

- 반드시 아래 JSON 형식으로만 답하세요. 자연어 설명 없이, 도구명과 파라미터만 출력하세요.

{{
  "tool_name": "도구이름",
  "tool_parameters": {{"a": (첫 번째 숫자), "b": (두 번째 숫자)}}
}}
"""

def llm_call(prompt: str, model: str = "gpt-5") -> str:
    messages = [{"role": "user", "content": prompt}]
    chat_completion = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return chat_completion.choices[0].message.content

if __name__ == "__main__":
    question = "1 더하기 3은 뭐야 (반드시 도구 사용해야 함)"

    prompt = PROMPT.format(question=question)
    llm_response = llm_call(prompt)
    print("LLM 응답:", llm_response)

    # LLM이 준 JSON 파싱
    result_json = json.loads(llm_response)
    tool_name = result_json["tool_name"]
    params = result_json["tool_parameters"]

    # 도구 직접 호출
    if tool_name in TOOLS_MAP:
        result = TOOLS_MAP[tool_name](**params)
        print(f"{tool_name}({params['a']}, {params['b']}) = {result}")
    else:
        print("알 수 없는 도구:", tool_name)
