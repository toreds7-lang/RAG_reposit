# Adding Memory

**Summary**: Learning material extracted from 01-LangGraph-Add-Memory.ipynb.

**Sources**: 01-LangGraph-Add-Memory.ipynb

**Last updated**: 2026-04-17

---

LangGraph에서 `메모리(Memory)`는 에이전트가 이전 대화 내용을 기억하고 맥락에 맞는 응답을 생성할 수 있게 해주는 핵심 기능입니다. 메모리가 없으면 에이전트는 매번 새로운 대화를 시작하는 것처럼 동작하여 일관된 다중 턴(multi-turn) 대화가 불가능합니다.

LangGraph는 **Checkpointer**를 통해 이 문제를 해결합니다. 그래프를 컴파일할 때 checkpointer를 제공하고, 그래프를 호출할 때 `thread_id`를 전달하면 각 실행 단계 후 상태가 자동으로 저장됩니다. 동일한 `thread_id`로 다시 호출하면 저장된 상태를 불러와 이전 대화를 이어서 진행할 수 있습니다.

또한 대화가 길어지면 LLM의 컨텍스트 윈도우 제한에 도달하거나 토큰 비용이 증가하는 문제가 발생합니다. 이를 해결하기 위해 메시지 트리밍(trimming), 삭제(deletion), 요약(summarization) 등의 단기 메모리 관리 전략을 사용합니다.

> 참고 문서: [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)

## 학습 목표

이 튜토리얼에서는 다음 내용을 학습합니다:

- MemorySaver 체크포인터를 사용한 상태 저장
- thread_id를 통한 대화 세션 관리
- 저장된 상태(스냅샷) 조회
- 도구와 메모리 결합
- 메시지 트리밍(trim_messages)을 통한 컨텍스트 관리
- RemoveMessage를 사용한 메시지 삭제
- 그래프 내에서 동적으로 메시지 관리하기
- 대화 요약을 통한 컨텍스트 압축
- 프로덕션 환경에서의 체크포인터 선택

## 환경 설정

LangGraph 튜토리얼을 시작하기 전에 필요한 환경을 설정합니다. `dotenv`를 사용하여 API 키를 로드하고, `langchain_teddynote`의 로깅 기능을 활성화하여 LangSmith에서 실행 추적을 확인할 수 있도록 합니다.

아래 코드는 환경 변수를 로드하고 LangSmith 프로젝트를 설정합니다.

```python
# API 키를 환경변수로 관리하기 위한 설정 파일
from dotenv import load_dotenv

# API 키 정보 로드
load_dotenv(override=True)
```

```python
# LangSmith 추적을 설정합니다. https://smith.langchain.com
from langchain_teddynote import logging

# 프로젝트 이름을 입력합니다.
logging.langsmith("LangGraph-V1-Tutorial")
```

---

## MemorySaver 체크포인터

체크포인터(Checkpointer)는 그래프의 각 단계에서 상태를 저장하여, 이후 동일한 대화를 이어서 진행할 수 있게 하는 컴포넌트입니다. `MemorySaver`는 인메모리 체크포인터로, 메모리에 상태를 저장하므로 개발 및 테스트 환경에서 사용하기 적합합니다.

프로덕션 환경에서는 서버 재시작 시에도 상태가 유지되어야 하므로 `PostgresSaver`나 `SqliteSaver` 같은 영구 저장소 기반 체크포인터를 사용하는 것이 좋습니다.

아래 코드에서는 `MemorySaver` 체크포인터를 생성합니다.

```python
from langgraph.checkpoint.memory import MemorySaver

# 메모리 저장소 생성
memory = MemorySaver()
```

---

## 메모리가 있는 챗봇 구축

이제 체크포인터를 사용하여 대화 기록을 저장하는 간단한 챗봇을 구축합니다. 챗봇은 사용자의 메시지를 받아 LLM에 전달하고, 응답을 상태에 추가합니다. 체크포인터가 각 단계의 상태를 저장하므로 동일한 `thread_id`로 호출하면 이전 대화 내용이 유지됩니다.

### State 정의

State는 그래프 전체에서 공유되는 데이터 구조를 정의합니다. `messages` 필드에 `add_messages` 리듀서를 적용하면, 새 메시지가 기존 리스트를 덮어쓰지 않고 추가됩니다. 이는 대화 이력을 유지하는 데 필수적입니다.

아래 코드에서는 State를 정의하고, 챗봇 노드 함수와 그래프를 구성합니다.

