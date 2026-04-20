# LangGraph Agents

**Summary**: Learning material extracted from 01-LangGraph-Agents.ipynb.

**Sources**: 01-LangGraph-Agents.ipynb

**Last updated**: 2026-04-17

---

에이전트는 언어 모델(LLM)과 도구(Tool)를 결합하여 복잡한 작업을 수행하는 시스템입니다. 에이전트는 주어진 작업에 대해 추론하고, 필요한 도구를 선택하며, 목표를 향해 반복적으로 작업을 수행합니다.

![](./assets/langgraph-agent.png)

LangChain의 `create_agent` 함수는 프로덕션 수준의 에이전트 구현을 제공합니다. 이 함수를 사용하면 모델 선택, 도구 연동, 미들웨어 설정 등을 손쉽게 구성할 수 있습니다.

> 참고 문서: [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)

## 환경 설정

에이전트 튜토리얼을 시작하기 전에 필요한 환경을 설정합니다. `dotenv`를 사용하여 API 키를 로드하고, `langchain_teddynote`의 로깅 기능을 활성화하여 LangSmith에서 실행 추적을 확인할 수 있도록 합니다.

LangSmith 추적을 활성화하면 에이전트의 추론 과정, 도구 호출, 응답 생성 등을 시각적으로 디버깅할 수 있어 개발에 큰 도움이 됩니다.

아래 코드는 환경 변수를 로드하고 LangSmith 프로젝트를 설정합니다.

```python
from dotenv import load_dotenv
from langchain_teddynote import logging

# 환경 변수 로드
load_dotenv(override=True)
# 추적을 위한 프로젝트 이름 설정
logging.langsmith("LangGraph-V1-Tutorial")
```

## 모델 (Model)

에이전트의 추론 엔진인 LLM은 `create_agent` 함수의 첫 번째 인자로 전달합니다. 모델을 지정하는 방법은 크게 두 가지가 있습니다.

### 방법 1: 문자열 식별자 (provider:model)

가장 간단한 방법은 `provider:model` 형식의 문자열을 직접 `create_agent`에 전달하는 것입니다. 이 방식은 빠른 프로토타이핑에 적합합니다.

### 방법 2: init_chat_model 함수

`init_chat_model` 함수를 사용하면 모델 인스턴스를 먼저 생성한 후 전달할 수 있습니다. 이 방식은 모델 옵션을 세밀하게 제어할 때 유용합니다.

아래 코드는 두 가지 방법을 모두 보여주는 예시입니다.

```python
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

# 방법 1: 문자열 식별자를 직접 전달 (빠른 프로토타이핑에 적합)
# agent = create_agent("anthropic:claude-sonnet-4-5", tools=[])

# 방법 2: init_chat_model로 모델 인스턴스 생성 후 전달
# OpenAI 키를 사용하는 경우 gpt-4.1-mini, gpt-4.1 등으로 변경하세요
model = init_chat_model("claude-sonnet-4-5")

# 모델 인스턴스를 사용하여 에이전트 생성
agent = create_agent(model, tools=[])
```

### 모델 세부 설정

더 세밀한 제어가 필요한 경우, 모델 생성 시 추가 옵션을 전달하여 다양한 설정을 적용할 수 있습니다.

- `temperature`: 응답의 무작위성을 제어합니다 (0에 가까울수록 일관된 응답, 1에 가까울수록 다양한 응답)
- `max_tokens`: 생성할 최대 토큰 수를 제한합니다
- `timeout`: 요청 타임아웃(초)을 설정합니다

모델 세부 설정을 적용하는 방법은 두 가지가 있습니다.

**방법 1: init_chat_model 사용**

`init_chat_model` 함수에 추가 옵션을 전달하는 방식입니다. Provider에 관계없이 동일한 인터페이스로 사용할 수 있어 편리합니다.

**방법 2: Provider별 클래스 직접 사용**

`ChatAnthropic`, `ChatOpenAI` 등 Provider별 클래스를 직접 인스턴스화하는 방식입니다. Provider 고유의 옵션을 세밀하게 제어할 때 유용합니다.

아래 코드는 두 가지 방법을 모두 보여주는 예시입니다.

```python
# 방법 1: init_chat_model에 추가 옵션 전달
# Provider에 관계없이 동일한 인터페이스로 사용 가능
model = init_chat_model(
    "claude-sonnet-4-5",  # OpenAI 키를 사용하는 경우 gpt-4.1-mini, gpt-4.1 등으로 변경하세요
    temperature=0.1,  # 응답의 무작위성 제어
    max_tokens=1000,  # 최대 생성 토큰 수
    timeout=30,  # 요청 타임아웃(초)
)

agent = create_agent(model, tools=[])
```

