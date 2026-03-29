# MCP Agent Suite

LangGraph + LangChain-MCP-Adapters를 사용한 **MCP(Model Context Protocol) 에이전트 모음**입니다.
3개의 특화 에이전트와 이를 동적으로 결합하는 **통합 에이전트**로 구성됩니다.

---

## Architecture (구조)

```
사용자 질문
    │
    ▼
combined_agent.py
    │
    ▼
MultiServerMCPClient
    ├── context7          (npx @upstash/context7-mcp)
    │     └── 라이브러리/API 문서 조회
    ├── sequential_thinking  (npx @modelcontextprotocol/server-sequential-thinking)
    │     └── 단계별 복잡한 추론/분석
    └── filesystem        (npx @modelcontextprotocol/server-filesystem)
          └── 로컬 파일 읽기/쓰기/탐색
```

에이전트가 질문을 분석한 뒤 **필요한 MCP 서버의 도구만 자동으로 선택**하거나, 복합 질문은 여러 서버를 조합합니다.

---

## Prerequisites (사전 요구사항)

| 항목 | 버전 |
|---|---|
| Python | 3.11 이상 |
| Node.js | 18 이상 (npx 사용) |
| Anthropic API Key | 필수 |

---

## Installation (설치)

### 1. 패키지 설치

```bash
pip install langchain-mcp-adapters langchain-anthropic langgraph python-dotenv
```

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Environment Variables (환경변수)

| 변수명 | 설명 | 필수 여부 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 | 필수 |
| `OPENAI_API_KEY` | OpenAI API 키 (사용 시) | 선택 |
| `LANGSMITH_API_KEY` | LangSmith 트레이싱 키 | 선택 |
| `LANGSMITH_TRACING` | LangSmith 트레이싱 활성화 (`true`/`false`) | 선택 |
| `LANGSMITH_PROJECT` | LangSmith 프로젝트명 | 선택 |

---

## Agents (에이전트)

### 1. context7_agent.py — 라이브러리 문서 조회

특정 라이브러리나 프레임워크의 **최신 공식 문서를 실시간으로 조회**합니다.

```bash
python context7_agent.py
```

**예시 대화:**
```
You: LangGraph의 create_react_agent 사용법을 알려줘
Agent: [Tool: resolve-library-id]
       [Tool: get-library-docs]
       create_react_agent는 ReAct 패턴의 에이전트를 생성합니다...
```

---

### 2. sequential_thinking_agent.py — 단계별 추론

복잡한 문제를 **단계적으로 분해하여 분석·추론**합니다.

```bash
python sequential_thinking_agent.py
```

**예시 대화:**
```
You: REST API와 GraphQL의 장단점을 비교 분석해줘
Agent: [Tool: sequentialthinking]
       Step 1: REST API 특성 분석...
       Step 2: GraphQL 특성 분석...
       Step 3: 비교 및 결론...
```

---

### 3. filesystem_agent.py — 파일시스템 조작

지정한 디렉토리 내 **파일 읽기, 쓰기, 탐색, 검색**을 수행합니다.

```bash
# 현재 디렉토리만 허용
python filesystem_agent.py

# 특정 디렉토리 지정 (여러 개 가능)
python filesystem_agent.py /path/to/project /path/to/data
```

**예시 대화:**
```
You: 현재 폴더의 Python 파일 목록을 보여줘
Agent: [Tool: list_directory]
       현재 디렉토리에 있는 Python 파일:
       - combined_agent.py
       - context7_agent.py
       ...
```

---

### 4. combined_agent.py — 통합 동적 결합 에이전트 ★

**3개의 MCP 서버를 동시에 연결**하여 질문에 따라 적절한 도구를 자동으로 선택·조합합니다.

```bash
# 현재 디렉토리를 filesystem 서버의 허용 경로로 사용
python combined_agent.py

# 특정 디렉토리 지정
python combined_agent.py /path/to/project
```

---

## Dynamic Routing (동적 라우팅) — combined_agent.py 핵심 기능

### 단일 도구 선택 예시

**라이브러리 문서 질문 → context7 도구 자동 선택**
```
You: pandas의 DataFrame.groupby() 사용법을 알려줘

Agent: context7 도구로 pandas 공식 문서를 조회하겠습니다.
[Tool: context7__resolve-library-id]
[Tool: context7__get-library-docs]
pandas의 DataFrame.groupby()는 데이터를 그룹화하는 메서드입니다...
```

**파일 탐색 질문 → filesystem 도구 자동 선택**
```
You: 이 프로젝트의 Python 파일들을 모두 나열해줘

Agent: filesystem 도구로 디렉토리를 탐색하겠습니다.
[Tool: filesystem__list_directory]
현재 프로젝트의 Python 파일:
- combined_agent.py
- context7_agent.py
- filesystem_agent.py
- sequential_thinking_agent.py
```