```python
from typing import Annotated
from typing_extensions import TypedDict
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


# State 정의: 메시지 리스트를 관리
class State(TypedDict):
    """챗봇의 상태를 정의하는 타입

    messages: 대화 메시지 리스트
    - add_messages 리듀서를 통해 새 메시지가 추가됩니다
    """

    messages: Annotated[list, add_messages]


# LLM 초기화
llm = init_chat_model("claude-sonnet-4-5", temperature=0)

# 챗봇 노드 함수 정의
def chatbot(state: State):
    """챗봇 노드 함수

    현재 상태의 메시지를 받아 LLM에 전달하고,
    응답을 새 메시지로 추가하여 반환합니다.
    """
    # LLM 호출 및 응답 반환
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# StateGraph 생성
graph_builder = StateGraph(State)

# 노드 추가
graph_builder.add_node("chatbot", chatbot)

# 엣지 추가
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

# 체크포인터와 함께 컴파일
graph = graph_builder.compile(checkpointer=memory)

print("메모리가 활성화된 그래프 생성 완료!")
```

---

## 멀티턴 대화 테스트

이제 같은 `thread_id`로 여러 번 대화를 나누며 챗봇이 이전 대화를 기억하는지 확인해봅시다. `RunnableConfig`를 사용하여 `thread_id`를 설정하면, 해당 스레드의 대화 기록이 체크포인터에 저장되고 불러와집니다.

아래 코드에서는 첫 번째 대화에서 이름을 알려주고, 두 번째 대화에서 이름을 물어봅니다.

!['chatbot'](./assets/01-chatbot-graph.png)

```python
from langchain_core.runnables import RunnableConfig

# Config 설정: thread_id로 대화 세션을 구분
config = RunnableConfig(
    recursion_limit=10,  # 최대 방문 노드 수
    configurable={"thread_id": "conversation_1"},  # 대화 세션 ID
)
```

```python
# 첫 번째 메시지: 자기소개
print("User: 안녕하세요! 저는 철수입니다.")

result = graph.invoke(
    {"messages": [{"role": "user", "content": "안녕하세요! 저는 철수입니다."}]},
    config,
)

print(f"Bot: {result['messages'][-1].content}")
```

```python
# 두 번째 메시지: 이름 확인 (이전 대화 기억 확인)
print("User: 제 이름이 뭐라고 했죠?")

result = graph.invoke(
    {"messages": [{"role": "user", "content": "제 이름이 뭐라고 했죠?"}]},
    config,  # 같은 thread_id 사용
)

print(f"Bot: {result['messages'][-1].content}")
```

### 다른 thread_id로 테스트

`thread_id`가 다르면 별도의 대화 세션으로 취급되므로, 이전 대화 내용을 기억하지 못합니다. 이를 통해 여러 사용자 또는 여러 대화 세션을 독립적으로 관리할 수 있습니다.

아래 코드에서는 다른 `thread_id`로 같은 질문을 해봅니다.

```python
# 다른 thread_id로 Config 설정
config_2 = RunnableConfig(
    recursion_limit=10,
    configurable={"thread_id": "conversation_2"},  # 다른 세션
)

print("--- 새로운 대화 세션 (thread_id: conversation_2) ---")
print("User: 제 이름이 뭐예요?")

result = graph.invoke(
    {"messages": [{"role": "user", "content": "제 이름이 뭐예요?"}]},
    config_2,
)

print(f"Bot: {result['messages'][-1].content}")
print("\n다른 thread에서는 이전 대화를 기억하지 못합니다.")
```

---

## 저장된 상태(스냅샷) 확인

체크포인터는 그래프 실행의 각 단계에서 상태를 저장합니다. `get_state()` 메서드를 사용하면 특정 `thread_id`의 현재 상태를 조회할 수 있습니다. 스냅샷에는 현재 상태 값(values), 설정 정보(config), 다음 노드(next) 등이 포함됩니다.

아래 코드에서는 저장된 상태를 조회하고 각 속성을 확인합니다.

```python
# 첫 번째 thread의 상태 조회
snapshot = graph.get_state(config)

# 저장된 메시지 확인
print("저장된 메시지:")
for msg in snapshot.values["messages"]:
    msg.pretty_print()
```

```python
# 설정 정보 확인
print("Config 정보:")
print(snapshot.config)
```

```python
# 다음 노드 확인 (실행 완료 시 빈 값)
print("다음 노드:", snapshot.next)
```

### 메타데이터 시각화

스냅샷의 메타데이터는 중첩된 구조로 되어 있어 직접 확인하기 어려울 수 있습니다. `langchain_teddynote.messages` 모듈의 `display_message_tree()` 함수를 사용하면 트리 형태로 보기 쉽게 출력할 수 있습니다.

아래 코드에서는 스냅샷의 메타데이터를 트리 형태로 시각화합니다.

```python
from langchain_teddynote.messages import display_message_tree

# 메타데이터를 트리 형태로 출력
display_message_tree(snapshot.metadata)
```

---

## 상태 이력 조회

체크포인터는 모든 상태 변경을 기록하므로, `get_state_history()` 메서드를 사용하여 과거 상태들을 시간 역순으로 조회할 수 있습니다. 이를 통해 특정 시점의 상태로 롤백하거나 디버깅에 활용할 수 있습니다.

> 참고 문서: [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)

아래 코드에서는 상태 이력을 조회하여 각 체크포인트를 확인합니다.

