---
marp: true
theme: default
paginate: true
---

# LLM 에이전트 만들기
## vllm 버전 — 로우레벨 OpenAI SDK

내부 LLM 서버(vllm)로 AI 에이전트를 단계적으로 구현한다

---

## 5단계 학습 로드맵

| 단계 | 파일 | 핵심 개념 |
|------|------|----------|
| 1 | `1_llm_call.py` | LLM 기본 호출 |
| 2 | `2_tool_call.py` | JSON 도구 호출 |
| 3 | `3_calculator_agent.py` | 에이전트 루프 |
| 4 | `4_coding_tools.py` | 파일 시스템 도구 |
| 5 | `5_coding_agent.py` | 자율 코딩 에이전트 |

---

## 환경 설정

```
# .env
OPENAI_API_KEY=sk-...        # 검증용 OpenAI 키
VLLM_BASE_URL=http://...     # 내부 vllm 서버 주소
```

```python
USE_OPENAI_FOR_VALIDATION = False  # True → OpenAI, False → vllm
```

> **핵심:** base_url만 바꾸면 vllm 서버를 그대로 사용

---

## Stage 1: LLM 기본 호출

**개념:** OpenAI SDK는 vllm과 완전히 호환된다

```python
client = OpenAI(
    base_url=VLLM_BASE_URL,   # vllm 서버 주소
    api_key="token"            # vllm은 아무 값이나 가능
)

def llm_call(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

---

## Stage 2: Tool Call — JSON 프로토콜

**개념:** LLM에게 JSON 형식으로 도구 호출을 지시한다

```
프롬프트에 규칙 명시
    ↓
LLM → JSON 응답 생성
    ↓
Python → JSON 파싱 → 함수 실행
    ↓
결과를 다시 LLM에 전달
```

---

## Stage 2: 도구 정의 패턴

```python
def add(a: int, b: int) -> int:
    return a + b

TOOLS_MAP = {"add": add}
```

```python
# LLM 응답 파싱 및 실행
response_json = json.loads(llm_response)
tool_name = response_json["tool"]
tool_args = response_json["args"]
result = TOOLS_MAP[tool_name](**tool_args)
```

---

## Stage 3: 에이전트 루프 개념

**핵심:** 히스토리를 누적하며 `final_answer`가 나올 때까지 반복

```
[history] 초기화
    ↓
LLM 호출 (history 전달)
    ↓
final_answer? → 종료
    ↓ 아니면
도구 실행 → 결과를 history에 추가
    ↓ 반복 (최대 10회)
```

---

## Stage 3: 에이전트 루프 코드

```python
def run_calculator_agent(question: str):
    history = ""
    for _ in range(10):
        prompt = AGENT_PROMPT.format(
            history=history, question=question
        )
        response = llm_call(prompt)
        parsed = json.loads(response)

        if parsed.get("final_answer"):
            return parsed["final_answer"]

        # 도구 실행 후 history 누적
        result = TOOLS_MAP[parsed["tool"]](**parsed["args"])
        history += f"tool: {parsed['tool']}, result: {result}\n"
```

---

## Stage 4: 파일 시스템 도구

| 도구 | 역할 |
|------|------|
| `list_files()` | 프로젝트 파일 목록 조회 |
| `read_file(path)` | 파일 내용 읽기 |
| `edit_file(path, old, new)` | 텍스트 교체로 파일 수정 |

> 이 3가지 도구만으로 에이전트가 코드를 자율적으로 수정할 수 있다

---

## Stage 5: 자율 코딩 에이전트

**개념:** 에이전트 루프 + 파일 도구 = 자율 코드 수정

```python
CODING_TOOLS_MAP = {
    "list_files": list_files,
    "read_file": read_file,
    "edit_file": edit_file,
}
```

- 에이전트가 스스로 파일을 탐색하고
- 필요한 부분을 읽고
- 코드를 직접 수정한다

---

## 핵심 정리

**vllm의 가치**
- OpenAI SDK → base_url만 교체 → 내부 LLM 서버 사용
- 외부 API 의존 없이 사내 모델 운용 가능

**에이전트의 본질**
- LLM + 도구 + 루프 = 에이전트
- 복잡한 문제도 단계적 도구 호출로 해결