```python
# 방법 2: Provider별 클래스 직접 사용
# Provider 고유의 옵션을 세밀하게 제어할 때 유용
from langchain_anthropic import ChatAnthropic
# from langchain_openai import ChatOpenAI  # OpenAI 사용 시

model = ChatAnthropic(
    model="claude-sonnet-4-5",
    temperature=0.1,
    max_tokens=1000,
    timeout=30,
)

agent = create_agent(model, tools=[])
```

### 동적 모델 선택

동적 모델 선택은 런타임에 현재 상태와 컨텍스트를 기반으로 사용할 모델을 결정하는 패턴입니다. 이를 통해 정교한 라우팅 로직과 비용 최적화가 가능합니다. 예를 들어, 간단한 질문에는 경량 모델을, 복잡한 대화에는 고급 모델을 사용할 수 있습니다.

`wrap_model_call` 데코레이터를 사용하면 모델 호출 전에 요청을 검사하고 수정할 수 있는 미들웨어를 생성할 수 있습니다.

![](../assets/wrap_model_call.png)

아래 코드는 대화 길이에 따라 모델을 동적으로 선택하는 예시입니다.

### ModelRequest 속성

`ModelRequest`는 에이전트의 모델 호출 정보를 담는 데이터 클래스로, 미들웨어에서 요청을 검사하고 수정할 때 사용됩니다. `override()` 메서드를 통해 여러 속성을 동시에 변경할 수 있습니다.

아래 코드는 ModelRequest를 사용하여 동적으로 모델과 시스템 프롬프트를 변경하는 예시입니다.

```python
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

# 기본 모델과 고급 모델 정의
basic_model = init_chat_model("claude-haiku-4-5")
advanced_model = init_chat_model("claude-sonnet-4-5")


@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """대화 복잡도에 따라 모델 선택"""
    message_count = len(request.state["messages"])

    # 긴 대화에는 고급 모델 사용
    if message_count > 10:
        model = advanced_model
    else:
        model = basic_model

    request.model = model
    print(f"모델 선택: {request.model.model}")
    return handler(request)


agent = create_agent(
    model=basic_model, tools=[], middleware=[dynamic_model_selection]  # 기본 모델
)
```

```python
from langchain_teddynote.messages import stream_graph
from langchain_core.messages import HumanMessage

stream_graph(
    agent,
    inputs={
        "messages": [HumanMessage(content="머신러닝의 동작 원리에 대해서 설명해줘")]
    },
)
```

**ModelRequest 주요 속성:**

| 속성 | 설명 |
|:---|:---|
| `model` | 사용할 `BaseChatModel` 인스턴스 |
| `system_prompt` | 시스템 프롬프트 (선택적) |
| `messages` | 대화 메시지 리스트 (시스템 프롬프트 제외) |
| `tool_choice` | 도구 선택 설정 |
| `tools` | 사용 가능한 도구 리스트 |
| `response_format` | 응답 형식 지정 |
| `state` | 현재 에이전트 상태 (`AgentState`) |
| `runtime` | 에이전트 런타임 정보 |
| `model_settings` | 추가 모델 설정 (dict) |

아래 코드는 `override()` 메서드를 사용하여 여러 속성을 동시에 변경하는 예시입니다.

```python
@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """대화 복잡도에 따라 모델 선택"""
    message_count = len(request.state["messages"][-1].content)
    print(f"글자수: {message_count}")

    # 긴 대화에는 고급 모델 사용
    if message_count > 10:
        # 여러 속성 동시 변경
        new_request = request.override(
            model=advanced_model,
            system_prompt="emoji 를 사용해서 답변해줘",
            tool_choice="auto",
        )
    else:
        new_request = request.override(
            model=basic_model,
            system_prompt="한 문장으로 간결하게 답변해줘. emoji 는 사용하지 말아줘.",
            tool_choice="auto",
        )
    print(f"모델 선택: {new_request.model.model}")
    return handler(new_request)

    
agent = create_agent(
    model=basic_model, tools=[], middleware=[dynamic_model_selection]  # 기본 모델
)
```

### 글자수 기반 모델 선택 테스트

아래는 글자수 10자 미만일 때의 응답입니다. 간결한 답변을 생성하도록 설정되어 있습니다.

```python
stream_graph(agent, inputs={"messages": [HumanMessage(content="머신러닝 동작원리")]})
```

