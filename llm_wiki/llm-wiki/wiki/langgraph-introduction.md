# LangGraph Introduction

**Summary**: Learning material extracted from 01-LangGraph-Introduction.ipynb.

**Sources**: 01-LangGraph-Introduction.ipynb

**Last updated**: 2026-04-17

---

## TypedDict

`dict`와 `TypedDict`의 차이점과 `TypedDict`가 왜 `dict` 대신 사용되는지 설명해드리겠습니다.

1. `dict`와 `TypedDict`의 주요 차이점:

   a) 타입 검사:
      - `dict`: 런타임에 타입 검사를 하지 않습니다.
      - `TypedDict`: 정적 타입 검사를 제공합니다. 즉, 코드 작성 시 IDE나 타입 체커가 오류를 미리 잡아낼 수 있습니다.

   b) 키와 값의 타입:
      - `dict`: 키와 값의 타입을 일반적으로 지정합니다 (예: Dict[str, str]).
      - `TypedDict`: 각 키에 대해 구체적인 타입을 지정할 수 있습니다.

   c) 유연성:
      - `dict`: 런타임에 키를 추가하거나 제거할 수 있습니다.
      - `TypedDict`: 정의된 구조를 따라야 합니다. 추가적인 키는 타입 오류를 발생시킵니다.

2. `TypedDict`가 `dict` 대신 사용되는 이유:

   a) 타입 안정성: 
      `TypedDict`는 더 엄격한 타입 검사를 제공하여 잠재적인 버그를 미리 방지할 수 있습니다.

   b) 코드 가독성:
      `TypedDict`를 사용하면 딕셔너리의 구조를 명확하게 정의할 수 있어 코드의 가독성이 향상됩니다.

   c) IDE 지원:
      `TypedDict`를 사용하면 IDE에서 자동 완성 및 타입 힌트를 더 정확하게 제공받을 수 있습니다.

   d) 문서화:
      `TypedDict`는 코드 자체가 문서의 역할을 하여 딕셔너리의 구조를 명확히 보여줍니다.

아래 코드에서는 `dict`와 `TypedDict`를 사용하여 두 방식의 차이점을 직접 비교해 보겠습니다.

```python
# TypedDict와 Dict의 차이점 예시
from typing import Dict, TypedDict

# 일반적인 파이썬 딕셔너리(dict) 사용
sample_dict: Dict[str, str] = {
    "name": "테디",
    "age": "30",  # 문자열로 저장 (dict 에서는 가능)
    "job": "개발자",
}


# TypedDict 사용
class Person(TypedDict):
    name: str
    age: int  # 정수형으로 명시
    job: str


typed_dict: Person = {"name": "셜리", "age": 25, "job": "디자이너"}
```

```python
# dict의 경우
sample_dict["age"] = 35  # 문자열에서 정수로 변경되어도 오류 없음
sample_dict["new_field"] = "추가 정보"  # 새로운 필드 추가 가능

# TypedDict의 경우
typed_dict["age"] = 35  # 정수형으로 올바르게 사용
typed_dict["age"] = "35"  # 타입 체커가 오류를 감지함
typed_dict["new_field"] = (
    "추가 정보"  # 타입 체커가 정의되지 않은 키라고 오류를 발생시킴
)
```

하지만 TypedDict의 진정한 가치는 정적 타입 검사기를 사용할 때 드러납니다.

예를 들어, mypy와 같은 정적 타입 검사기를 사용하거나 PyCharm, VS Code 등의 IDE에서 타입 검사 기능을 활성화하면, 이러한 타입 불일치와 정의되지 않은 키 추가를 오류로 표시합니다. 이처럼 정적 타입 검사기를 활용하면 코드 실행 전에 잠재적인 버그를 미리 발견하고 수정할 수 있어 개발 생산성이 크게 향상됩니다.

## Annotated

`Annotated`는 Python의 `typing` 모듈에서 제공하는 특별한 타입 힌트로, 기존 타입에 메타데이터를 추가할 수 있게 해줍니다. LangGraph에서는 상태(State) 필드에 리듀서(reducer) 함수를 지정할 때 주로 사용됩니다.

`Annotated`를 사용하면 타입 힌트에 추가 정보를 포함시킬 수 있어 코드의 가독성을 높이고, 더 자세한 타입 정보를 제공할 수 있습니다.

### Annotated 주요 기능(사용 이유)