```python
# 상태 이력 조회
print("상태 이력:")
for i, state in enumerate(graph.get_state_history(config)):
    checkpoint_id = state.config["configurable"].get("checkpoint_id", "N/A")
    msg_count = len(state.values.get("messages", []))
    print(f"  [{i}] checkpoint_id: {checkpoint_id[:20]}... | 메시지 수: {msg_count}")
```

---

## 도구와 메모리 결합

실제 에이전트는 도구를 사용하여 외부 정보를 검색하거나 작업을 수행합니다. 도구를 사용하는 에이전트에도 체크포인터를 적용하면 도구 호출 결과까지 포함한 전체 대화 기록이 저장됩니다.

아래 코드에서는 검색 도구를 사용하는 에이전트에 메모리를 추가합니다.

```python
from langchain_teddynote.tools.tavily import TavilySearch
from langgraph.prebuilt import ToolNode, tools_condition

# 새로운 체크포인터 생성
agent_memory = MemorySaver()

# 검색 도구 설정
search_tool = TavilySearch(max_results=2)
tools = [search_tool]

# LLM에 도구 바인딩
llm_with_tools = init_chat_model("claude-sonnet-4-5").bind_tools(tools)

# 에이전트 노드 함수
def agent(state: State):
    """에이전트 노드 함수

    도구가 바인딩된 LLM을 호출하여 응답을 생성합니다.
    """
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# 그래프 구성
agent_builder = StateGraph(State)

# 노드 추가
agent_builder.add_node("agent", agent)
agent_builder.add_node("tools", ToolNode(tools=tools))

# 엣지 추가
agent_builder.add_edge(START, "agent")
agent_builder.add_conditional_edges("agent", tools_condition)
agent_builder.add_edge("tools", "agent")

# 체크포인터와 함께 컴파일
agent_graph = agent_builder.compile(checkpointer=agent_memory)

print("도구와 메모리가 통합된 에이전트 생성 완료!")
```

![graph](./assets/01-agent-graph.png)

```python
from langchain_teddynote.messages import stream_graph

# 에이전트 config 설정
agent_config = RunnableConfig(
    recursion_limit=20,
    configurable={"thread_id": "agent_session_1"},
)

# 검색 요청
inputs = {"messages": [{"role": "user", "content": "LangGraph의 최신 버전에 대해 알려주세요."}]}

# 스트리밍 실행
stream_graph(agent_graph, inputs=inputs, config=agent_config)
```

```python
# 후속 질문 (이전 검색 결과 기반)
inputs = {"messages": [{"role": "user", "content": "방금 알려준 내용을 한 문장으로 요약해주세요."}]}

stream_graph(agent_graph, inputs=inputs, config=agent_config)
```

---

## 단기 메모리 관리

지금까지 체크포인터를 사용하여 대화 기록을 저장하고 불러오는 방법을 학습했습니다. 그러나 대화가 길어지면 LLM의 컨텍스트 윈도우 제한에 도달하거나 토큰 비용이 증가하는 문제가 발생합니다.

이를 해결하기 위해 다음과 같은 단기 메모리 관리 전략을 사용합니다:

- **트리밍(Trimming)**: 오래된 메시지를 잘라내어 최근 메시지만 유지
- **삭제(Deletion)**: 특정 메시지를 상태에서 영구 제거
- **요약(Summarization)**: 오래된 메시지를 요약하여 컨텍스트 압축

---

## 기본 에이전트 구축

먼저 메시지 관리 기법을 테스트할 기본 에이전트를 구축합니다. 이 에이전트는 검색 도구를 사용하며, `MemorySaver` 체크포인터를 통해 대화 기록을 저장합니다. 메시지가 누적되면서 다양한 관리 기법을 적용해볼 수 있습니다.

아래 코드에서는 검색 도구, LLM 모델, 그리고 StateGraph를 정의합니다.

