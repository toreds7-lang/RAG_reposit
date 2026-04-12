# LangGraph 기반 에이전트형 파이썬 코딩 시스템 — 구현 문서

## 1. 프로젝트 개요

자연어로 목표를 입력하면 **계획 → 코딩 → 테스트 → 수정** 루프를 자동으로 반복하여 동작하는 코드를 생성하는 자율형 코딩 에이전트입니다.

### 핵심 제약 사항
- **Local LLM** 사용 (OpenAI 호환 API, vLLM localhost:8000)
- LLM 능력이 제한적이므로 **노드당 하나의 단순한 작업**만 부여
- 구조화 출력(JSON/Pydantic) 사용 불가 → **plain text + 코드블록 파싱** 방식 채택
- 프롬프트당 지시사항 **3개 이하**로 제한

---

## 2. 시스템 아키텍처

### 2.1 전체 그래프 흐름

```
[goal_analyzer] → [rag_retriever] → [planner] →(interrupt)→ [coder] → [test_writer] → [tester]
                                        ↑          사용자승인                                  │
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

### 2.2 노드 역할 요약

| 노드 | 역할 (단 하나) | LLM 호출 |
|---|---|---|
| `goal_analyzer` | 목표 → 요구사항 번호 목록 + TEST_COMMAND 추출 | ✅ |
| `rag_retriever` | 기존 코드베이스에서 유사 코드 벡터 검색 | ❌ (임베딩만) |
| `planner` | 요구사항 → 단계별 구현 계획 작성 | ✅ |
| `backend_coder` | 계획 → Python 백엔드 코드 1개 파일 생성 | ✅ |
| `frontend_coder` | 계획 → HTML/CSS/JS 프론트엔드 코드 생성 | ✅ |
| `test_writer` | 생성된 코드 → pytest 테스트 코드 작성 | ✅ |
| `tester` | subprocess로 테스트 실행 + 에러 분류 | ❌ |
| `error_analyzer` | 에러 메시지 → 원인 한 문장 진단 | ✅ |
| `fixer` | 진단 기반 코드 수정 | ✅ |
| `summarizer` | 작업 결과 요약 + Store에 학습 내용 저장 | ✅ |

### 2.3 조건부 라우팅

| 분기 지점 | 조건 | 대상 | 이유 |
|---|---|---|---|
| `planner` 이후 | goal에 frontend 키워드 포함 | `frontend_coder` | 프론트엔드 전용 프롬프트 |
| `planner` 이후 | 그 외 | `backend_coder` | 백엔드 전용 프롬프트 |
| `tester` 이후 | `done=True` 또는 `iteration >= max_iterations` | `summarizer` | 성공 또는 반복 한도 |
| `tester` 이후 | 에러 발생 | `error_analyzer` | 에러 진단 필요 |
| `fixer` 이후 | `syntax` / `import` 에러 | `tester` | 단순 에러 → 바로 재테스트 |
| `fixer` 이후 | `test_fail` / `runtime` / `logic` 에러 | `planner` | 로직 문제 → 재계획 |

---

## 3. 파일 구조

```
coding_agent/
├── main.py                  # CLI 진입점 (interrupt 처리 + stream 출력)
├── graph.py                 # StateGraph 정의 + 라우팅 + compile
├── state.py                 # AgentState TypedDict (공유 상태)
├── llm_config.py            # get_llm() + load_prompt()
├── parsers.py               # extract_code_block(), extract_filename()
├── checkpointer.py          # MemorySaver 초기화 + thread_id 관리
├── nodes/
│   ├── goal_analyzer.py     # ① 요구사항 추출
│   ├── rag_retriever.py     # ② RAG 벡터 검색
│   ├── planner.py           # ③ 구현 계획 + interrupt()
│   ├── coder.py             # ④ backend/frontend 라우터
│   ├── backend_coder.py     # ④-a 백엔드 코드 생성
│   ├── frontend_coder.py    # ④-b 프론트엔드 코드 생성
│   ├── test_writer.py       # ⑤ 테스트 코드 생성
│   ├── tester.py            # ⑥ 실행 + 에러 분류
│   ├── error_analyzer.py    # ⑦ 에러 진단
│   ├── fixer.py             # ⑧ 코드 수정
│   └── summarizer.py        # ⑨ 학습 요약 + Store 저장
├── tools/
│   ├── file_ops.py          # write_file, read_file, apply_patch, list_files
│   ├── exec_ops.py          # run_command (subprocess + 안전장치)
│   └── plan_ops.py          # write_plan_md
├── prompts/                 # 노드별 시스템 프롬프트 (8개)
│   ├── analyzer.txt
│   ├── planner.txt
│   ├── backend_coder.txt
│   ├── frontend_coder.txt
│   ├── test_writer.txt
│   ├── error_analyzer.txt
│   ├── fixer.txt
│   └── summarizer.txt
├── tests/                   # 단위 + 통합 테스트 (42개)
│   ├── test_tools.py        # 도구 테스트 (19개)
│   ├── test_parsers.py      # 파서 테스트 (8개)
│   ├── test_classifier.py   # 에러 분류 테스트 (9개)
│   └── test_graph.py        # 그래프 통합 테스트 (17개)
├── workspace/               # 에이전트가 코드를 생성하는 디렉토리
├── .env                     # 환경 설정
└── requirements.txt         # 의존성
```

---

## 4. 핵심 모듈 상세

### 4.1 State 설계 (`state.py`)

LangGraph `TypedDict` 기반의 공유 상태. 모든 노드가 이 상태를 읽고 쓰며 그래프를 통해 데이터가 흐릅니다.

```python
class AgentState(TypedDict):
    goal: str                                          # 사용자 원본 목표
    plan: str                                          # 현재 계획 텍스트
    plan_approved: bool                                # 사용자 승인 여부
    files: Annotated[dict[str, str], merge_dicts]      # 파일명→내용 (병합 reducer)
    test_code: str                                     # 테스트 파일 내용
    test_command: str                                  # 실행할 테스트 명령어
    logs: Annotated[list[dict], operator.add]           # 반복 기록 (append reducer)
    error_type: str | None                             # 에러 분류
    error_message: str | None                          # 에러 원문 (500자 제한)
    diagnosis: str | None                              # 에러 진단
    rag_context: str | None                            # RAG 검색 결과
    iteration: int                                     # 현재 반복 횟수
    max_iterations: int                                # 최대 반복 (기본 5)
    done: bool                                         # 완료 여부
