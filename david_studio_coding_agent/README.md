# 코딩 AI 에이전트 만들기

OpenAI API를 사용하여 단계별로 코딩 AI 에이전트를 구현하는 튜토리얼 프로젝트입니다.

## 사전 요구사항

- 파이썬 설치
- OpenAI API 키 설정

## 초기 셋팅

### OpenAI API 키 설정

프로젝트 루트에 `.env` 파일 생성:

```
OPENAI_API_KEY=여기에_API_키_입력
```

### 의존성 설치

```bash
uv sync
```

## 실행 방법

스크립트를 순서대로 실행하세요:

```bash
# 1단계: 기본 LLM 호출
uv run 1_llm_call.py

# 2단계: 단일 도구 사용
uv run 2_tool_call.py

# 3단계: 반복문에서 도구 사용 (계산기 에이전트)
uv run 3_calculator_agent.py

# 4단계: 코딩 도구 구현
uv run 4_coding_tools.py

# 5단계: 완전한 코딩 에이전트
uv run 5_coding_agent.py
```

## 프로젝트 구조

각 스크립트는 점진적으로 에이전트의 개념을 확장합니다:

- **1단계**: 기본 LLM 호출
- **2단계**: 단일 도구 사용
- **3단계**: 반복문에서 여러 도구 사용
- **4단계**: 코딩 도구 구현 (파일 읽기/쓰기/수정)
- **5단계**: 완전한 코딩 에이전트