**복잡한 분석 질문 → sequential_thinking 도구 자동 선택**
```
You: 마이크로서비스 아키텍처 도입 시 고려해야 할 사항을 분석해줘

Agent: sequential_thinking 도구로 단계별 분석하겠습니다.
[Tool: sequential_thinking__sequentialthinking]
Step 1: 현재 모놀리식 구조의 문제점 파악...
Step 2: 마이크로서비스 전환 시 이점...
Step 3: 도입 시 주요 과제 (네트워크 복잡도, 데이터 일관성)...
Step 4: 권장 전환 전략...
```

### 복합 도구 조합 예시

**파일 읽기 + 라이브러리 문서 조회**
```
You: requirements.txt를 읽고 각 라이브러리의 주요 기능을 설명해줘

Agent: filesystem로 파일을 읽고, context7로 각 라이브러리 문서를 조회합니다.
[Tool: filesystem__read_file]           ← requirements.txt 읽기
[Tool: context7__resolve-library-id]    ← 첫 번째 라이브러리
[Tool: context7__get-library-docs]
[Tool: context7__resolve-library-id]    ← 두 번째 라이브러리
[Tool: context7__get-library-docs]
...
```

**파일 읽기 + 단계별 분석**
```
You: combined_agent.py 코드를 읽고 개선 방안을 단계별로 분석해줘

Agent: 파일을 읽고 구조적으로 분석하겠습니다.
[Tool: filesystem__read_file]               ← 코드 읽기
[Tool: sequential_thinking__sequentialthinking]  ← 분석
Step 1: 현재 코드 구조 파악...
Step 2: 잠재적 문제점 식별...
Step 3: 개선 방안 제시...
```

---

## How Dynamic Routing Works (동작 원리)

```
질문 입력
    │
    ▼
System Prompt으로 도구 카테고리 안내
    │
    ├─ context7__*       ← 라이브러리/API/프레임워크 관련 질문
    ├─ sequential_thinking__*  ← 복잡한 추론/분석/설계 질문
    └─ filesystem__*     ← 파일/디렉토리 조작 질문
    │
    ▼
LLM이 질문 도메인을 판단 → 적절한 접두어의 도구 선택
    │
    ▼
[Tool: xxx__yyy] 형태로 실시간 출력 (어떤 도구를 사용하는지 투명하게 표시)
```

**핵심 메커니즘:**
- `MultiServerMCPClient`가 3개의 MCP 서버를 동시에 연결
- 각 서버의 도구에 서버명 접두어가 자동 추가 (`filesystem__read_file` 등)
- System Prompt에서 접두어 기반 라우팅 규칙을 LLM에게 안내
- LLM이 질문 맥락을 분석하여 알맞은 도구를 자동 선택

---

## Notes (주의사항) — combined_agent.py

### 1. 도구명 충돌 방지 (`tool_name_prefix`)

`MultiServerMCPClient`는 내부적으로 각 서버의 도구명 앞에 **서버명 접두어를 자동 추가**합니다.

```
context7__resolve-library-id
sequential_thinking__sequentialthinking
filesystem__read_file
```

서버마다 동일한 이름의 도구(예: `list_resources`)가 존재할 수 있습니다.
접두어가 없으면 나중에 로드된 도구가 앞의 도구를 **조용히 덮어써서** 일부 서버 도구를 사용할 수 없게 됩니다.
접두어 덕분에 각 도구가 고유하게 구분되며 System Prompt의 라우팅 규칙도 정확하게 동작합니다.

### 2. `MultiServerMCPClient`는 `async with` 미지원

`langchain-mcp-adapters` v0.1.0 이후 컨텍스트 매니저 지원이 **제거**되었습니다.
아래와 같이 `async with`를 사용하면 `NotImplementedError`가 발생합니다:

```python
# ❌ 잘못된 사용 — NotImplementedError 발생
async with MultiServerMCPClient({...}) as client:
    tools = client.get_tools()
```

반드시 컨텍스트 매니저 없이 인스턴스를 생성한 뒤 `get_tools()`를 직접 호출해야 합니다:

```python
# ✅ 올바른 사용
client = MultiServerMCPClient({...})
tools = await client.get_tools()
```

---

## Troubleshooting

| 문제 | 원인 | 해결 방법 |
|---|---|---|
| `npx: command not found` | Node.js 미설치 | Node.js 18+ 설치 |
| `ANTHROPIC_API_KEY` 오류 | `.env` 파일 없거나 키 누락 | `.env` 파일에 API 키 설정 |
| 도구 0개 로드됨 | MCP 서버 연결 실패 | 인터넷 연결 및 npx 정상 동작 확인 |
| `ModuleNotFoundError: langchain_mcp_adapters` | 패키지 미설치 | `pip install langchain-mcp-adapters` |
| `ModuleNotFoundError: langgraph` | 패키지 미설치 | `pip install langgraph` |
| 파일 접근 거부 오류 | filesystem 허용 경로 외 접근 | 실행 시 해당 디렉토리를 인자로 전달 |