아래는 글자수 10자 이상일 때의 응답입니다. 이모지를 사용하여 친근한 답변을 생성하도록 설정되어 있습니다.

```python
stream_graph(
    agent,
    inputs={
        "messages": [
            HumanMessage(content="머신러닝의 동작 원리에 대해서 설명해 주세요.")
        ]
    },
)
```

---

## 프롬프트

에이전트의 동작을 제어하는 핵심 요소 중 하나는 시스템 프롬프트입니다. 시스템 프롬프트를 통해 에이전트의 역할, 응답 스타일, 제약 조건 등을 정의할 수 있습니다.

### 시스템 프롬프트

`system_prompt` 매개변수를 사용하여 에이전트의 기본 동작을 정의할 수 있습니다. 시스템 프롬프트는 모든 대화에서 일관되게 적용되며, 에이전트의 페르소나와 응답 가이드라인을 설정하는 데 사용됩니다.

아래 코드는 간결하고 정확한 응답을 생성하도록 시스템 프롬프트를 설정한 에이전트를 생성합니다.

```python
# OpenAI 키를 사용하는 경우 gpt-4.1-mini, gpt-4.1 등으로 변경하세요
model = init_chat_model("claude-sonnet-4-5")

agent = create_agent(
    model,
    system_prompt="You are a helpful assistant. Be concise and accurate.",
)
```

아래는 설정된 시스템 프롬프트를 사용한 에이전트의 응답 예시입니다.

```python
stream_graph(
    agent,
    inputs={"messages": [HumanMessage(content="대한민국의 수도는 어디야?")]},
)
```

### 동적 시스템 프롬프트 (Dynamic Prompting)

런타임 컨텍스트나 에이전트 상태를 기반으로 시스템 프롬프트를 동적으로 생성해야 하는 경우가 있습니다. `dynamic_prompt` 데코레이터를 사용하면 요청마다 다른 시스템 프롬프트를 적용할 수 있습니다.

이 기능은 사용자 역할, 언어 설정, 응답 형식 등을 런타임에 결정해야 할 때 유용합니다. `context_schema`를 정의하여 에이전트 호출 시 필요한 컨텍스트 정보를 전달할 수 있습니다.

아래 코드는 답변 형식과 길이를 동적으로 설정하는 에이전트를 생성합니다.

```python
from typing import TypedDict
from langchain.agents.middleware import dynamic_prompt, ModelRequest


class Context(TypedDict):
    prompt_type: str
    length: int


@dynamic_prompt
def user_role_prompt(request: ModelRequest) -> str:
    """사용자 역할에 따라 시스템 프롬프트 생성"""
    # 답변 형식 설정
    answer_type = (
        request.runtime.context.get("prompt_type", "default")
        if request.runtime.context
        else "default"
    )
    # 답변 길이 설정
    answer_length = (
        request.runtime.context.get("length", 20) if request.runtime.context else 20
    )
    base_prompt = "You are a helpful assistant. Answer in Korean.\n"

    # 답변 형식에 따라 시스템 프롬프트 생성(동적 프롬프팅)
    if answer_type == "default":
        return f"{base_prompt} [답변 형식] 간결하게 답변해줘. 답변 길이는 {answer_length}자 이하로 해줘."
    elif answer_type == "sns":
        return f"{base_prompt} [답변 형식] SNS 형식으로 답변해줘. 답변 길이는 {answer_length}자 이하로 해줘."
    elif answer_type == "article":
        return f"{base_prompt} [답변 형식] 뉴스 기사 형식으로 답변해줘. 답변 길이는 {answer_length}자 이하로 해줘."
    else:
        return f"{base_prompt} [답변 형식] 간결하게 답변해줘. 답변 길이는 {answer_length}자 이하로 해줘."


# 컨텍스트 스키마와 user_role_prompt 미들웨어를 사용하여 에이전트 생성
agent = create_agent(
    model=model,
    middleware=[user_role_prompt],
    context_schema=Context,
)
```

```python
# 컨텍스트에 따라 시스템 프롬프트가 동적으로 설정됩니다
stream_graph(
    agent,
    inputs={
        "messages": [HumanMessage(content="머신러닝의 동작 원리에 대해서 설명해줘")]
    },
    context=Context(prompt_type="article", length=1000),
)
```

```python
stream_graph(
    agent,
    inputs={
        "messages": [HumanMessage(content="머신러닝의 동작 원리에 대해서 설명해줘")]
    },
    context=Context(prompt_type="sns", length=50),
)
```

