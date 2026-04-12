# LangGraph 기반 에이전트형 파이썬 코딩 시스템 - 구현 계획

## Context
사용자가 자연어로 목표를 주면, LangGraph 그래프가 **계획 → 코딩 → 실행 → 수정** 루프를 자동으로 돌며 작동하는 코드를 만들어내는 에이전트.

**핵심 제약:** Local LLM (OpenAI 호환 API) 사용. LLM 능력이 제한적이므로 **노드당 하나의 단순한 작업**만 부여. 구조화 출력(JSON/Pydantic) 대신 **plain text + 코드블록 파싱** 사용.

---

## 1. State 설계 (`state.py`)

```python
from typing import TypedDict, Annotated
import operator

def merge_dicts(old, new):
    if old is None: return new or {}
    if new is None: return old
    return {**old, **new}

class AgentState(TypedDict):
    goal: str                                          # 사용자 원본 목표
    plan: str                                          # 현재 계획 텍스트
    plan_approved: bool                                # Human-in-the-loop: 사용자 승인 여부
    files: Annotated[dict[str, str], merge_dicts]      # 파일명→내용 (reducer: 병합)
    test_code: str                                     # 테스트 파일 내용
    test_command: str                                  # 실행할 테스트 명령어
    logs: Annotated[list[dict], operator.add]           # 매 반복 기록 (reducer: append)
    error_type: str | None                             # syntax/import/test_fail/runtime/logic/none
    error_message: str | None                          # 에러 원문 (truncate 500자)
    diagnosis: str | None                              # error_analyzer가 작성한 진단
    rag_context: str | None                            # RAG로 검색된 참고 코드
    iteration: int                                     # 현재 반복 횟수
    max_iterations: int                                # 최대 반복 (기본 5)
    done: bool                                         # 완료 여부
```

**추가 필드:**
- `plan_approved` — Human-in-the-loop에서 사용자 승인 추적
- `rag_context` — RAG 검색 결과를 coder에게 전달

---

## 2. LLM 설정 (`llm_config.py`)

```python
from langchain_openai import ChatOpenAI

def get_llm():
    return ChatOpenAI(
        base_url="http://localhost:8000/v1",   # vLLM 서버
        api_key="not-needed",                   # 로컬이므로 더미값
        model="local-model",
        temperature=0,
    )
```

- `.env` 파일에서 `BASE_URL`, `MODEL_NAME` 읽도록 설정 가능
- **구조화 출력 없음** — `with_structured_output()` 사용하지 않음
- 모든 노드가 plain text 응답만 받음

---

## 3. 출력 파서 (`parsers.py`)

LLM의 plain text 응답에서 코드블록을 추출하는 유틸리티.

```python
import re

def extract_code_block(text: str) -> str:
    """```python ... ``` 또는 ``` ... ``` 에서 코드 추출"""
    match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 코드블록 없으면 전체 텍스트를 코드로 간주
    return text.strip()

def extract_filename(text: str) -> str:
    """FILENAME: xxx.py 패턴에서 파일명 추출"""
    match = re.search(r'FILENAME:\s*(\S+\.py)', text)
    if match:
        return match.group(1)
    return "solution.py"  # 기본값
```

- 로컬 LLM이 코드블록 마크다운을 잘 못 쓸 수 있으므로 **폴백** 포함
- 각 노드에서 이 함수를 호출해 LLM 출력을 파싱

---

## 4. 도구(Tool) 설계 (`tools/`)

이전 계획과 동일. 6개 도구.

### `tools/file_ops.py`
- `write_file(filename, content, workspace_dir)` — 파일 생성/덮어쓰기
- `read_file(filename, workspace_dir)` — 파일 읽기
- `apply_patch(content, old_str, new_str)` — 부분 수정 (replace 1회)
- `list_files(workspace_dir)` — 파일 목록

### `tools/exec_ops.py`
- `run_command(cmd, cwd, timeout=30)` → `(stdout, stderr, returncode)`
- 위험 명령어 블랙리스트 내장

### `tools/plan_ops.py`
- `write_plan_md(text, workspace_dir)` — plan.md 저장

---

## 5. 그래프 노드 (9개) — Local LLM 최적화 + 확장 기능

