import os
import json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()

def list_files(directory: str = ".") -> str:
    try:
        if not os.path.exists(directory):
            return f"존재하지 않는 경로입니다: {directory}"
        items = []
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                items.append(f"[폴더]  {item}/")
            else:
                items.append(f"[파일] {item}")
        if not items:
            return f"비어있는 폴더입니다: {directory}"
        return f"{directory}의 내용:\n" + "\n".join(items)
    except Exception as e:
        return f"폴더/파일 목록을 불러오는 중 오류 발생: {str(e)}"

## 2) 파일 내용 불러오기
def read_file(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""

def edit_file(file_path: str, old_text: str = "", new_text: str = "") -> str:
    try:
        # 파일이 존재하고 old_text가 주어졌을 때 교체
        if os.path.exists(file_path) and old_text:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_text not in content:
                return f"파일에서 텍스트를 찾을 수 없습니다: {old_text}"
            
            content = content.replace(old_text, new_text)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"파일이 성공적으로 수정되었습니다: {file_path}"
        
        # 파일이 없을 경우 새로 생성
        else:
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            return f"파일이 성공적으로 생성되었습니다: {file_path}"
    except Exception as e:
        return f"파일 수정 중 오류 발생: {str(e)}"
    
    

TOOLS_MAP = {
    "list_files": list_files,
    "read_file": read_file,
    "edit_file": edit_file,
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
아래 도구만 사용해서 문제를 단계별로 해결하세요.

- list_files: 지정한 폴더의 파일/폴더 이름 목록을 반환합니다. (directory)
- read_file: 파일 경로에 해당하는 텍스트 파일의 내용을 반환합니다. (file_path)
- edit_file: 파일에서 문자열을 교체할 수 있습니다. (file_path, old_text, new_text)

각 단계에서 반드시 아래 JSON 형식으로 하나의 도구만 호출하세요:

- 아직 최종 답이 아니면 아래와 같이 출력하세요:
  {{
    "final_answer": "no",
    "tool_name": "도구이름",
    "tool_parameters": {{ ...매개변수... }}
  }}

- 최종 답이면 아래와 같이 출력하세요:
  {{
    "final_answer": "yes",
    "final_response": "질문에 대한 최종 응답을 자연스러운 언어로 표현"
  }}

- 반드시 위의 JSON만 출력하세요. 자연어 설명이나 기타 텍스트는 쓰지 마세요.

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
        final_response = tool_call.get("final_response", "")
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

if __name__ == "__main__":

    # 예시 1: import 구문 교체 (a.py, b.py만 변경, c.py는 변경 없음)
    # 예상 도구 사용 흐름: 파일 목록 확인 → 각 파일 읽기 → 문자열 교체 (replace)
    # user_question = "test_files 폴더 안의 모든 .py 파일에서 'import math'를 'import math as m'으로 바꿔줘."

    # 예시 2: 여러 파일에서 함수 이름 교체
    # 예상 도구 사용 흐름: 파일 목록 확인 → 각 파일 읽기 → 문자열 교체 (replace)
    user_question = "test_files 폴더 내 모든 파일에서 'def foo'를 'def foo_renamed'로 바꿔줘"

    # 예시 3: 함수 위에 docstring(주석) 추가
    # 예상 도구 사용 흐름: 파일 목록 확인 → 각 파일 읽기 → 문자열 삽입 (insert)
    # user_question = "test_files 폴더의 모든 .py 파일에서 함수 정의 위에 주석을 한글로 추가해줘"
    
    
    run_agent(user_question)