```python
from typing import Literal

from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# 체크포인트 저장을 위한 메모리 객체 초기화
memory = MemorySaver()


# 웹 검색 기능을 모방하는 도구 함수 정의
@tool
def search(query: str):
    """웹 검색을 수행합니다."""
    return f"검색 결과: '{query}'에 대한 정보를 찾았습니다. LangGraph는 상태 기반 워크플로우를 구축하는 프레임워크입니다."


# 도구 목록 생성 및 도구 노드 초기화
tools = [search]
tool_node = ToolNode(tools)

# 모델 초기화 및 도구 바인딩
model = init_chat_model("claude-sonnet-4-5")
model_with_tools = model.bind_tools(tools)


# Bedrock CountTokens API 호환성을 위한 토큰 카운터 래퍼 함수
def token_counter(messages):
    """Bedrock 호환 토큰 카운터

    Bedrock CountTokens API는 빈 메시지 리스트나 시스템 메시지만 포함된
    리스트를 허용하지 않으므로, 오류 발생 시 문자 기반으로 토큰 수를 추정합니다.
    """
    if not messages:
        return 0
    try:
        return model.get_num_tokens_from_messages(messages)
    except Exception:
        # Bedrock API 호환성 문제 시 문자 기반으로 추정 (~4자 = 1토큰)
        total = 0
        for m in messages:
            if hasattr(m, "content") and isinstance(m.content, str):
                total += len(m.content) // 4
            total += 4  # 메시지 오버헤드
        return total


# LLM 모델 호출 및 응답 처리 함수
def call_model(state: MessagesState):
    """에이전트 노드 함수

    현재 메시지를 LLM에 전달하고 응답을 반환합니다.
    """
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# 상태 기반 워크플로우 그래프 초기화
workflow = StateGraph(MessagesState)

# 에이전트와 도구 노드 추가
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# 시작점을 에이전트 노드로 설정
workflow.add_edge(START, "agent")

# 조건부 엣지 설정: 도구 호출 여부에 따라 분기
workflow.add_conditional_edges("agent", tools_condition)

# 도구 실행 후 에이전트로 돌아가는 엣지 추가
workflow.add_edge("tools", "agent")

# 체크포인터가 포함된 최종 워크플로우 컴파일
app = workflow.compile(checkpointer=memory)

print("기본 에이전트 생성 완료!")
```

### 그래프 시각화

컴파일된 그래프의 구조를 시각화합니다. `agent` 노드에서 도구 호출 여부에 따라 `tools` 노드로 분기하거나 종료되는 흐름을 확인할 수 있습니다.

아래 코드는 그래프를 시각화합니다.

```python
from IPython.display import Image

# 그래프 시각화
Image("./assets/03-basic-agent-graph.png")
```

### 에이전트 테스트

기본 에이전트가 대화를 기억하는지 테스트합니다. 첫 번째 메시지에서 이름을 알려주고, 두 번째 메시지에서 이름을 물어보면 체크포인터에 저장된 대화 기록을 바탕으로 답변합니다.

아래 코드에서는 연속으로 두 번 대화를 수행합니다.

```python
from langchain_core.messages import HumanMessage

# 스레드 ID가 1인 설정 객체 초기화
config = {"configurable": {"thread_id": "1"}}

# 첫 번째 질문
input_message = HumanMessage(content="안녕하세요! 제 이름은 Teddy입니다.")

# 스트림 모드로 메시지 처리 및 응답 출력
for event in app.stream({"messages": [input_message]}, config, stream_mode="values"):
    event["messages"][-1].pretty_print()
```

```python
# 후속 질문: 이름 기억 확인
input_message = HumanMessage(content="제 이름이 뭐라고 했죠?")

for event in app.stream({"messages": [input_message]}, config, stream_mode="values"):
    event["messages"][-1].pretty_print()
```

```python
# 현재 저장된 메시지 확인
messages = app.get_state(config).values["messages"]
print(f"현재 저장된 메시지 수: {len(messages)}개\n")

for message in messages:
    message.pretty_print()
```

---

## 메시지 트리밍(Trimming)

대부분의 LLM에는 최대 지원 컨텍스트 윈도우(토큰 단위)가 있습니다. 대화가 길어지면 이 한계에 도달하여 오류가 발생하거나 컨텍스트가 손실될 수 있습니다. `trim_messages` 함수를 사용하면 메시지 기록의 토큰 수를 계산하고, 한계에 도달했을 때 오래된 메시지를 트리밍할 수 있습니다.

### trim_messages 함수

`langchain_core.messages`의 `trim_messages` 함수는 다음과 같은 옵션을 제공합니다:

- `strategy`: "last"(최근 메시지 유지) 또는 "first"(첫 메시지 유지)
- `max_tokens`: 유지할 최대 토큰 수
- `token_counter`: 토큰 수를 계산하는 함수 또는 LLM 모델
- `start_on`: 시작할 메시지 타입 ("human", "ai" 등)
- `include_system`: 시스템 메시지 포함 여부 (strategy가 "last"일 경우에만 사용)

### token_counter 주의사항

`token_counter` 파라미터에는 **LLM 모델 객체**를 전달하는 것이 권장됩니다. `token_counter=len`처럼 `len` 함수를 전달하면 메시지 **개수**를 토큰 수로 잘못 계산하여 트리밍이 제대로 작동하지 않습니다.

```python
# 잘못된 사용 (메시지 개수를 토큰으로 계산)
trim_messages(messages, max_tokens=100, token_counter=len)

# 올바른 사용 (LLM 모델로 정확한 토큰 계산)
trim_messages(messages, max_tokens=100, token_counter=model)
```

아래 코드에서는 LLM 모델을 token_counter로 사용하여 트리밍 전략을 테스트합니다.