```
[goal_analyzer] → [rag_retriever] → [planner] → interrupt() → [coder] → [test_writer] → [tester]
                                        ↑          사용자승인                                  │
                                        │                                                 done=True → [summarizer] → [END]
                                        │                                                     │
                                        │                                                  done=False
                                        │                                                     ↓
                                        │                                               [error_analyzer]
                                        │                                                     ↓
                                        │                                                  [fixer]
                                        │                                                     │
                                        │                                 syntax/import ──→ [tester]
                                        │                                                     │
                                        └──────────────── test_fail/runtime/logic ────────────┘
```

### 핵심 원칙: **노드당 LLM에게 하나만 시키기**

| 노드 | LLM에게 시키는 것 (단 하나) | LLM 호출 |
|---|---|---|
| goal_analyzer | "이 목표의 요구사항을 번호 목록으로 나열해" | ✅ |
| rag_retriever | 기존 코드베이스에서 관련 코드 검색 | ❌ (벡터 검색만) |
| planner | "이 요구사항으로 구현 계획을 단계별로 써" | ✅ |
| *(interrupt)* | 사용자에게 계획 승인 요청 | ❌ (Human-in-the-loop) |
| coder | "이 계획대로 Python 코드를 작성해" | ✅ |
| test_writer | "이 코드를 테스트하는 pytest 코드를 작성해" | ✅ |
| tester | subprocess 실행 + 에러 분류 | ❌ |
| error_analyzer | "이 에러의 원인을 한 문장으로 말해" | ✅ |
| fixer | "이 진단을 바탕으로 코드를 수정해" | ✅ |
| summarizer | "결과를 요약하고 Store에 학습 내용 저장" | ✅ |

### 노드별 상세

#### ① goal_analyzer (1회만 실행)
- **읽기:** `goal`
- **쓰기:** `plan` (요구사항 목록), `test_command`, `logs`
- **프롬프트 (짧고 단순하게):**
  ```
  사용자의 목표: {goal}

  위 목표를 구현하기 위한 요구사항을 번호 목록으로 나열하세요.
  마지막 줄에 TEST_COMMAND: <테스트 실행 명령어>를 적으세요.
  ```
- **파싱:** `TEST_COMMAND:` 줄에서 test_command 추출, 나머지는 plan에 저장

#### ② rag_retriever (LLM 호출 없음)
- **읽기:** `goal`, `plan`
- **쓰기:** `rag_context`, `logs`
- **동작:**
  1. 기존 코드베이스 디렉토리(설정 가능)에서 `.py` 파일 수집
  2. 텍스트 청킹 → FAISS 벡터 저장소에 인덱싱
  3. `goal` + `plan`을 쿼리로 유사도 검색 (top-k=3)
  4. 검색된 코드 조각을 `rag_context`에 저장
- **LLM 호출 없음** — 임베딩 모델만 사용 (HuggingFace sentence-transformers 로컬)
- **코드베이스 없을 시:** `rag_context = None`으로 스킵

#### ③ planner
- **읽기:** `goal`, `plan` (요구사항), `rag_context`, `error_type`, `diagnosis`, `iteration`
- **쓰기:** `plan`, `logs`
- **프롬프트:**
  ```
  목표: {goal}
  요구사항: {plan}
  [RAG 있을 시] 참고 코드: {rag_context}
  [에러 시] 이전 에러: {error_type} - {diagnosis}

  위 요구사항을 구현할 Python 코드의 계획을 작성하세요.
  어떤 함수를 만들지, 각 함수가 무엇을 하는지 적으세요.
  ```
- **도구:** `write_plan_md()`로 workspace/plan.md 저장
- **interrupt() 후:** 사용자가 계획을 확인하고 승인/수정 가능 (Human-in-the-loop)

#### ④ coder
- **읽기:** `goal`, `plan`, `files`, `rag_context`
- **쓰기:** `files`, `logs`
- **프롬프트:**
  ```
  계획:
  {plan}
  [RAG 있을 시] 참고 코드: {rag_context}

  위 계획대로 Python 코드를 작성하세요.
  파일 하나만 작성하세요.
  FILENAME: <파일명>으로 시작하고, 코드블록 안에 코드를 넣으세요.
  ```
