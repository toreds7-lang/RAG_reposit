# 디버깅 가이드 및 프로젝트 구조

## 프로젝트 파일 구조

```
python_deepresearch/
│
├── main.py                          # 파이프라인 진입점 (3단계 순차 실행)
├── utils.py                         # 공통 LLM 헬퍼 (setup_logging, llm_call, JSON_llm)
├── requirements.txt
├── .env                             # API 키 (git 제외)
│
├── step1_feedback/
│   └── feedback.py                  # 1단계: 후속 질문 생성 (JSON_llm 사용)
│
├── step2_research/
│   └── research.py                  # 2단계: 재귀 웹 리서치 (Firecrawl + JSON_llm)
│
├── step3_reporting/
│   └── reporting.py                 # 3단계: 최종 보고서 생성 (llm_call 사용)
│
└── output/
    ├── output.md                    # 최종 보고서 출력
    └── debug.log                    # 디버그 로그 (실행 시 자동 생성)
```

### 각 모듈 역할

| 파일 | 사용 LLM 함수 | 모델 요구사항 |
|---|---|---|
| `step1_feedback/feedback.py` | `JSON_llm()` | Structured Output 지원 필수 |
| `step2_research/research.py` | `JSON_llm()` | Structured Output 지원 필수 |
| `step3_reporting/reporting.py` | `llm_call()` | 제한 없음 (일반 텍스트 생성) |

> **Structured Output 지원 모델**: `gpt-4o`, `gpt-4o-mini`  
> **미지원 모델**: `o1-mini`, 일부 사내 배포 모델

---

## 로깅 시스템

### 설정 구조

`utils.py`의 `setup_logging()`이 **콘솔 + 파일 이중 출력**을 구성합니다.  
`main.py`의 `main()` 첫 줄에서 한 번만 호출되며, 이후 모든 모듈에 자동 적용됩니다.

```
콘솔 출력  →  INFO 이상만  (실행 흐름 요약)
파일 출력  →  DEBUG 이상   (전체 프롬프트·응답·traceback 포함)
```

### 로그 파일 위치

```
output/debug.log
```

실행할 때마다 **이어쓰기(append)** 되므로 여러 번 실행한 기록이 누적됩니다.  
초기화하려면 파일을 직접 삭제하세요.

### 로그 포맷

```
2026-04-09 10:23:01 | INFO     | __main__                    | === Pipeline started ===
2026-04-09 10:23:01 | INFO     | __main__                    | Models | feedback=gpt-4o-mini | research=gpt-4o | reporting=gpt-4o
2026-04-09 10:23:01 | INFO     | step1_feedback.feedback     | generate_feedback started | model=gpt-4o-mini | query='AI 트렌드'
2026-04-09 10:23:01 | DEBUG    | utils                       | JSON_llm called | model=gpt-4o-mini | schema=FeedbackResponse
2026-04-09 10:23:01 | DEBUG    | utils                       | JSON_llm prompt (first 500 chars): ...
2026-04-09 10:23:02 | DEBUG    | utils                       | JSON_llm raw response BEFORE parsing: {"questions": [...]}
2026-04-09 10:23:02 | INFO     | step1_feedback.feedback     | generate_feedback completed | 3 questions returned
```

---

## 에러 진단

### 가장 흔한 오류: Structured Output API 미지원

회사 배포 모델이 `client.beta.chat.completions.parse()`를 지원하지 않으면  
`JSON_llm()`이 예외를 던지고 `None`을 반환합니다.

**`output/debug.log`에서 확인할 내용:**

```
2026-04-09 10:23:02 | ERROR | utils | JSON_llm FAILED | model=사내모델명 | schema=FeedbackResponse | error=...
Traceback (most recent call last):
  File "utils.py", line 85, in JSON_llm
    completion = client.beta.chat.completions.parse(
  AttributeError: 'OpenAI' object has no attribute 'beta'
```

**예외 타입별 원인:**

| 예외 타입 | 원인 | 대응 |
|---|---|---|
| `AttributeError` | SDK 버전이 낮거나 사내 모델이 beta API 미지원 | SDK 업그레이드 또는 `json_object` 방식으로 전환 |
| `ValidationError` | 모델이 JSON을 반환했지만 Pydantic 스키마 불일치 | 로그의 `raw response` 확인 후 스키마 조정 |
| `openai.BadRequestError` | `response_format` 파라미터 자체를 거부 | 모델이 Structured Output 완전 미지원 |
| `openai.RateLimitError` | API 요청 한도 초과 | 대기 후 재시도 |

### 연쇄 에러 패턴 읽기

`JSON_llm`이 `None`을 반환하면 → `generate_serp_queries`의 `model_validate(None)` 호출 → `ValidationError` 발생.  
로그에서 두 ERROR가 연달아 나오면 **근본 원인은 항상 먼저 나온 `JSON_llm FAILED`** 입니다.

```
ERROR | utils           | JSON_llm FAILED | model=... | schema=SerpQueryResponse   ← 근본 원인
ERROR | step2_research  | generate_serp_queries FAILED | response_was_none=True    ← 연쇄 오류
```

---

## 로그 레벨별 활용

### 빠른 흐름 확인 (INFO만 보기)

```bash
# Windows
findstr " | INFO " output\debug.log

# Unix/Mac
grep " | INFO " output/debug.log
```

### 특정 단계 에러만 보기

```bash
findstr "ERROR" output\debug.log
findstr "feedback" output\debug.log
```

### 모델별 호출 추적

```bash
findstr "JSON_llm called" output\debug.log
```

---

## 모델 변경 방법

`main.py` 상단의 모델 변수를 수정합니다:

```python
feedback_model  = "gpt-4o-mini"   # Structured Output 지원 모델만 가능
research_model  = "gpt-4o"        # Structured Output 지원 모델만 가능
reporting_model = "gpt-4o"        # 제한 없음 (llm_call 사용)
```

사내 모델을 사용할 경우 `JSON_llm()`이 호출하는  
`client.beta.chat.completions.parse()` 대신  
`response_format={"type": "json_object"}` 방식으로 전환이 필요할 수 있습니다.

---

## Firecrawl 속도 제한 주의

무료 플랜은 **5회/분** 제한이 있습니다.  
`breadth=2, depth=2` 이상으로 설정하면 요청 수가 급격히 늘어납니다.

| breadth | depth | 최대 Firecrawl 요청 수 |
|---|---|---|
| 2 | 2 | 약 6회 |
| 3 | 3 | 약 21회 |
| 4 | 3 | 약 36회 |

요청이 제한에 걸리면 `debug.log`에 `firecrawl_search FAILED` 에러가 기록됩니다.