```python
from langchain_core.messages import trim_messages, HumanMessage, AIMessage, SystemMessage

# 긴 대화 히스토리 시뮬레이션
sample_messages = [
    SystemMessage(content="당신은 친절한 어시스턴트입니다."),
    HumanMessage(content="안녕하세요"),
    AIMessage(content="안녕하세요! 무엇을 도와드릴까요?"),
    HumanMessage(content="날씨가 어때요?"),
    AIMessage(content="오늘은 맑은 날씨입니다."),
    HumanMessage(content="추천 음식이 있나요?"),
    AIMessage(content="파스타를 추천합니다."),
    HumanMessage(content="레시피를 알려주세요"),
    AIMessage(content="토마토 파스타 레시피입니다. 먼저 토마토를 준비하고..."),
    HumanMessage(content="감사합니다"),
    AIMessage(content="천만에요! 다른 질문이 있으시면 말씀해주세요."),
]

print(f"원본 메시지 수: {len(sample_messages)}개")
```

```python
# 전략 1: 최근 메시지만 유지 (strategy="last")
# token_counter 함수를 전달하면 정확한 토큰 수를 계산합니다.
trimmed_last = trim_messages(
    sample_messages,
    strategy="last",
    max_tokens=100,  # 최대 100 토큰만 유지
    token_counter=token_counter,  # 토큰 카운터 함수 전달
    start_on="human",  # 사람 메시지로 시작
    include_system=True,  # 시스템 메시지 포함
)

print("전략 1 - 최근 메시지 유지 (strategy='last'):")
print(f"트리밍 후 메시지 수: {len(trimmed_last)}개\n")
for msg in trimmed_last:
    print(f"  [{msg.type}] {msg.content[:50]}..." if len(msg.content) > 50 else f"  [{msg.type}] {msg.content}")
```

```python
# 전략 2: 첫 메시지 유지 (strategy="first")
trimmed_first = trim_messages(
    sample_messages,
    strategy="first",
    max_tokens=100,
    token_counter=token_counter,  # 토큰 카운터 함수 전달
)

print("전략 2 - 첫 메시지 유지 (strategy='first'):")
print(f"트리밍 후 메시지 수: {len(trimmed_first)}개\n")
for msg in trimmed_first:
    print(f"  [{msg.type}] {msg.content[:50]}..." if len(msg.content) > 50 else f"  [{msg.type}] {msg.content}")
```

### 그래프에서 트리밍 적용

LLM을 호출하기 전에 메시지를 트리밍하여 컨텍스트 윈도우 제한을 관리할 수 있습니다. 아래 예제에서는 에이전트 노드에서 LLM을 호출하기 전에 자동으로 메시지를 트리밍합니다.

아래 코드에서는 트리밍이 적용된 에이전트를 구축합니다.

```python
# 새로운 체크포인터 생성
memory_trimmed = MemorySaver()


def call_model_with_trimming(state: MessagesState):
    """트리밍이 적용된 에이전트 노드
    
    LLM 호출 전에 메시지를 트리밍하여 컨텍스트 관리를 수행합니다.
    """
    # 메시지 트리밍 - 최대 500 토큰만 유지
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        max_tokens=500,
        token_counter=token_counter,  # 토큰 카운터 함수 전달
        start_on="human",
        include_system=True,
    )
    
    # 트리밍된 메시지로 LLM 호출
    response = model_with_tools.invoke(trimmed_messages)
    return {"messages": [response]}


# 트리밍이 적용된 워크플로우 생성
workflow_trimmed = StateGraph(MessagesState)
workflow_trimmed.add_node("agent", call_model_with_trimming)
workflow_trimmed.add_node("tools", tool_node)
workflow_trimmed.add_edge(START, "agent")
workflow_trimmed.add_conditional_edges("agent", tools_condition)
workflow_trimmed.add_edge("tools", "agent")

app_trimmed = workflow_trimmed.compile(checkpointer=memory_trimmed)

print("트리밍이 적용된 에이전트 생성 완료!")
```

---

## RemoveMessage를 사용한 메시지 삭제

`RemoveMessage`는 LangGraph에서 제공하는 특수 수정자로, 메시지 목록에서 특정 메시지를 영구적으로 삭제할 때 사용합니다. 트리밍과 달리 메시지가 실제로 상태에서 제거되므로, 저장된 데이터 양을 줄이거나 민감한 정보를 삭제하는 데 유용합니다.

### 수동으로 메시지 삭제

`update_state()` 메서드와 `RemoveMessage`를 함께 사용하면 그래프 상태에서 원하는 메시지를 선택적으로 제거할 수 있습니다. 각 메시지는 고유한 `id` 속성을 가지고 있어 정확하게 삭제 대상을 지정할 수 있습니다.

아래 코드에서는 저장된 메시지 중 첫 번째 메시지를 삭제합니다.

```python
from langchain_core.messages import RemoveMessage

# 현재 저장된 메시지 확인
messages = app.get_state(config).values["messages"]
print(f"삭제 전 메시지 수: {len(messages)}개\n")

for i, msg in enumerate(messages):
    print(f"  [{i}] {msg.type}: {msg.content[:40]}..." if len(msg.content) > 40 else f"  [{i}] {msg.type}: {msg.content}")
```