1. **추가 정보 제공**: 타입 힌트에 메타데이터를 추가하여 더 상세한 정보를 제공합니다.
2. **문서화**: 코드 자체에 추가 설명을 포함시켜 문서화 효과를 얻을 수 있습니다.
3. **유효성 검사**: 특정 라이브러리(예: Pydantic)와 함께 사용하여 데이터 유효성 검사를 수행할 수 있습니다.
4. **프레임워크 지원**: 일부 프레임워크(예: LangGraph)에서는 `Annotated`를 사용하여 특별한 동작을 정의합니다.

**기본 문법**

- `Type`: 기본 타입 (예: `int`, `str`, `List[str]` 등)
- `metadata1`, `metadata2`, ...: 추가하고자 하는 메타데이터

```python
from typing import Annotated

variable: Annotated[Type, metadata1, metadata2, ...]
```

### 사용 예시

아래에서는 `Annotated`의 다양한 사용 예시를 살펴보겠습니다. 기본 사용법부터 Pydantic 라이브러리와의 통합, 그리고 LangGraph에서의 활용까지 단계별로 확인합니다.

### 기본 사용

가장 기본적인 `Annotated` 사용 방법입니다. 타입 힌트와 함께 문자열 형태의 메타데이터를 추가하여 변수의 의미를 명확히 할 수 있습니다.

아래 코드에서는 `name`과 `age` 변수에 설명 문자열을 메타데이터로 추가합니다.

```python
from typing import Annotated

# 타입 힌트에 메타데이터(설명)를 추가하는 기본 사용법
name: Annotated[str, "사용자 이름"]
age: Annotated[int, "사용자 나이 (0-150)"]
```

### Pydantic과 함께 사용

Pydantic은 Python에서 데이터 유효성 검사를 위한 라이브러리입니다. `Annotated`와 Pydantic의 `Field`를 함께 사용하면 각 필드에 대해 상세한 제약 조건과 설명을 추가할 수 있습니다.

아래 코드에서는 `Employee` 모델을 정의하고, 각 필드에 최소/최대 값, 길이 제한 등의 유효성 검사 규칙을 적용합니다.

```python
from typing import Annotated, List
from pydantic import Field, BaseModel, ValidationError


class Employee(BaseModel):
    id: Annotated[int, Field(..., description="직원 ID")]
    name: Annotated[str, Field(..., min_length=3, max_length=50, description="이름")]
    age: Annotated[int, Field(gt=18, lt=65, description="나이 (19-64세)")]
    salary: Annotated[
        float, Field(gt=0, lt=10000, description="연봉 (단위: 만원, 최대 10억)")
    ]
    # Pydantic v2: min_items/max_items 대신 min_length/max_length 사용
    skills: Annotated[
        List[str], Field(min_length=1, max_length=10, description="보유 기술 (1-10개)")
    ]


# 유효한 데이터로 인스턴스 생성
try:
    valid_employee = Employee(
        id=1, name="테디노트", age=30, salary=1000, skills=["Python", "LangChain"]
    )
    print("유효한 직원 데이터:", valid_employee)
except ValidationError as e:
    print("유효성 검사 오류:", e)

# 유효하지 않은 데이터로 인스턴스 생성 시도
try:
    invalid_employee = Employee(
        name="테디",  # 이름이 너무 짧음
        age=17,  # 나이가 범위를 벗어남
        salary=20000,  # 급여가 범위를 벗어남
        skills="Python",  # 리스트가 아님
    )
except ValidationError as e:
    print("유효성 검사 오류:")
    for error in e.errors():
        print(f"- {error['loc'][0]}: {error['msg']}")
```

### LangGraph에서의 사용(add_messages)

LangGraph에서 `Annotated`는 상태(State) 필드에 리듀서(reducer) 함수를 지정할 때 사용됩니다. 리듀서 함수는 상태가 업데이트될 때 기존 값과 새 값을 어떻게 결합할지 정의합니다.

`add_messages`는 LangGraph에서 가장 많이 사용되는 리듀서로, 새로운 메시지를 기존 메시지 리스트에 추가하는 역할을 합니다. 이를 통해 대화 기록을 자연스럽게 누적할 수 있습니다.

