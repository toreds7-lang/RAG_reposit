# ArXiv MCP Agent

LangChain MCP Adapters를 사용하여 arXiv 논문을 검색하고 분석하는 AI 에이전트입니다.
MCP(Model Context Protocol) Session 모드(stdio transport)로 서버와 통신합니다.

## 구조

```
arxiv/
├── .env               # API 키 설정 파일
├── arxiv_agent.py     # MCP 클라이언트 (메인 실행 파일)
└── arxiv-mcp/         # arXiv MCP 서버 (git clone)
```

## 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `search_arxiv` | 키워드로 arXiv 논문 검색 |
| `get_paper_details` | arXiv ID로 논문 상세 정보 조회 |
| `search_and_summarize` | 논문 검색 후 종합 요약 생성 |

## 설치 방법

### 1. 소스 다운로드

```bash
git clone https://github.com/kelvingao/arxiv-mcp.git
```

### 2. Python 가상환경 생성

```bash
uv venv
```

### 3. arxiv-mcp 서버 설치

```bash
uv pip install -e ./arxiv-mcp
```

> 설치 후 `arxiv-mcp/src/server.py`에서 `FastMCP()` 생성자의 `description` 파라미터를 제거해야 합니다.
> 설치된 mcp 버전에서 해당 파라미터를 지원하지 않기 때문입니다.

### 4. 클라이언트 의존성 설치

```bash
uv pip install langchain-anthropic langchain-mcp-adapters langchain python-dotenv
```

### 5. 환경 변수 설정

`.env` 파일에 Anthropic API 키를 설정합니다.

```
ANTHROPIC_API_KEY=sk-ant-...your-key...
```

## 실행 방법

```bash
.venv/Scripts/python arxiv_agent.py
```

실행하면 아래와 같이 MCP 서버에 연결되고 도구가 로드됩니다.

```
Connecting to ArXiv MCP server...
Loaded 3 tools: search_arxiv, get_paper_details, search_and_summarize
ArXiv Agent ready. Type your query (or 'quit' to exit).

You:
```

## 자연어 Query 예시

### 논문 검색

```
You: LLM 에이전트에 대한 최신 논문을 찾아줘
```

```
You: transformer 아키텍처 개선에 관한 논문 5편을 검색해줘
```

```
You: retrieval augmented generation 관련 논문을 찾아줘
```

### 특정 논문 조회

```
You: arXiv 논문 2401.04088의 상세 정보를 알려줘
```

```
You: 논문 ID 2305.10601의 저자와 초록을 확인해줘
```

### 검색 + 요약

```
You: multi-agent system 관련 논문을 검색하고 요약해줘
```

```
You: 최근 code generation 분야의 연구 동향을 정리해줘
```

### 복합 질의

```
You: knowledge graph와 LLM을 결합한 연구를 찾아서 각 논문의 핵심 기여를 비교해줘
```

```
You: MCP protocol에 대한 논문이 있는지 찾아보고, 없으면 관련된 tool-use 논문을 추천해줘
```

### 종료

```
You: quit
```

## 동작 원리

1. `arxiv_agent.py`가 `stdio_client`로 arxiv-mcp 서버를 자식 프로세스로 실행
2. `ClientSession`으로 MCP 세션을 수립 (Session 모드)
3. `load_mcp_tools(session)`으로 서버의 도구들을 LangChain 도구로 변환
4. Claude (claude-sonnet-4-20250514) + LangChain Agent가 자연어 입력을 분석하여 적절한 도구 호출
5. 대화형 루프로 연속 질의 가능