```python
# 첫 번째 메시지 삭제
app.update_state(config, {"messages": RemoveMessage(id=messages[0].id)})

# 삭제 결과 확인
messages_after = app.get_state(config).values["messages"]
print(f"삭제 후 메시지 수: {len(messages_after)}개\n")

for i, msg in enumerate(messages_after):
    print(f"  [{i}] {msg.type}: {msg.content[:40]}..." if len(msg.content) > 40 else f"  [{i}] {msg.type}: {msg.content}")
```

---

## 그래프 내부에서 동적으로 메시지 삭제

수동 삭제 외에도 그래프 실행 중에 자동으로 오래된 메시지를 삭제하는 로직을 구현할 수 있습니다. 이는 대화가 길어질 때 컨텍스트 윈도우를 관리하거나 토큰 비용을 절약하는 데 유용합니다.

아래 예시에서는 그래프 실행이 종료될 때 최근 3개 메시지만 유지하고 나머지는 자동으로 삭제하는 `delete_messages` 노드를 추가합니다.

```python
from typing import Literal
from langchain_core.messages import RemoveMessage

# 새로운 체크포인터 생성
memory_auto_delete = MemorySaver()


def delete_messages(state: MessagesState):
    """오래된 메시지 삭제 노드
    
    메시지가 3개를 초과하면 최신 3개만 유지하고 나머지를 삭제합니다.
    """
    messages = state["messages"]
    if len(messages) > 3:
        # 오래된 메시지 삭제 (최신 3개만 유지)
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:-3]]}
    return {}


def should_continue(state: MessagesState) -> Literal["tools", "delete_messages"]:
    """조건부 라우팅 함수
    
    도구 호출이 있으면 tools 노드로, 없으면 delete_messages 노드로 이동합니다.
    """
    last_message = state["messages"][-1]
    # 도구 호출이 없으면 메시지 삭제 노드로 이동
    if not last_message.tool_calls:
        return "delete_messages"
    return "tools"


# 동적 삭제가 포함된 워크플로우 생성
workflow_auto = StateGraph(MessagesState)

# 노드 추가
workflow_auto.add_node("agent", call_model)
workflow_auto.add_node("tools", tool_node)
workflow_auto.add_node("delete_messages", delete_messages)

# 엣지 추가
workflow_auto.add_edge(START, "agent")
workflow_auto.add_conditional_edges("agent", should_continue)
workflow_auto.add_edge("tools", "agent")
workflow_auto.add_edge("delete_messages", END)

# 컴파일
app_auto = workflow_auto.compile(checkpointer=memory_auto_delete)

print("동적 삭제가 적용된 에이전트 생성 완료!")
```

### 수정된 그래프 시각화

수정된 그래프에는 `delete_messages` 노드가 추가되었습니다. 에이전트가 도구 호출 없이 응답을 완료하면 `delete_messages` 노드를 거쳐 종료됩니다.

아래 코드는 수정된 그래프를 시각화합니다.

```python
from IPython.display import Image

# 그래프 시각화
Image("./assets/03-auto-delete-graph.png")
```

### 동적 삭제 테스트

이제 그래프를 여러 번 호출하여 메시지가 누적되는지, 그리고 오래된 메시지가 자동으로 삭제되는지 확인해보겠습니다. 각 호출 후 상태에는 최신 3개의 메시지만 유지됩니다.

아래 코드에서는 연속으로 여러 번 대화를 수행합니다.

```python
# 새로운 스레드 ID로 설정
config_auto = {"configurable": {"thread_id": "auto_delete_test"}}

# 첫 번째 대화
input1 = HumanMessage(content="안녕하세요! 저는 철수입니다.")
for event in app_auto.stream({"messages": [input1]}, config_auto, stream_mode="values"):
    event["messages"][-1].pretty_print()

print(f"\n현재 메시지 수: {len(app_auto.get_state(config_auto).values['messages'])}개")
```

```python
# 두 번째 대화
input2 = HumanMessage(content="제 이름이 뭐라고 했죠?")
for event in app_auto.stream({"messages": [input2]}, config_auto, stream_mode="values"):
    event["messages"][-1].pretty_print()

print(f"\n현재 메시지 수: {len(app_auto.get_state(config_auto).values['messages'])}개")
```

```python
# 세 번째 대화 (이 시점에서 오래된 메시지 삭제 예상)
input3 = HumanMessage(content="오늘 날씨는 어때요?")
for event in app_auto.stream({"messages": [input3]}, config_auto, stream_mode="values"):
    event["messages"][-1].pretty_print()

print(f"\n현재 메시지 수: {len(app_auto.get_state(config_auto).values['messages'])}개")
```

```python
# 최종 상태 확인
final_messages = app_auto.get_state(config_auto).values["messages"]
print(f"최종 메시지 수: {len(final_messages)}개\n")

for msg in final_messages:
    msg.pretty_print()
```

---