> 참고 문서: [LangGraph Graph API](https://langchain-ai.github.io/langgraph/)

아래 코드에서는 `messages` 필드에 `add_messages` 리듀서를 적용하여 메시지가 자동으로 누적되도록 설정합니다.

```python
from typing import Annotated, TypedDict
from langgraph.graph import add_messages


# add_messages 리듀서를 State 필드에 적용하는 예시
class MyData(TypedDict):
    messages: Annotated[list, add_messages]
```

**참고**

1. `Annotated`는 Python 3.9 이상에서 사용 가능합니다. 단, **LangGraph v1은 Python 3.10 이상**을 필요로 합니다.
2. 런타임에는 `Annotated`가 무시되므로, 실제 동작에는 영향을 주지 않습니다.
3. 타입 검사 도구나 IDE가 `Annotated`를 지원해야 그 효과를 볼 수 있습니다.

## add_messages

`messages` 키는 [`add_messages`](https://langchain-ai.github.io/langgraph/reference/graphs/?h=add+messages#add_messages) 리듀서 함수로 주석이 달려 있으며, 이는 LangGraph에게 기존 목록에 새 메시지를 추가하도록 지시합니다.

주석이 없는 상태 키는 각 업데이트에 의해 덮어쓰여져 가장 최근의 값이 저장됩니다.

`add_messages` 함수는 2개의 인자(left, right)를 받으며 좌, 우 메시지를 병합하는 방식으로 동작합니다.

**주요 기능**

- 두 개의 메시지 리스트를 병합합니다.
- 기본적으로 "append-only" 상태를 유지합니다.
- 동일한 ID를 가진 메시지가 있을 경우, 새 메시지로 기존 메시지를 대체합니다.

**동작 방식**

- `right`의 메시지 중 `left`에 동일한 ID를 가진 메시지가 있으면, `right`의 메시지로 대체됩니다.
- 그 외의 경우 `right`의 메시지가 `left`에 추가됩니다.

**매개변수**

- `left` (Messages): 기본 메시지 리스트
- `right` (Messages): 병합할 메시지 리스트 또는 단일 메시지

**반환값**

- `Messages`: `right`의 메시지들이 `left`에 병합된 새로운 메시지 리스트

아래 코드에서는 `add_messages` 함수를 사용하여 두 메시지 리스트를 병합하는 기본 예시를 살펴봅니다.

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import add_messages

# 기본 사용 예시
msgs1 = [HumanMessage(content="안녕하세요?", id="1")]
msgs2 = [AIMessage(content="반갑습니다~", id="2")]

result1 = add_messages(msgs1, msgs2)
print(result1)
```

### 동일한 ID를 가진 메시지 대체

`add_messages` 리듀서의 중요한 특징 중 하나는 동일한 ID를 가진 메시지가 있을 경우 기존 메시지를 새 메시지로 대체한다는 점입니다. 이 기능을 활용하면 특정 메시지를 업데이트하거나 수정할 수 있습니다.

아래 코드에서는 동일한 ID("1")를 가진 두 메시지를 병합할 때, 나중에 추가된 메시지가 기존 메시지를 대체하는 것을 확인할 수 있습니다.

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import add_messages

# 동일한 ID("1")를 가진 두 메시지를 병합
msgs1 = [HumanMessage(content="안녕하세요?", id="1")]
msgs2 = [AIMessage(content="반갑습니다~", id="1")]  # msgs1과 동일한 ID "1" 사용

# ID가 같으므로 msgs1의 메시지가 msgs2의 메시지로 대체됨
result2 = add_messages(msgs1, msgs2)
print(result2)
```

## 정리

LangGraph State의 핵심 개념을 모두 학습했습니다.

### 학습 완료 체크리스트

**이론 학습**

- **TypedDict**는 딕셔너리의 키와 값 타입을 명시적으로 선언하는 방법입니다.
- **Annotated**는 기존 타입 힌트에 추가적인 메타데이터를 결합하는 기능을 제공합니다.
- **add_messages**는 LangGraph가 제공하는 기본 리듀서 함수로, 새로운 메시지를 기존 메시지 리스트에 누적합니다.


### 다음 단계 추천

이제 여러분은 **LangGraph의 State 관리체계** 를 이해하셨습니다. 다음 튜토리얼에서는 **기본 ChatBot 구축** 에 대해 학습해보세요.

(source: 01-LangGraph-Introduction.ipynb)

## Related pages

- [[langgraph-building-graphs]]
- [[langgraph-memory]]