- **파싱:** `extract_filename()` + `extract_code_block()`
- **도구:** `write_file()`로 저장

#### ④ test_writer (새 노드 — coder에서 분리)
- **읽기:** `goal`, `files`
- **쓰기:** `test_code`, `files`, `logs`
- **프롬프트:**
  ```
  다음 코드를 테스트하는 pytest 코드를 작성하세요.
  테스트는 최소 2개 이상 작성하세요.

  코드:
  {files의 메인 파일 내용}
  ```
- **파싱:** `extract_code_block()`
- **도구:** `write_file("test_solution.py", ...)`로 저장
- **이 노드의 의미:** coder에게 "코드 쓰고 테스트도 써" 대신 각각 하나씩만 시킴

#### ⑤ tester (LLM 호출 없음)
- **읽기:** `test_command`
- **쓰기:** `error_type`, `error_message`, `done`, `logs`
- **동작:** `run_command(test_command)` 실행 → 에러 분류 (순수 Python)
- **에러 분류 로직:**
  ```python
  def classify_error(output: str, returncode: int) -> str:
      if returncode == 0: return "none"
      if "SyntaxError" in output: return "syntax"
      if "ModuleNotFoundError" in output or "ImportError" in output: return "import"
      if "AssertionError" in output or "FAILED" in output: return "test_fail"
      if "Traceback" in output: return "runtime"
      return "logic"
  ```

#### ⑥ error_analyzer (새 노드 — fixer에서 분리)
- **읽기:** `error_type`, `error_message`, `files`
- **쓰기:** `diagnosis`, `logs`
- **프롬프트 (매우 단순):**
  ```
  에러 종류: {error_type}
  에러 메시지:
  {error_message[:500]}

  코드:
  {관련 파일 내용}

  이 에러의 원인을 한 문장으로 설명하세요.
  ```
- **파싱:** LLM 응답 전체를 `diagnosis`에 저장 (추가 파싱 불필요)
- **이 노드의 의미:** "에러 진단"과 "코드 수정"을 분리 → 각각 더 단순한 작업

#### ⑦ fixer
- **읽기:** `error_type`, `diagnosis`, `files`, `iteration`, `max_iterations`
- **쓰기:** `files`, `iteration` (+1), `logs`
- **프롬프트:**
  ```
  다음 코드에 에러가 있습니다.
  에러 원인: {diagnosis}

  코드:
  {에러 관련 파일 내용}

  수정된 전체 코드를 코드블록 안에 작성하세요.
  ```
- **파싱:** `extract_code_block()`
- **도구:** `write_file()`로 수정된 코드 저장
- **iteration += 1** 처리

#### ⑩ summarizer (완료 후 1회 실행)
- **읽기:** `goal`, `files`, `logs`, `iteration`
- **쓰기:** `logs`
- **동작:**
  1. LLM에게 "이번 작업에서 배운 점을 한 줄로 요약해" 요청
  2. 결과를 LangGraph Store에 저장 (장기 메모리)
  3. 저장 형식: `{"goal_summary": ..., "lesson": ..., "error_patterns": ..., "iteration_count": ...}`
- **프롬프트:**
  ```
  목표: {goal}
  반복 횟수: {iteration}
  에러 로그: {logs에서 에러 관련만 추출}

  이번 작업에서 배운 점을 한 줄로 요약하세요.
  자주 발생한 에러 패턴이 있으면 적으세요.
  ```
- **Store 활용:** 다음 프로젝트의 planner/coder가 Store에서 과거 교훈을 검색하여 참고

---

## 6. 조건부 라우팅

```python
# tester 이후
def route_after_tester(state) -> str:
    if state.get("done"):
        return "summarizer"     # 완료 → 학습 요약 후 종료
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "summarizer"     # 최대 반복 도달 → 요약 후 종료
    return "error_analyzer"

# fixer 이후 — 에러 종류별 분기
def route_after_fixer(state) -> str:
    error = state.get("error_type", "")
    if error in ("syntax", "import"):
        return "tester"         # 단순 에러 → 바로 재테스트
    return "planner"            # 복잡한 에러 → 재계획
```