```

**Reducer 설계:**
- `files` → `merge_dicts`: 새 파일이 추가되면 기존 파일과 병합 (덮어쓰기 가능)
- `logs` → `operator.add`: 각 노드의 로그가 누적 (append)

### 4.2 LLM 설정 (`llm_config.py`)

```python
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
        api_key=os.getenv("API_KEY", "not-needed"),
        model=os.getenv("MODEL_NAME", "local-model"),
        temperature=0,
    )
```

- `.env` 파일에서 `BASE_URL`, `API_KEY`, `MODEL_NAME` 읽기
- `temperature=0`으로 결정적 출력
- `with_structured_output()` **사용하지 않음** — 모든 응답은 plain text

### 4.3 출력 파서 (`parsers.py`)

LLM의 plain text 응답에서 코드와 메타데이터를 추출하는 유틸리티:

```python
def extract_code_block(text: str) -> str:
    """```python ... ``` 또는 ``` ... ``` 에서 코드 추출. 없으면 전체 텍스트 반환."""

def extract_filename(text: str) -> str:
    """FILENAME: xxx.py 패턴에서 파일명 추출. 없으면 'solution.py' 반환."""
```

- 로컬 LLM이 마크다운 형식을 지키지 않을 수 있으므로 **폴백 로직** 포함
- `extract_filename`은 `.py` 외에도 `.html`, `.js` 등 모든 확장자 지원

### 4.4 Checkpointer (`checkpointer.py`)

```python
def get_checkpointer():
    return MemorySaver()  # SqliteSaver로 교체 가능

