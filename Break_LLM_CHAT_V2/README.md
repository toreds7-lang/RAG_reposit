# Break_LLM_CHAT_V2

사내 API LLM(낮은 성능)이 LangChain으로 전체 흐름을 오케스트레이션하고,
Selenium을 통해 웹 기반 고성능 LLM(reasoning 포함)을 간접 제어하는 시스템입니다.

```
┌─────────────────────────────────────────────────┐
│  사용자 질의                                     │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  LLMChatAgent  (llm_chat_agent.py)              │
│  사내 API LLM + LangChain AgentExecutor          │
│  — 질의 분석 및 단계 분해                        │
└────────────────────┬────────────────────────────┘
                     │ ThinkingModelQuery Tool 호출
                     ▼
┌─────────────────────────────────────────────────┐
│  WebLLMTool  (web_llm_tool.py)                  │
│  LangChain Tool 래퍼                            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  LLMChatClient  (chat_client.py)                │
│  Selenium — 웹 채팅 입력 / 응답 추출            │
│  + Self-healing selector                        │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
         웹 채팅 고성능 LLM (reasoning)
```

---

## 파일 설명

### `config.py`
환경변수(`.env`)를 읽어 `AgentConfig` 데이터클래스로 반환합니다.
모든 설정 값의 단일 진입점이며, 필수 변수(`VLLM_BASE_URL`, `VLLM_MODEL`, `LLM_CHAT_URL`) 누락 시 명확한 오류 메시지와 함께 종료합니다.

주요 설정 항목:

| 항목 | 환경변수 | 기본값 | 설명 |
|------|----------|--------|------|
| 오케스트레이터 URL | `VLLM_BASE_URL` | — | 사내 API LLM 엔드포인트 |
| 오케스트레이터 모델 | `VLLM_MODEL` | — | 오케스트레이터로 사용할 모델명 |
| 웹 채팅 URL | `LLM_CHAT_URL` | — | Selenium이 접속할 웹 채팅 주소 |
| 실패 임계값 | `SELECTOR_FAILURE_THRESHOLD` | `3` | N회 실패 시 자동 재발견 트리거 |
| 캐시 파일 | `SELECTOR_CACHE_FILE` | `selector_cache.json` | Selector 영속 저장 경로 |
| Trace 로그 디렉토리 | `TRACE_LOG_DIR` | `trace_log` | 로그 파일 저장 폴더 |

---

### `trace_logger.py`
매 실행 세션마다 `trace_log/YYYYMMDD_HHMMSS_<id>.txt` 파일을 생성하고,
파이프라인의 모든 단계를 타임스탬프와 함께 기록합니다.

**로그 형식:**
```
[2026-03-29 14:30:22.123] [SESSION_START] url=http://internal/ session=abc12345
[2026-03-29 14:30:23.456] [DISCOVERY_START] url=http://internal/
[2026-03-29 14:30:25.789] [DISCOVERY_RESULT] source=llm input=3 send=2 loading=2 response=3
[2026-03-29 14:30:25.790] [CACHE_SAVED] url=http://internal/
[2026-03-29 14:30:26.000] [QUERY_SEND] length=22
[2026-03-29 14:30:26.001] [SELECTOR_TRY] type=input selector="#prompt-textarea" result=FOUND
[2026-03-29 14:30:26.500] [LOADING_DETECTED]
[2026-03-29 14:31:05.123] [RESPONSE_RECEIVED] length=1250 elapsed_s=39.1
[2026-03-29 14:31:10.000] [SELECTOR_FAIL] type=input total_failures=3
[2026-03-29 14:31:10.001] [SELF_HEAL_TRIGGER] reason=input_not_found
[2026-03-29 14:31:10.002] [SELF_HEAL_START]
[2026-03-29 14:31:15.000] [SELF_HEAL_DONE] new_selectors=5 source=llm
[2026-03-29 14:31:15.001] [SESSION_END] total_queries=3
```

**주요 이벤트:**

| 이벤트 | 발생 시점 |
|--------|-----------|
| `SESSION_START` / `SESSION_END` | 에이전트 시작 / 종료 |
| `DISCOVERY_START` / `DISCOVERY_RESULT` | Selector 자동 발견 |
| `CACHE_HIT` / `CACHE_SAVED` | Selector 캐시 적중 / 저장 |
| `SELECTOR_TRY` | CSS selector 시도 (성공 시만 기록) |
| `SELECTOR_FAIL` | Selector 탐색 실패 |
| `SELF_HEAL_TRIGGER` / `SELF_HEAL_DONE` | Self-healing 시작 / 완료 |
| `LOADING_DETECTED` | 모델 생성 중 로딩 표시자 감지 |
| `RESPONSE_RECEIVED` | 응답 수신 완료 |
| `TOOL_CALL` / `TOOL_RESPONSE` | LangChain Tool 호출 / 응답 |