**graph.py 연결:**
```python
g.add_edge(START, "goal_analyzer")
g.add_edge("goal_analyzer", "rag_retriever")
g.add_edge("rag_retriever", "planner")
# planner 이후 interrupt → 사용자 승인 → coder
g.add_edge("planner", "coder")
g.add_edge("coder", "test_writer")
g.add_edge("test_writer", "tester")
g.add_edge("error_analyzer", "fixer")
g.add_edge("summarizer", END)
g.add_conditional_edges("tester", route_after_tester, {
    "error_analyzer": "error_analyzer",
    "summarizer": "summarizer",
})
g.add_conditional_edges("fixer", route_after_fixer, {
    "tester": "tester",
    "planner": "planner",
})
```

**그래프 흐름:**
```
[goal_analyzer] → [rag_retriever] → [planner] →(interrupt)→ [coder] → [test_writer] → [tester]
                                        ↑                                                  │
                                        │                                           ┌── done ──→ [summarizer] → [END]
                                        │                                           │
                                        │                                        not done
                                        │                                           ↓
                                        │                                     [error_analyzer]
                                        │                                           ↓
                                        │                                        [fixer]
                                        │                                           │
                                        │                           syntax/import → [tester]
                                        │                                           │
                                        └────────── test_fail/runtime/logic ────────┘
```

**라우팅 요약:**
| 상황 | 경로 | 이유 |
|---|---|---|
| 성공 또는 max_iterations | tester → **summarizer** → END | 학습 내용 Store에 저장 후 종료 |
| syntax/import 에러 | fixer → **tester** (직행) | 코드 수정만으로 해결 가능 |
| test_fail/runtime/logic | fixer → **planner** (interrupt 포함) → coder → ... | 로직 문제이므로 재계획 + 사용자 확인 |

---

## 7. 프롬프트 전략 — Local LLM 최적화

**원칙:**
- 한 프롬프트에 지시사항 **3개 이하**
- 출력 형식은 **코드블록** 하나만 요구
- 역할 설명 최소화 (토큰 절약)
- 한국어/영어 혼용 가능 (LLM 지원 언어에 따라)

| 파일 | 지시사항 수 | 출력 형식 |
|---|---|---|
| `analyzer.txt` | 2개 (목록 나열 + TEST_COMMAND) | 번호 목록 + 마지막 줄 |
| `planner.txt` | 2개 (함수 목록 + 역할 설명) | 자유 텍스트 |
| `coder.txt` | 2개 (FILENAME + 코드블록) | FILENAME: + ```python``` |
| `test_writer.txt` | 2개 (pytest 작성 + 2개 이상) | ```python``` |
| `error_analyzer.txt` | 1개 (원인 한 문장) | 자유 텍스트 |
| `fixer.txt` | 2개 (수정 코드 + 코드블록) | ```python``` |

---

## 8. 확장 기능 상세 설계

### 8-1. Human-in-the-loop (`interrupt()`)

planner 노드 이후에 `interrupt()`로 그래프 실행을 일시 중단하여 사용자에게 계획 승인을 받음.

**구현:**
```python
from langgraph.types import interrupt

def planner(state: AgentState) -> dict:
    # ... LLM으로 계획 생성 ...
    plan_text = llm_result.content
    write_plan_md(plan_text)

    # 사용자에게 계획 승인 요청
    approval = interrupt({
        "plan": plan_text,
        "question": "이 계획을 승인하시겠습니까? (승인/수정/거부)"
    })

    # 사용자 응답에 따라 처리
    if approval.get("action") == "modify":
        plan_text = approval.get("modified_plan", plan_text)

    return {"plan": plan_text, "plan_approved": True, "logs": [...]}
```

**사용자 인터페이스 (main.py):**
```python
# graph.stream()으로 실행 → interrupt 발생 시 사용자 입력 받기
for event in graph.stream(state, config=config):
    if '__interrupt__' in event:
        print("=== 계획 검토 ===")
        print(event['__interrupt__']['plan'])
        user_input = input("승인(y) / 수정(m) / 거부(n): ")
        # Command.resume()으로 그래프 재개
```

**task 분할 효과:** planner가 계획만 세우고, 사용자가 검증하므로 LLM이 잘못된 방향으로 가는 것을 조기 차단.