def get_thread_config(thread_id: str | None = None) -> dict:
    if thread_id is None:
        thread_id = str(uuid.uuid4())[:8]
    return {"configurable": {"thread_id": thread_id}}
```

- `MemorySaver`로 그래프 상태를 메모리에 저장
- `thread_id`로 세션 관리 → interrupt() 후 재개 가능
- 추후 `SqliteSaver`로 교체하면 프로세스 재시작 후에도 상태 유지

---

## 5. 노드 구현 상세

### 5.1 goal_analyzer — 목표 분석

**파일:** `nodes/goal_analyzer.py`

사용자의 자연어 목표를 구조화된 요구사항 목록으로 변환합니다.

- **입력:** `goal`
- **출력:** `plan` (요구사항 번호 목록), `test_command`, `logs`
- **프롬프트 전략:** "요구사항을 나열하고, 마지막 줄에 TEST_COMMAND: 을 쓰세요"
- **파싱:** `TEST_COMMAND:` 패턴으로 테스트 명령어 추출, 없으면 `python -m pytest` 기본값

### 5.2 rag_retriever — RAG 벡터 검색

**파일:** `nodes/rag_retriever.py`

기존 코드베이스에서 관련 코드를 검색하여 coder에게 참고 자료를 제공합니다. **LLM 호출 없음**.

- **입력:** `goal`, `plan`
- **출력:** `rag_context` (검색된 코드 조각, 2000자 제한), `logs`
- **동작 과정:**
  1. `CODEBASE_DIR` 환경변수에서 대상 디렉토리 확인
  2. `DirectoryLoader`로 `.py` 파일 수집
  3. `RecursiveCharacterTextSplitter`로 500자 단위 청킹
  4. `OpenAIEmbeddings`로 벡터화 (동일한 BASE_URL 사용)
  5. `FAISS.from_documents()`로 벡터 저장소 생성
  6. `goal + plan`을 쿼리로 유사도 검색 (top-3)
- **스킵 조건:** `CODEBASE_DIR` 미설정 시 graceful skip
- **에러 처리:** ImportError, 일반 Exception 모두 catch → 로그에 기록 후 None 반환

### 5.3 planner — 구현 계획 수립

**파일:** `nodes/planner.py`

요구사항을 기반으로 단계별 구현 계획을 생성하고, 사용자 승인을 받습니다.

- **입력:** `goal`, `plan`, `rag_context`, `error_type`, `diagnosis`, `iteration`
- **출력:** `plan`, `plan_approved`, `logs`
- **Store 연동:** 과거 학습 내용(`lessons` 네임스페이스)을 검색하여 프롬프트에 포함
- **RAG 연동:** `rag_context`가 있으면 참고 코드로 프롬프트에 추가
- **에러 재진입:** 에러 타입과 진단이 있으면 프롬프트에 포함 (재계획 시)
- **Human-in-the-loop:** `interrupt()`로 실행 일시 중단 → 사용자 승인/수정/거부 처리
- **도구:** `write_plan_md()`로 `workspace/plan.md` 저장

### 5.4 coder — 멀티 에이전트 라우터

**파일:** `nodes/coder.py`

goal 키워드를 분석하여 적절한 코더 서브에이전트를 선택합니다. **LLM 호출 없음**.

```python
FRONTEND_KEYWORDS = [
    "frontend", "html", "css", "react", "ui",
    "웹페이지", "화면", "javascript", "web page"
]

def route_to_coder(state: dict) -> str:
    goal_lower = state.get("goal", "").lower()
    if any(kw in goal_lower for kw in FRONTEND_KEYWORDS):
        return "frontend_coder"
    return "backend_coder"