---

### `selector_store.py`
URL별로 발견된 CSS selector를 `selector_cache.json`에 영속 저장하고,
실패 카운터를 관리하여 self-healing 트리거 여부를 판단합니다.

**캐시 파일 구조 (`selector_cache.json`):**
```json
{
  "http://internal-llm-chat/": {
    "discovered_at": "2026-03-29T14:30:25",
    "failures": 0,
    "input_selectors": ["#chat-input", "textarea[placeholder]"],
    "send_button_selectors": ["button[aria-label='Send']"],
    "loading_indicators": ["[class*='generating']"],
    "response_selectors": ["[data-role='assistant']"]
  }
}
```

**주요 메서드:**

| 메서드 | 설명 |
|--------|------|
| `load(url)` | 캐시에서 selector 로드 |
| `save(url, discovered)` | 발견된 selector 저장 및 실패 카운터 초기화 |
| `mark_failure(url)` | 실패 카운터 +1, 현재 횟수 반환 |
| `reset_failures(url)` | 실패 카운터 0으로 초기화 |
| `should_rediscover(url)` | 실패 횟수 >= threshold 이면 `True` 반환 |

---

### `selector_analyzer.py`
헤드리스 브라우저로 웹 페이지 HTML을 가져온 뒤 오케스트레이터 LLM에게
분석을 요청하여 CSS selector를 자동으로 발견합니다.

**발견 파이프라인:**
```
_get_page_html()      — 헤드리스 Chrome으로 페이지 소스 취득
    ↓
_strip_scripts_and_styles()  — <script>, <style> 제거
    ↓
_ask_llm_for_selectors()     — LLM에게 JSON 형식으로 selector 요청 (최대 3회 재시도)
    ↓
_validate_selectors()        — 결과 검증 및 DiscoveredSelectors 반환
    ↓
patch_chat_client_selectors() — chat_client 모듈 레벨 리스트에 prepend (런타임 패치)
```

LLM이 JSON 반환에 실패하거나 네트워크 오류 시에는 빈 `DiscoveredSelectors`를 반환하여
내장 selector 목록으로 자동 폴백합니다.

---

### `chat_client.py`
Selenium WebDriver로 웹 채팅 UI를 직접 제어합니다.
selector 탐색, 메시지 입력, 응답 대기, self-healing 로직이 모두 이 모듈에 있습니다.

**응답 대기 3단계 전략:**
```
Phase 1 — 로딩 표시자 출현 감지 (모델 생성 시작 확인)
Phase 2 — 로딩 표시자 소멸 대기 (모델 생성 완료 확인)
Phase 3 — 텍스트 안정화 확인 (0.5초 간격으로 4회 동일 = 약 2초간 변화 없음)
```

**내장 Selector 목록** (가장 구체적 → 가장 일반적 순서):

| 분류 | 기본 Selector 예시 |
|------|-------------------|
| 입력창 | `#prompt-textarea`, `div[contenteditable='true'][role='textbox']`, `textarea` |
| 전송 버튼 | `button[data-testid='send-button']`, `button[aria-label*='Send']`, `button[type='submit']` |
| 로딩 표시자 | `button[data-testid='stop-button']`, `[class*='generating']`, `[class*='spinner']` |
| 응답 영역 | `[data-message-author-role='assistant']`, `[class*='bot-message']`, `[class*='response']` |

---

### `web_llm_tool.py`
`LLMChatClient`를 LangChain `Tool`로 래핑합니다.
에이전트는 `ThinkingModelQuery`라는 이름으로 이 도구를 호출합니다.

단일 Selenium 세션을 유지하는 싱글턴 패턴을 사용하므로
동일 세션에서 여러 번 질의해도 브라우저를 새로 열지 않습니다.

---

### `llm_chat_agent.py`
전체 시스템의 진입점이자 오케스트레이터입니다.

**시작 시퀀스 (`startup()`):**
1. `TraceLogger` 초기화 → 세션 로그 파일 생성
2. `selector_cache.json` 캐시 확인 → 캐시 적중 시 즉시 적용, 미스 시 LLM으로 새로 발견
3. 브라우저 열기 및 로그인 대기
4. `AgentExecutor` 빌드 (tool-calling → ReAct 폴백)
5. `atexit` 정리 핸들러 등록

---

## Self-healing Selector 동작 흐름