### 8-2. SQLite Checkpointer

그래프 실행 중간 상태를 SQLite에 저장하여 중단 후 재개 가능.

**구현:**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# graph.py에서
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=checkpointer)

# main.py에서 — thread_id로 세션 관리
config = {"configurable": {"thread_id": "session-001"}}
result = graph.invoke(state, config=config)

# 재개 시 — 같은 thread_id로 이전 상태에서 이어감
result = graph.invoke(None, config=config)  # None으로 호출하면 마지막 상태에서 재개
```

**파일:** `checkpointer.py` — SqliteSaver 초기화 + thread_id 관리
**DB 위치:** `coding_agent/checkpoints.db`

**interrupt()와 연동:** Checkpointer가 있어야 interrupt() 후 재개가 가능. 둘은 항상 함께 사용.

### 8-3. 멀티 에이전트 (서브그래프)

coder 노드를 **backend_coder**와 **frontend_coder** 서브에이전트로 분리. 목표에 따라 적절한 에이전트를 선택.

**구현 — 서브그래프 방식:**
```python
# nodes/coder.py — 라우터 역할
def route_to_coder(state) -> str:
    """goal에 'frontend', 'html', 'css', 'react' 등이 있으면 frontend_coder로"""
    goal_lower = state["goal"].lower()
    frontend_keywords = ["frontend", "html", "css", "react", "ui", "웹페이지", "화면"]
    if any(kw in goal_lower for kw in frontend_keywords):
        return "frontend_coder"
    return "backend_coder"
```

**각 서브에이전트의 프롬프트 차이:**
| 에이전트 | 프롬프트 핵심 | 파일 |
|---|---|---|
| backend_coder | "Python 백엔드 코드를 작성하세요" | `prompts/backend_coder.txt` |
| frontend_coder | "HTML/CSS/JS 프론트엔드 코드를 작성하세요" | `prompts/frontend_coder.txt` |

**task 분할:** 각 서브에이전트는 자기 영역의 코드만 작성 → LLM 부담 감소.

**graph.py에 적용:**
```python
g.add_conditional_edges("planner_approved", route_to_coder, {
    "backend_coder": "backend_coder",
    "frontend_coder": "frontend_coder",
})
g.add_edge("backend_coder", "test_writer")
g.add_edge("frontend_coder", "test_writer")
```

### 8-4. RAG 연동 (`rag_retriever` 노드)

기존 코드베이스를 벡터 검색하여 coder에게 참고 자료 제공. LLM 호출 없이 임베딩 모델만 사용.

**구현:**
```python
# nodes/rag_retriever.py
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

def rag_retriever(state: AgentState) -> dict:
    codebase_dir = os.getenv("CODEBASE_DIR", "")
    if not codebase_dir or not Path(codebase_dir).exists():
        return {"rag_context": None, "logs": [{"node": "rag_retriever", "status": "skipped"}]}

    # 1. .py 파일 수집
    docs = load_py_files(codebase_dir)

    # 2. 청킹 (함수/클래스 단위)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    # 3. 로컬 임베딩 모델로 벡터화
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # 4. 검색 (top-3)
    query = f"{state['goal']} {state['plan']}"
    results = vectorstore.similarity_search(query, k=3)

    context = "\n---\n".join([doc.page_content for doc in results])
    return {
        "rag_context": context[:2000],  # 2000자 제한
        "logs": [{"node": "rag_retriever", "chunks_found": len(results)}]
    }
```

**task 분할:** 검색만 수행 (LLM 호출 0회). 결과는 planner와 coder가 각자 프롬프트에서 참고.

**설정:** `.env`에 `CODEBASE_DIR=/path/to/existing/project` 지정. 없으면 자동 스킵.

### 8-5. Store 기반 장기 메모리

이전 프로젝트에서 배운 패턴(자주 나는 에러, 선호 라이브러리)을 LangGraph Store에 저장하여 다음 프로젝트에서 참고.

**구현 — InMemoryStore (→ 추후 SQLite 기반으로 교체 가능):**
```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# summarizer 노드에서 저장
def summarizer(state: AgentState, config, *, store) -> dict:
    # LLM에게 학습 내용 요약 요청
    lesson = llm.invoke("이번 작업에서 배운 점을 한 줄로 요약...")

    # Store에 저장 (namespace: "lessons")
    store.put(
        namespace=("lessons",),
        key=f"lesson_{datetime.now().isoformat()}",
        value={
            "goal": state["goal"],
            "lesson": lesson.content,
            "iterations": state["iteration"],
            "error_patterns": extract_error_patterns(state["logs"]),
        }
    )
    return {"logs": [{"node": "summarizer", "lesson": lesson.content}]}