```

### 5.5 backend_coder / frontend_coder — 코드 생성

**파일:** `nodes/backend_coder.py`, `nodes/frontend_coder.py`

각각 Python 백엔드 코드와 HTML/CSS/JS 프론트엔드 코드를 생성합니다.

- **입력:** `goal`, `plan`, `rag_context`
- **출력:** `files` (파일명→내용 딕셔너리), `logs`
- **프롬프트 전략:** "FILENAME: 으로 시작, 코드블록 안에 코드 작성"
- **파싱:** `extract_filename()` + `extract_code_block()`
- **도구:** `write_file()`로 workspace에 저장

### 5.6 test_writer — 테스트 코드 생성

**파일:** `nodes/test_writer.py`

생성된 코드에 대한 pytest 테스트를 작성합니다.

- **입력:** `goal`, `files`
- **출력:** `test_code`, `files`, `logs`
- **프롬프트 전략:** "이 코드를 테스트하는 pytest 코드를 작성하세요. 최소 2개."
- **코드 제한:** 3000자까지만 프롬프트에 포함 (LLM 컨텍스트 절약)
- **파일명:** `test_` 접두사 + 메인 파일명 (예: `test_solution.py`)

### 5.7 tester — 테스트 실행 및 에러 분류

**파일:** `nodes/tester.py`

subprocess로 테스트를 실행하고 결과를 분류합니다. **LLM 호출 없음**.

- **입력:** `test_command`
- **출력:** `error_type`, `error_message`, `done`, `logs`
- **에러 분류 (우선순위):**
  ```
  returncode == 0  → "none" (성공)
  "SyntaxError"    → "syntax"
  "ModuleNotFound" → "import"
  "FAILED"         → "test_fail"
  "Traceback"      → "runtime"
  그 외            → "logic"
  ```
- **에러 메시지:** 500자로 truncate

### 5.8 error_analyzer — 에러 진단

**파일:** `nodes/error_analyzer.py`

에러의 근본 원인을 한 문장으로 진단합니다.

- **입력:** `error_type`, `error_message`, `files`
- **출력:** `diagnosis`, `logs`
- **프롬프트 전략:** "이 에러의 원인을 한 문장으로 설명하세요" (지시사항 1개)
- **파싱 불필요:** LLM 응답 전체가 진단 텍스트

### 5.9 fixer — 코드 수정

**파일:** `nodes/fixer.py`

진단 결과를 바탕으로 코드를 수정합니다.

- **입력:** `error_type`, `diagnosis`, `files`
- **출력:** `files` (수정된 코드), `iteration` (+1), `logs`
- **대상 파일 선택:** `test_`로 시작하지 않고 `.md`가 아닌 파일 우선
- **프롬프트 전략:** "수정된 전체 코드를 코드블록 안에 작성하세요"
- **코드 제한:** 3000자까지만 프롬프트에 포함
- **iteration 증가:** 매 수정마다 +1

### 5.10 summarizer — 학습 요약 및 Store 저장

**파일:** `nodes/summarizer.py`

작업 결과를 요약하고 장기 메모리(Store)에 학습 내용을 저장합니다.

- **입력:** `goal`, `files`, `logs`, `iteration`
- **출력:** `logs`
- **Store 저장 형식:**
  ```python
  {
      "goal": "사용자 목표",
      "lesson": "LLM이 요약한 학습 내용",
      "iterations": 3,
      "success": True,
      "error_patterns": ["syntax", "import"]
  }
  ```
- **네임스페이스:** `("lessons",)`
- **키 형식:** `lesson_YYYYMMDD_HHMMSS`

---

## 6. 도구(Tool) 구현

### 6.1 파일 도구 (`tools/file_ops.py`)

| 함수 | 역할 | 비고 |
|---|---|---|
| `write_file(filename, content, workspace_dir)` | 파일 생성/덮어쓰기 | 부모 디렉토리 자동 생성 |
| `read_file(filename, workspace_dir)` | 파일 읽기 | 없으면 에러 메시지 반환 |
| `apply_patch(content, old_str, new_str)` | 부분 수정 | 첫 번째 매치만 교체 |
| `list_files(workspace_dir)` | 파일 목록 | 재귀적 탐색, 상대 경로 |

### 6.2 실행 도구 (`tools/exec_ops.py`)

```python
def run_command(command, cwd="workspace", timeout=30):
```

- **타임아웃:** 30초 (설정 가능)
- **위험 명령어 차단:**
  ```
  rm -rf, rm -r /, mkfs, dd if=, chmod -R 777 /,
  curl | sh, wget | sh, format, del /s /q
  ```
- **반환값:** `(stdout, stderr, returncode)` 튜플

### 6.3 계획 도구 (`tools/plan_ops.py`)

```python
def write_plan_md(plan_text, workspace_dir="workspace"):
    write_file("plan.md", plan_text, workspace_dir)