웹 페이지의 HTML 구조가 동적으로 변경되어 기존 selector가 더 이상 유효하지 않을 때
시스템이 자동으로 새 selector를 학습하고 재시도합니다.

```
send_query(query) 호출
        │
        ▼
  find_input() 시도
  ── 각 selector를 순서대로 시도 ──
        │
    성공? ──── Yes ──→ 정상 실행 계속
        │
       No
        │
        ▼
  SelectorStore.mark_failure(url)
  실패 횟수 += 1
        │
  failures >= threshold(기본 3)?
        │
       No ──→ RuntimeError (단순 실패)
        │
       Yes
        │
        ▼
  SelectorNeedHeal 예외 raise
        │
        ▼
  [SELF_HEAL_TRIGGER] 이벤트 기록
        │
        ▼
  discover_selectors()
  ┌─────────────────────────────┐
  │ 1. 헤드리스 브라우저로 HTML 취득 │
  │ 2. LLM에게 HTML 분석 요청     │
  │ 3. JSON selector 추출 및 검증 │
  └─────────────────┬───────────┘
                    │
                    ▼
  patch_chat_client_selectors()
  — 모듈 레벨 리스트 맨 앞에 새 selector 삽입
        │
        ▼
  SelectorStore.save()
  — selector_cache.json 갱신
  — 실패 카운터 0 초기화
        │
        ▼
  [SELF_HEAL_DONE] 이벤트 기록
        │
        ▼
  find_input() 재시도
  ── 2차 실패 시 RuntimeError
```

**캐시 우선 전략:**
시스템 시작 시 `selector_cache.json`에 해당 URL의 selector가 존재하면
LLM 분석 없이 즉시 적용합니다. LLM 호출은 캐시 미스 또는 self-healing 시에만 발생합니다.

---

## 시작 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 아래 필수 항목을 입력합니다:

```env
# 사내 오케스트레이터 LLM (API 접근 가능한 모델)
VLLM_BASE_URL=http://10.0.0.5:8000/v1
VLLM_MODEL=mistral-7b-instruct

# Selenium이 접속할 웹 채팅 주소
LLM_CHAT_URL=http://internal-llm-chat/
```

### 3. 실행

**단일 질의:**
```bash
python llm_chat_agent.py --query "CAP 정리를 쉽게 설명해줘"
```

**대화형 REPL:**
```bash
python llm_chat_agent.py --interactive
```

**로그인 세션이 이미 있는 경우 (쿠키 재사용):**
```bash
python llm_chat_agent.py --no-wait-for-login --query "파이썬으로 퀵소트 구현해줘"
```

**Selector 발견 건너뛰기 (내장 목록 사용):**
```bash
python llm_chat_agent.py --skip-discovery --query "안녕하세요"
```

**Selenium만 단독 테스트:**
```bash
python chat_client.py --url http://internal-llm-chat/ --query "테스트 메시지"
```

### 4. Trace 로그 확인

실행 후 `trace_log/` 폴더에 세션별 `.txt` 파일이 생성됩니다:

```bash
# Windows
type trace_log\20260329_143022_abc12345.txt

# macOS / Linux
cat trace_log/20260329_143022_abc12345.txt
```

### 5. Self-healing 동작 확인

**캐시 초기화 후 새로운 Selector 발견 테스트:**
```bash
# 캐시 삭제
del selector_cache.json   # Windows
rm selector_cache.json    # macOS / Linux

# 재실행 시 DISCOVERY_START → CACHE_SAVED 이벤트 확인
python llm_chat_agent.py --query "테스트"
```

**Self-healing 강제 트리거 테스트:**
```bash
# selector_cache.json의 input_selectors를 잘못된 값으로 수정
# 예: ["#nonexistent-element-xyz"]
# 실행 후 trace 로그에서 SELF_HEAL_TRIGGER 이벤트 확인
python llm_chat_agent.py --query "테스트"
```

---

## CLI 옵션 요약

| 옵션 | 설명 |
|------|------|
| `--query TEXT` | 단일 질의를 전송하고 종료 |
| `--interactive` | 대화형 REPL 모드 (기본값) |
| `--headless` | 헤드리스 모드로 브라우저 실행 |
| `--no-wait-for-login` | 로그인 대기 생략 |
| `--skip-discovery` | CSS selector 자동 발견 건너뛰기 |
| `--vllm-url URL` | 오케스트레이터 LLM URL 직접 지정 |
| `--vllm-model MODEL` | 오케스트레이터 모델명 직접 지정 |
| `--llm-chat-url URL` | 웹 채팅 LLM URL 직접 지정 |