---

## 미들웨어

미들웨어를 사용하면 모델 호출 전후에 커스텀 로직을 실행할 수 있습니다. `@before_model` 및 `@after_model` 데코레이터를 사용하여 모델 호출을 감싸는 훅을 정의할 수 있습니다.

**미들웨어 활용 사례:**
- 모델 호출 전 메시지 전처리 (예: 쿼리 재작성)
- 모델 호출 후 응답 후처리 (예: 필터링, 로깅)
- 상태 기반 동적 라우팅

아래 코드는 모델 호출 전후에 로깅을 수행하는 미들웨어 예시입니다.

```python
from langchain.agents.middleware import (
    before_model,
    after_model,
)
from langchain.agents.middleware import (
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from typing import Any, Callable


# 노드 스타일: 모델 호출 전 로깅
@before_model
def log_before_model(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    print(
        f"\033[95m\n\n모델 호출 전 메시지 {len(state['messages'])}개가 있습니다\033[0m"
    )
    last_message = state["messages"][-1].content
    # OpenAI 키를 사용하는 경우 gpt-4.1-mini, gpt-4.1 등으로 변경하세요
    llm = init_chat_model("claude-sonnet-4-5")

    query_rewrite = (
        PromptTemplate.from_template(
            "Rewrite the following query to be more understandable. Do not change the original meaning. Make it one sentence: {query}"
        )
        | llm
    )
    rewritten_query = query_rewrite.invoke({"query": last_message})

    return {"messages": [rewritten_query.content]}


@after_model
def log_after_model(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:

    print(
        f"\033[95m\n\n모델 호출 후 메시지 {len(state['messages'])}개가 있습니다\033[0m"
    )
    for i, message in enumerate(state["messages"]):
        print(f"[{i}] {message.content}")
    return None
```

```python
agent = create_agent(
    model,
    middleware=[
        log_before_model,
        log_after_model,
    ],
)
```

```python
stream_graph(
    agent,
    inputs={"messages": [HumanMessage(content="대한민국 수도")]},
)
```

### 클래스 기반 미들웨어

데코레이터 대신 클래스 기반 미들웨어를 사용할 수 있습니다. `AgentMiddleware` 클래스를 상속하고 `before_model` 및 `after_model` 메서드를 오버라이드하여 커스텀 로직을 구현합니다.

클래스 기반 미들웨어는 커스텀 상태 스키마를 정의하거나 복잡한 미들웨어 로직을 구조화할 때 유용합니다.

아래 코드는 클래스 기반 미들웨어를 사용하여 커스텀 상태를 관리하는 예시입니다.

```python
from typing import Any
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware


# 커스텀 상태 스키마 정의
class CustomState(AgentState):
    user_preferences: dict


class CustomMiddleware(AgentMiddleware):
    state_schema = CustomState
    tools = []

    def before_model(self, state: CustomState, runtime) -> dict[str, Any] | None:
        # 모델 호출 전 커스텀 로직
        pass


agent = create_agent(model, tools=[], middleware=[CustomMiddleware()])

# 에이전트는 이제 메시지 외에 추가 상태를 추적할 수 있습니다
result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "I prefer technical explanations"}],
        "user_preferences": {"style": "technical", "verbosity": "detailed"},
    }
)
```

### 모델 오류 시 재시도 로직

`wrap_model_call` 데코레이터를 사용하면 모델 호출 실패 시 자동으로 재시도하는 로직을 구현할 수 있습니다. 이는 네트워크 오류나 일시적인 API 장애에 대응하는 데 유용합니다.

아래 코드는 최대 3회까지 재시도하는 미들웨어 예시입니다.

```python
@wrap_model_call
def retry_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    for attempt in range(3):
        try:
            return handler(request)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"오류 발생으로 {attempt + 1}/3 번째 재시도합니다: {e}")
```

```python
# OpenAI 키를 사용하는 경우 gpt-4.1-mini, gpt-4.1 등으로 변경하세요
# 일부러 존재하지 않는 모델명을 사용하여 재시도 로직을 테스트합니다
model = init_chat_model("claude-sonnet-4-5-invalid")

agent = create_agent(
    model,
    middleware=[retry_model],
)
```

```python
stream_graph(
    agent,
    inputs={"messages": [HumanMessage(content="대한민국의 수도는?")]},
)
```

(source: 01-LangGraph-Agents.ipynb)

## Related pages

- [[langgraph-models]]
- [[langgraph-middleware]]
- [[langgraph-supervisor]]