```

---

## 7. 확장 기능

### 7.1 Human-in-the-loop (interrupt)

`planner` 노드에서 `langgraph.types.interrupt()`를 호출하여 그래프 실행을 일시 중단합니다.

**동작 흐름:**
1. Planner가 계획을 생성
2. `interrupt({"plan": plan_text, "question": "승인하시겠습니까?"})` 호출
3. 그래프 실행 일시 중단
4. `main.py`가 사용자 입력 대기
5. 사용자 응답에 따라:
   - **승인 (y):** `Command(resume={"action": "approve"})` → 계속 진행
   - **수정 (m):** 사용자가 수정된 계획 입력 → `Command(resume={"action": "modify", "modified_plan": ...})`
   - **거부 (n):** `Command(resume={"action": "reject"})` → 재계획

### 7.2 Checkpointer (상태 지속성)

`MemorySaver`로 그래프 실행 중간 상태를 저장합니다.

- **interrupt()와 필수 연동:** Checkpointer 없이는 interrupt() 후 재개 불가
- **thread_id:** UUID 기반 세션 식별자
- **교체 가능:** `SqliteSaver`로 변경하면 프로세스 재시작 후에도 상태 유지

### 7.3 멀티 에이전트 (backend / frontend)

goal 키워드 분석으로 적절한 코더를 자동 선택합니다.

- **프론트엔드 키워드:** `frontend`, `html`, `css`, `react`, `ui`, `웹페이지`, `화면`, `javascript`, `web page`
- **각 에이전트의 프롬프트가 다름:**
  - `backend_coder.txt` → Python 코드 생성 전용
  - `frontend_coder.txt` → HTML/CSS/JS 코드 생성 전용

### 7.4 RAG 연동 (벡터 검색)

FAISS + OpenAI 호환 임베딩 API로 기존 코드베이스를 검색합니다.

- **설정:** `.env`에 `CODEBASE_DIR=/path/to/project` 지정
- **임베딩:** OpenAI 호환 API 사용 (LLM과 동일한 BASE_URL)
- **청킹:** 500자 단위, 50자 오버랩
- **검색:** top-3 결과, 2000자 제한
- **활용:** `planner`와 `coder` 프롬프트에 참고 코드로 포함
- **미설정 시:** 자동 스킵 (에러 없음)

### 7.5 Store 기반 장기 메모리

`InMemoryStore`로 프로젝트 간 학습 내용을 공유합니다.

| 노드 | Store 동작 | 용도 |
|---|---|---|
| `planner` | `store.search()` | 과거 교훈을 계획에 반영 |
| `summarizer` | `store.put()` | 이번 작업 학습 내용 저장 |

- **저장:** `("lessons",)` 네임스페이스에 goal, lesson, error_patterns 저장
- **검색:** goal 텍스트로 유사도 검색 (limit=3)
- **모듈 수준 인스턴스:** `graph.py`에서 `_store = InMemoryStore()`로 프로세스 내 지속

---

## 8. 프롬프트 전략

### Local LLM 최적화 원칙

1. **지시사항 3개 이하** — 복잡한 지시는 LLM이 못 따름
2. **코드블록 하나만 요구** — 여러 파일 동시 생성 금지
3. **역할 설명 최소화** — 토큰 절약
4. **출력 형식 명시** — FILENAME: + 코드블록

### 프롬프트별 지시사항 수

| 프롬프트 파일 | 지시사항 수 | 출력 형식 |
|---|---|---|
| `analyzer.txt` | 2개 | 번호 목록 + TEST_COMMAND 줄 |
| `planner.txt` | 2개 | 자유 텍스트 |
| `backend_coder.txt` | 2개 | FILENAME: + 코드블록 |
| `frontend_coder.txt` | 2개 | FILENAME: + 코드블록 |
| `test_writer.txt` | 2개 | 코드블록 |
| `error_analyzer.txt` | 1개 | 자유 텍스트 (한 문장) |
| `fixer.txt` | 2개 | 코드블록 |
| `summarizer.txt` | 2개 | 자유 텍스트 |

---

## 9. 안전장치

| 항목 | 방법 | 설정값 |
|---|---|---|
| 무한 루프 방지 | `max_iterations` | 기본 5회 |
| 명령 실행 제한 | subprocess 타임아웃 | 30초 |
| 위험 명령 차단 | 블랙리스트 패턴 매칭 | rm -rf, mkfs 등 9개 |
| 에러 메시지 크기 | truncate | 500자 |
| 코드 내용 크기 | 프롬프트 삽입 시 truncate | 3000자 |
| 파일 I/O 격리 | workspace/ 디렉토리 한정 | — |
| RAG 결과 크기 | truncate | 2000자 |

---

## 10. 테스트

### 테스트 실행

```bash
python -m pytest tests/ -v
```

### 테스트 구성 (총 42개)

| 테스트 파일 | 테스트 수 | 대상 |
|---|---|---|
| `test_tools.py` | 19개 | file_ops (write/read/list/patch), exec_ops (run/block/timeout) |
| `test_parsers.py` | 8개 | extract_code_block, extract_filename |
| `test_classifier.py` | 9개 | classify_error (모든 에러 타입 + 우선순위) |
| `test_graph.py` | 17개 | 그래프 컴파일, 노드 존재, 라우팅 로직 |

### 주요 테스트 시나리오

- **파서 테스트:** 코드블록 있을 때/없을 때, Python 태그/없을 때, 멀티라인
- **에러 분류 테스트:** 각 에러 타입별 정확한 분류, 복합 에러 시 우선순위
- **라우팅 테스트:** backend/frontend 분기, 성공/에러/max_iterations 분기, 에러 타입별 fixer 라우팅
- **도구 테스트:** 파일 생성/읽기/패치, 중첩 디렉토리, 위험 명령 차단, 타임아웃

---

## 11. 실행 방법

### 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일 설정
BASE_URL=http://localhost:8000/v1    # vLLM 서버 주소
API_KEY=not-needed                    # 로컬 LLM이므로 더미값
MODEL_NAME=local-model                # 모델명
EMBEDDING_MODEL=local-model           # 임베딩 모델명
CODEBASE_DIR=                         # RAG 대상 디렉토리 (선택사항)
```