# planner 노드에서 검색
def planner(state: AgentState, config, *, store) -> dict:
    # 과거 교훈 검색
    past_lessons = store.search(namespace=("lessons",), query=state["goal"], limit=3)
    lesson_text = "\n".join([item.value["lesson"] for item in past_lessons])
    # planner 프롬프트에 포함
    ...
```

**Store 접근 패턴:**
| 노드 | Store 동작 | 용도 |
|---|---|---|
| planner | `store.search()` | 과거 교훈을 계획에 반영 |
| coder | `store.search()` | 자주 쓴 패턴/라이브러리 참고 |
| summarizer | `store.put()` | 이번 작업 학습 내용 저장 |

**graph.py에서 Store 연결:**
```python
store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)
```

---

## 9. 안전장치

| 항목 | 방법 |
|---|---|
| 무한루프 | `max_iterations` (기본 5) |
| 명령 실행 | subprocess 타임아웃 30초 + 블랙리스트 |
| 에러 메시지 | 500자로 truncate (LLM 컨텍스트 절약) |
| 파일 내용 | 노드에 전달할 때 3000자로 truncate |
| workspace 격리 | 모든 파일 I/O는 workspace/ 하위로 제한 |
| Windows 호환 | `python -m pytest` 사용 |
| workspace 보장 | main.py에서 `Path("workspace").mkdir(exist_ok=True)` |

### requirements.txt
```
langgraph>=1.0.0
langchain-openai>=1.0.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langchain-huggingface>=0.1.0
faiss-cpu>=1.7.0
sentence-transformers>=2.0.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

---

## 9. 파일 구조

```
coding_agent/
├── main.py                  # CLI 진입점 (interrupt 처리 + stream 출력)
├── graph.py                 # StateGraph 정의 + 라우팅 + compile (checkpointer + store)
├── state.py                 # AgentState TypedDict
├── llm_config.py            # get_llm() + load_prompt()
├── parsers.py               # extract_code_block(), extract_filename()
├── checkpointer.py          # SqliteSaver 초기화 + thread_id 관리
├── nodes/
│   ├── __init__.py
│   ├── goal_analyzer.py     # ① 요구사항 추출
│   ├── rag_retriever.py     # ② RAG 벡터 검색 (LLM 호출 없음)
│   ├── planner.py           # ③ 구현 계획 + interrupt()
│   ├── coder.py             # ④ 코드 생성 (backend/frontend 라우터)
│   ├── backend_coder.py     # ④-a 백엔드 코드 생성
│   ├── frontend_coder.py    # ④-b 프론트엔드 코드 생성
│   ├── test_writer.py       # ⑤ 테스트 코드 생성
│   ├── tester.py            # ⑥ 실행 + 에러 분류
│   ├── error_analyzer.py    # ⑦ 에러 진단
│   ├── fixer.py             # ⑧ 코드 수정
│   └── summarizer.py        # ⑨ 학습 요약 + Store 저장
├── tools/
│   ├── __init__.py
│   ├── file_ops.py
│   ├── plan_ops.py
│   └── exec_ops.py
├── prompts/
│   ├── analyzer.txt
│   ├── planner.txt
│   ├── backend_coder.txt
│   ├── frontend_coder.txt
│   ├── test_writer.txt
│   ├── error_analyzer.txt
│   ├── fixer.txt
│   └── summarizer.txt
├── workspace/               # 에이전트가 코드 생성하는 디렉토리
├── tests/
│   ├── test_tools.py
│   ├── test_parsers.py
│   ├── test_classifier.py
│   └── test_graph.py
├── checkpoints.db           # SQLite 체크포인트 (자동 생성)
├── .env                     # BASE_URL, MODEL_NAME, CODEBASE_DIR 설정
└── requirements.txt
```