## 대화 요약을 통한 컨텍스트 압축

메시지를 트리밍하거나 삭제하면 정보가 손실될 수 있습니다. 대화 요약(summarization)은 오래된 메시지들의 핵심 내용을 압축하여 컨텍스트를 유지하면서도 토큰 사용량을 줄이는 방법입니다.

### 요약 전략

1. 오래된 메시지들을 LLM을 사용하여 요약
2. 요약 내용을 시스템 메시지로 추가
3. 원본 메시지는 삭제

아래 코드에서는 대화 요약 기능을 구현합니다.

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


# 요약을 저장할 수 있는 확장된 State
class SummaryState(TypedDict):
    """요약 기능이 포함된 State
    
    messages: 대화 메시지 리스트
    summary: 이전 대화의 요약 (선택적)
    """
    messages: Annotated[list, add_messages]
    summary: str


def summarize_conversation(messages: list) -> str:
    """대화 내용을 요약하는 함수
    
    주어진 메시지 리스트를 LLM을 사용하여 2-3문장으로 요약합니다.
    """
    # 요약을 위한 프롬프트
    summary_prompt = f"""
    다음 대화 내용을 2-3문장으로 요약해주세요.
    핵심 정보와 컨텍스트를 유지하면서 간결하게 작성해주세요.
    
    대화 내용:
    {chr(10).join([f"{msg.type}: {msg.content}" for msg in messages])}
    """
    
    # LLM으로 요약 생성
    summary_response = model.invoke([HumanMessage(content=summary_prompt)])
    return summary_response.content


print("대화 요약 함수 정의 완료!")
```

```python
# 요약 테스트
test_summary = summarize_conversation(sample_messages[1:])  # 시스템 메시지 제외
print("대화 요약 결과:")
print(test_summary)
```

### 요약이 포함된 에이전트 구축

이제 대화가 길어지면 자동으로 요약을 생성하고, 요약된 내용을 컨텍스트로 사용하는 에이전트를 구축합니다. 이 방식은 정보 손실을 최소화하면서 토큰 효율성을 높입니다.

아래 코드에서는 요약 기능이 포함된 에이전트를 구축합니다.

```python
# 새로운 체크포인터 생성
memory_summary = MemorySaver()


def call_model_with_summary(state: SummaryState):
    """요약을 활용하는 에이전트 노드
    
    이전 대화 요약이 있으면 시스템 메시지로 추가하여 컨텍스트를 유지합니다.
    """
    # 요약이 있으면 시스템 메시지로 추가
    messages = state["messages"]
    if state.get("summary"):
        system_msg = SystemMessage(content=f"이전 대화 요약: {state['summary']}")
        messages = [system_msg] + list(messages)
    
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


def maybe_summarize(state: SummaryState):
    """조건부 요약 노드
    
    메시지가 6개를 초과하면 처음 4개를 요약하고 삭제합니다.
    """
    messages = state["messages"]
    
    if len(messages) > 6:
        # 처음 4개 메시지 요약
        messages_to_summarize = messages[:4]
        summary = summarize_conversation(messages_to_summarize)
        
        # 요약된 메시지 삭제
        delete_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize]
        
        return {
            "messages": delete_messages,
            "summary": summary
        }
    
    return {}


def should_continue_summary(state: SummaryState) -> Literal["tools", "summarize"]:
    """조건부 라우팅 함수"""
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "summarize"
    return "tools"


# 요약 기능이 포함된 워크플로우 생성
workflow_summary = StateGraph(SummaryState)

workflow_summary.add_node("agent", call_model_with_summary)
workflow_summary.add_node("tools", tool_node)
workflow_summary.add_node("summarize", maybe_summarize)

workflow_summary.add_edge(START, "agent")
workflow_summary.add_conditional_edges("agent", should_continue_summary)
workflow_summary.add_edge("tools", "agent")
workflow_summary.add_edge("summarize", END)

app_summary = workflow_summary.compile(checkpointer=memory_summary)

print("요약 기능이 포함된 에이전트 생성 완료!")
```

```python
from IPython.display import Image