### 실행

```bash
# 기본 실행
python main.py "1부터 10까지 합을 구하는 함수를 만들어"

# 프론트엔드 코드 생성
python main.py "간단한 웹페이지를 만들어"
```

### 실행 흐름 예시

```
$ python main.py "피보나치 함수를 만들어"

[goal_analyzer] 요구사항 분석 중...
[rag_retriever] 코드베이스 검색 스킵 (CODEBASE_DIR 미설정)
[planner] 구현 계획 생성 중...

=== 계획 검토 ===
1. fibonacci(n) 함수 구현
2. 재귀 또는 반복문 방식
...

승인(y) / 수정(m) / 거부(n): y

[backend_coder] 코드 생성 중...
[test_writer] 테스트 작성 중...
[tester] 테스트 실행 중...

✅ 테스트 통과!

[summarizer] 학습 내용 저장 중...

=== 생성된 파일 ===
workspace/fibonacci.py
workspace/test_fibonacci.py
```

---

## 12. 구현 과정 요약

### Phase A: 코어 모듈 (기반 구축)

| 순서 | 구현 내용 | 파일 |
|---|---|---|
| A1 | 공유 상태(State) 정의 | `state.py` |
| A2 | LLM 설정 + 출력 파서 | `llm_config.py`, `parsers.py` |
| A3 | 도구 (파일/실행/계획) | `tools/*.py` |
| A4 | 프롬프트 템플릿 | `prompts/*.txt` |
| A5 | 환경 설정 | `.env`, `requirements.txt` |

