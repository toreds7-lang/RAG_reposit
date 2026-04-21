---
marp: true
theme: default
paginate: true
---

# LLM 에이전트 만들기
## LangChain 버전 — 추상화로 더 간결하게

LangChain 프레임워크로 AI 에이전트를 단계적으로 구현한다

---

## 5단계 학습 로드맵

| 단계 | 핵심 개념 | LangChain 핵심 API |
|------|----------|-------------------|
| 1 | LLM 호출 | `init_chat_model` |
| 2 | 도구 호출 | `@tool`, `bind_tools` |
| 3 | 에이전트 루프 | 메시지 히스토리 |
| 4 | 파일 도구 | `@tool` 데코레이터 |
| 5 | 코딩 에이전트 | 루프 재사용 |

---

## LangChain이란?

**한 줄로 모델을 교체할 수 있는 프레임워크**

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-4o", model_provider="openai")
model = init_chat_model("claude-3-5-sonnet", model_provider="anthropic")
model = init_chat_model("gemini-2.0-flash", model_provider="google_vertexai")
```

> 코드 변경 없이 OpenAI, Anthropic, Google 등 교체 가능

---

## Stage 1: LLM 기본 호출

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

model = init_chat_model("gpt-4o-mini", model_provider="openai")

def llm_call(prompt: str) -> str:
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content
```

vllm 버전과 동일한 결과, 더 간결한 코드

---

## Stage 2: Tool Call — @tool 데코레이터

**개념:** 함수에 `@tool`을 붙이면 LangChain이 스키마를 자동 생성

```python
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """두 숫자를 더한다"""
    return a + b

# 모델에 도구 바인딩
model_with_tools = model.bind_tools([add])
```

> JSON 스키마를 수동으로 작성할 필요 없음

---

## Stage 2: 도구 호출 자동 파싱

**vllm 버전:** JSON 문자열 수동 파싱 필요
**LangChain 버전:** `response.tool_calls`로 자동 파싱

```python
response = model_with_tools.invoke([HumanMessage(content=question)])

for tool_call in response.tool_calls:
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    result = TOOLS_MAP[tool_name].invoke(tool_args)
```

---

## Stage 3: 에이전트 루프 — 메시지 패턴

**핵심:** 메시지 객체로 대화 히스토리를 관리

```
HumanMessage(질문)
    ↓
AIMessage(tool_calls=[...])    ← LLM 응답
    ↓
ToolMessage(result, tool_call_id)  ← 도구 실행 결과
    ↓
AIMessage(final_answer)        ← 최종 답변
```

---

## Stage 3: 에이전트 루프 코드

```python
def run_calculator_agent(question: str):
    messages = [HumanMessage(content=question)]

    for _ in range(10):
        response = model_with_tools.invoke(messages)
        messages.append(response)  # AIMessage 추가

        if not response.tool_calls:
            return response.content  # 도구 없으면 최종 답변

        for tc in response.tool_calls:
            result = TOOLS_MAP[tc["name"]].invoke(tc["args"])
            messages.append(ToolMessage(
                content=str(result), tool_call_id=tc["id"]
            ))
```

---

## Stage 4: 파일 도구 — @tool 버전

```python
@tool
def list_files() -> list:
    """프로젝트의 파일 목록을 반환한다"""
    ...

@tool
def read_file(path: str) -> str:
    """파일 내용을 읽어 반환한다"""
    ...

@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """파일의 특정 텍스트를 교체한다"""
    ...
```

---

## Stage 5: 코딩 에이전트

**핵심:** 계산기 에이전트와 동일한 루프 구조 재사용

```python
CODING_TOOLS_MAP = {
    "list_files": list_files,
    "read_file": read_file,
    "edit_file": edit_file,
}
model_with_tools = model.bind_tools(list(CODING_TOOLS_MAP.values()))

# run_calculator_agent()와 동일한 루프 → run_coding_agent()
```

> 루프 구조는 고정, 도구만 교체하면 다른 에이전트가 된다

---

## vllm vs LangChain 비교

| 항목 | vllm (로우레벨) | LangChain |
|------|----------------|-----------|
| 도구 정의 | JSON 스키마 수동 작성 | `@tool` 자동 생성 |
| 도구 파싱 | `json.loads()` 수동 | `response.tool_calls` 자동 |
| 히스토리 | 문자열 연결 | 메시지 객체 리스트 |
| 모델 교체 | base_url 변경 | `init_chat_model` 한 줄 |

---

## 핵심 정리 & 다음 단계

**오늘 배운 것**
- `@tool` + `bind_tools` → 도구 정의가 간결해진다
- 메시지 히스토리 패턴 → 에이전트 루프의 표준 구조

**다음 단계**
- **LangGraph** — 복잡한 에이전트 워크플로우 그래프화
- **메모리** — 대화 간 장기 기억 유지
- **RAG** — 외부 문서 검색 + LLM 결합