# 그래프 시각화
Image("./assets/03-summary-graph.png")
```

---

## 프로덕션 환경: 영구 저장소 사용

`MemorySaver`는 인메모리 저장소이므로 서버 재시작 시 데이터가 사라집니다. 프로덕션 환경에서는 PostgreSQL, SQLite, Redis 등의 영구 저장소를 사용하는 체크포인터를 선택해야 합니다.

### 지원되는 체크포인터

| 체크포인터 | 패키지 | 특징 |
|-----------|--------|------|
| PostgresSaver | langgraph-checkpoint-postgres | ACID 준수, 엔터프라이즈 표준 |
| SqliteSaver | langgraph-checkpoint-sqlite | 가벼운 로컬 저장소 |
| RedisSaver | langgraph-checkpoint-redis | 초고속 메모리 DB, 캐싱 최적화 |

### PostgreSQL 사용 예시

PostgreSQL 체크포인터를 사용하면 서버를 재시작하거나 연결을 끊었다가 다시 연결해도 이전 대화가 유지됩니다. 이것이 `MemorySaver`와의 가장 큰 차이점입니다.

`PostgresSaver.from_conn_string()`으로 연결하고, 첫 실행 시 `setup()`으로 필요한 테이블을 생성합니다. Context manager(`with` 문)를 사용하면 연결이 자동으로 관리됩니다.

> 아래 코드를 실행하려면 PostgreSQL 서버가 필요합니다. Docker를 사용하면 간편하게 설정할 수 있습니다.

#### Docker를 사용한 PostgreSQL 설정

개발 환경에서 PostgreSQL을 빠르게 설정하려면 Docker를 사용하는 것이 편리합니다.

```bash
# PostgreSQL 컨테이너 실행
docker run --name langgraph_db \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=langgraph_db \
    -p 5432:5432 \
    -d postgres:15

# 연결 문자열
DB_URI = "postgresql://postgres:postgres@localhost:5432/langgraph_db"
```

```python
from langgraph.checkpoint.postgres import PostgresSaver

# PostgreSQL 연결 문자열
DB_URI = "postgresql://postgres:postgres@localhost:5432/langgraph_db"

# PostgresSaver를 Context manager로 사용하여 연결을 관리
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # 첫 실행 시 체크포인터 테이블 생성
    checkpointer.setup()

    # PostgresSaver 체크포인터로 그래프 컴파일
    graph = graph_builder.compile(checkpointer=checkpointer)

    # Config 설정: thread_id로 대화 세션 구분
    pg_config = RunnableConfig(
        configurable={"thread_id": "postgres_session_1"},
    )

    # 첫 번째 대화: 자기소개
    inputs = {"messages": [{"role": "user", "content": "안녕하세요! 저는 영희입니다."}]}
    stream_graph(graph, inputs=inputs, config=pg_config)
```

**핵심 포인트**: 아래 코드에서는 `with` 블록을 새로 열어 **별도의 연결**을 생성합니다. `MemorySaver`였다면 이전 대화를 기억하지 못하겠지만, PostgreSQL에 저장되어 있으므로 이전 대화가 유지됩니다.

```python
# 새로운 연결에서도 이전 대화가 유지되는지 확인
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # 같은 graph_builder로 다시 컴파일
    graph = graph_builder.compile(checkpointer=checkpointer)

    # 같은 thread_id로 후속 질문
    pg_config = RunnableConfig(
        configurable={"thread_id": "postgres_session_1"},
    )

    # 두 번째 대화: 이름 기억 확인
    inputs = {"messages": [{"role": "user", "content": "제 이름이 뭐라고 했죠?"}]}
    stream_graph(graph, inputs=inputs, config=pg_config)
```

```python
# PostgreSQL에 저장된 대화 상태 확인
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    graph = graph_builder.compile(checkpointer=checkpointer)

    pg_config = RunnableConfig(
        configurable={"thread_id": "postgres_session_1"},
    )

    # 저장된 메시지 조회
    snapshot = graph.get_state(pg_config)
    print(f"PostgreSQL에 저장된 메시지 수: {len(snapshot.values['messages'])}개\n")
    for msg in snapshot.values["messages"]:
        msg.pretty_print()
```

---

## 정리

이번 튜토리얼에서는 LangGraph에서 메모리를 추가하고 관리하는 방법을 학습했습니다.

### 핵심 내용

- **체크포인터**: 그래프의 상태를 저장하고 복원하는 컴포넌트
- **thread_id**: 대화 세션을 구분하는 식별자로, 같은 thread_id에서는 대화가 이어짐
- **MemorySaver**: 개발/테스트용 인메모리 체크포인터
- **get_state()**: 현재 상태 스냅샷 조회
- **get_state_history()**: 상태 변경 이력 조회

### 단기 메모리 관리 전략

| 기법 | 특징 | 사용 사례 |
|------|------|----------|
| 트리밍 | LLM 호출 전 메시지 필터링 | 컨텍스트 윈도우 제한 관리 |
| 삭제 | 상태에서 메시지 영구 제거 | 민감 정보 삭제, 저장 공간 관리 |
| 요약 | 오래된 메시지를 압축 | 정보 손실 최소화하면서 토큰 절약 |

### 전략 선택 가이드

- **트리밍**: 간단하고 빠름, 정보 손실 가능
- **삭제**: 저장 공간 절약, 정보 손실 가능
- **요약**: 정보 보존, 추가 LLM 호출 비용 발생

### 프로덕션 체크포인터

- **PostgresSaver**: ACID 준수, 엔터프라이즈 표준
- **SqliteSaver**: 가벼운 로컬 저장소
- **RedisSaver**: 초고속 메모리 DB, 캐싱 최적화

(source: 01-LangGraph-Add-Memory.ipynb)

## Related pages

- [[langgraph-building-graphs]]
- [[langgraph-models]]