### Phase B: 노드 구현 (독립적 구현)

| 순서 | 구현 내용 | 파일 |
|---|---|---|
| B1 | 목표 분석 | `nodes/goal_analyzer.py` |
| B2 | 계획 수립 (interrupt 포함) | `nodes/planner.py` |
| B3-B4 | 백엔드/프론트엔드 코더 | `nodes/backend_coder.py`, `nodes/frontend_coder.py` |
| B5 | 코더 라우터 | `nodes/coder.py` |
| B6 | 테스트 작성 | `nodes/test_writer.py` |
| B7 | 테스트 실행 + 에러 분류 | `nodes/tester.py` |
| B8 | 에러 진단 | `nodes/error_analyzer.py` |
| B9 | 코드 수정 | `nodes/fixer.py` |
| B10 | 학습 요약 | `nodes/summarizer.py` |

### Phase C: 그래프 조립 + 확장 기능

| 순서 | 구현 내용 | 파일 |
|---|---|---|
| C1 | 그래프 조립 (11노드 + 라우팅) | `graph.py` |
| C2 | CLI 진입점 (interrupt 처리) | `main.py` |
| C3 | Checkpointer 연동 | `checkpointer.py` |
| C4 | RAG 벡터 검색 | `nodes/rag_retriever.py` |
| C5 | Store 장기 메모리 | `nodes/summarizer.py`, `nodes/planner.py` |
| C6 | 테스트 작성 + 검증 | `tests/*.py` (42개 통과) |

---

## 13. 의존성

```
langgraph>=1.0.0           # 그래프 프레임워크
langchain-openai>=1.0.0    # OpenAI 호환 LLM/임베딩
langchain-core>=0.3.0      # LangChain 코어
langchain-community>=0.3.0 # 커뮤니티 도구 (FAISS, DirectoryLoader)
faiss-cpu>=1.7.0           # 벡터 유사도 검색
python-dotenv>=1.0.0       # .env 환경변수 로딩
pytest>=8.0.0              # 테스트 프레임워크
```

---

## 14. 설계 원칙 정리

1. **노드당 하나의 작업** — Local LLM의 제한된 능력에 맞춰 task를 최대한 분리
2. **Plain text 파싱** — 구조화 출력 대신 regex 기반 코드블록/파일명 추출
3. **에러 타입별 라우팅** — 단순 에러(syntax/import)는 빠른 수정, 복잡한 에러는 재계획
4. **Human-in-the-loop** — 계획 단계에서 사용자 검증으로 잘못된 방향 조기 차단
5. **Graceful degradation** — RAG/Store 미설정 시 에러 없이 스킵
6. **안전 우선** — 명령 블랙리스트, 타임아웃, 반복 제한, workspace 격리