---

## 11. 구현 순서 (3단계: 코어 → 그래프 → 확장)

### Phase A: 코어 모듈 (도구 + 파서 + 기반)
| 단계 | 파일 | 확인 기준 |
|---|---|---|
| **A1** | `state.py` | import 성공 |
| **A2** | `llm_config.py`, `parsers.py` | import 성공 |
| **A3** | `tools/` 전체 (3파일) | `test_tools.py` 통과 |
| **A4** | `tests/test_parsers.py` | 코드블록 파싱 테스트 통과 |
| **A5** | `prompts/` 전체 (8파일) | 파일 존재 확인 |
| **A6** | `.env`, `requirements.txt` | 설정 파일 생성 |

### Phase B: 노드 구현 (각 노드 독립 테스트)
| 단계 | 파일 | 확인 기준 |
|---|---|---|
| **B1** | `nodes/goal_analyzer.py` | 목표 → 요구사항 목록 출력 |
| **B2** | `nodes/planner.py` (interrupt 없이 먼저) | 요구사항 → 계획 텍스트 출력 |
| **B3** | `nodes/backend_coder.py` | 계획 → 코드 파일 1개 생성 |
| **B4** | `nodes/frontend_coder.py` | 계획 → HTML/CSS/JS 파일 생성 |
| **B5** | `nodes/coder.py` (라우터) | goal 키워드 → 올바른 서브에이전트 선택 |
| **B6** | `nodes/test_writer.py` | 코드 → 테스트 파일 생성 |
| **B7** | `nodes/tester.py` + `tests/test_classifier.py` | 에러 분류 테스트 통과 |
| **B8** | `nodes/error_analyzer.py` | 에러 → 진단 한 문장 |
| **B9** | `nodes/fixer.py` | 진단 + 코드 → 수정 코드 출력 |

### Phase C: 그래프 조립 + 확장 기능
| 단계 | 파일 | 확인 기준 |
|---|---|---|
| **C1** | `graph.py` (기본 — checkpointer/store 없이) | 노드 연결 + compile 성공 |
| **C2** | `main.py` + 기본 E2E | 간단한 목표로 end-to-end 동작 |
| **C3** | `checkpointer.py` + graph.py에 연결 | 중단 후 재개 동작 확인 |
| **C4** | `planner.py`에 `interrupt()` 추가 | 계획 승인 후 진행 확인 |
| **C5** | `nodes/rag_retriever.py` | CODEBASE_DIR 설정 시 검색 결과 반환, 미설정 시 스킵 |
| **C6** | `nodes/summarizer.py` + Store 연결 | 완료 후 Store에 학습 내용 저장 |
| **C7** | planner/coder에 Store 검색 연동 | 과거 교훈이 프롬프트에 포함되는지 확인 |
| **C8** | `tests/test_graph.py` | 통합 테스트 통과 |

---

## 12. 검증 방법

1. **단위 테스트:** `python -m pytest tests/test_tools.py tests/test_parsers.py tests/test_classifier.py -v`
2. **기본 E2E:** `python main.py "1부터 10까지 합을 구하는 함수를 만들어"` → workspace/에 코드 + 테스트 생성 + 통과
3. **interrupt 테스트:** 실행 → 계획 출력 → 사용자 승인 → 코드 생성 진행 확인
4. **checkpointer 테스트:** 실행 중 Ctrl+C → 재실행 시 이전 상태에서 이어가는지 확인
5. **RAG 테스트:** `CODEBASE_DIR` 설정 후 실행 → coder 프롬프트에 참고 코드 포함 확인
6. **Store 테스트:** 2번 연속 실행 → 두 번째 실행에서 첫 번째 교훈이 planner에 반영되는지 확인
7. **루프 테스트:** 의도적으로 어려운 목표 → fix 루프 + 에러 종류별 라우팅 동작 확인
8. **멀티에이전트 테스트:** "웹페이지 만들어" → frontend_coder 선택 확인
9. **안전장치:** max_iterations=2로 제한 후 summarizer → 종료 확인
