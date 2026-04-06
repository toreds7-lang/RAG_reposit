# Mini Coding Agent (OpenAI)

Sebastian Raschka의 [mini-coding-agent](https://github.com/rasbt/mini-coding-agent)를 OpenAI API 기반으로 포팅한 경량 코딩 에이전트입니다.  
외부 프레임워크 없이 표준 라이브러리만으로 구현되었으며, GPT 모델을 백엔드로 사용합니다.

---

## 요구 사항

- Python 3.10 이상
- OpenAI API 키

---

## 설치

```bash
pip install openai
```

---

## 환경 설정

프로젝트 루트(또는 `--cwd`로 지정한 디렉터리)에 `.env` 파일을 만들고 API 키를 입력합니다.

```env
OPENAI_API_KEY=sk-...
```

또는 실행 시 `--api-key` 옵션으로 직접 전달할 수 있습니다.

---

## 실행 방법

### 대화형 모드 (Interactive)

```bash
python mini_coding_agent.py
```

프롬프트가 표시되면 자연어로 작업을 입력합니다.

```
mini-coding-agent> 이 디렉터리의 파일 목록을 보여줘
mini-coding-agent> binary_search.py 파일을 만들고 테스트도 작성해줘
```

### 1회성 실행 (One-shot)

```bash
python mini_coding_agent.py "이 디렉터리의 파일을 나열해줘"
```

### 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--model` | `gpt-4o-mini` | 사용할 OpenAI 모델 |
| `--api-key` | (`.env` 참조) | OpenAI API 키 |
| `--cwd` | `.` | 에이전트가 작업할 디렉터리 |
| `--approval` | `ask` | 위험 작업 승인 방식 (`ask` / `auto` / `never`) |
| `--max-steps` | `6` | 요청당 최대 도구 호출 횟수 |
| `--max-new-tokens` | `512` | 단계당 최대 생성 토큰 수 |
| `--temperature` | `0.2` | 샘플링 온도 |
| `--resume` | - | 이전 세션 재개 (`--resume latest` 또는 세션 ID) |
| `--timeout` | `120` | OpenAI 요청 타임아웃 (초) |

#### 사용 예시

```bash
# GPT-4o 모델 사용
python mini_coding_agent.py --model gpt-4o "테스트 코드를 작성해줘"

# 모든 도구 사용을 자동 승인 (확인 없이 파일 쓰기, 명령 실행)
python mini_coding_agent.py --approval auto "리팩토링해줘"

# 마지막 세션 이어서 작업
python mini_coding_agent.py --resume latest

# 특정 디렉터리를 워크스페이스로 지정
python mini_coding_agent.py --cwd /path/to/project
```

### 대화형 모드 내 명령어

| 명령어 | 설명 |
|--------|------|
| `/help` | 도움말 표시 |
| `/memory` | 에이전트의 현재 작업 메모리 표시 |
| `/session` | 저장된 세션 파일 경로 표시 |
| `/reset` | 현재 세션 기록 및 메모리 초기화 |
| `/exit` | 에이전트 종료 |

---

## 코드 구조

모든 로직은 `mini_coding_agent.py` 단일 파일에 구현되어 있습니다.  
내부는 6개의 핵심 컴포넌트로 구성됩니다.

```
mini_coding_agent.py
│
├── load_dotenv()               .env 파일 로드 (stdlib 전용)
│
├── [컴포넌트 1] WorkspaceContext   Git 저장소 메타데이터 수집
├── [컴포넌트 5] SessionStore       세션 JSON 저장/불러오기
│
├── FakeModelClient             테스트용 가짜 클라이언트
├── OpenAIModelClient           OpenAI Chat Completions 클라이언트
│
├── MiniAgent                   에이전트 핵심 루프
│   ├── [컴포넌트 2] build_prefix / prompt   시스템 프롬프트 구성
│   ├── [컴포넌트 3] build_tools / run_tool  도구 정의·검증·승인
│   ├── [컴포넌트 4] clip / history_text     컨텍스트 길이 제한
│   ├── [컴포넌트 5] record / note_tool / ask  대화 기록·메모리
│   └── [컴포넌트 6] tool_delegate           하위 에이전트 위임
│
├── build_welcome()             시작 화면 렌더링
├── build_agent()               인자로 에이전트 초기화
├── build_arg_parser()          CLI 인자 파서
└── main()                      진입점
```

### 6개 핵심 컴포넌트 상세

| # | 컴포넌트 | 클래스/함수 | 역할 |
|---|----------|------------|------|
| 1 | Live Repo Context | `WorkspaceContext` | `git` 명령으로 브랜치·커밋·상태 수집, 프롬프트에 주입 |
| 2 | Prompt Shaping | `build_prefix()`, `prompt()` | 시스템 프롬프트(도구 정의 포함) 생성 및 히스토리 결합 |
| 3 | Structured Tools | `build_tools()`, `run_tool()`, `validate_tool()`, `approve()` | 7개 도구 스키마 정의, 경로 검증, 위험 작업 승인 게이트 |
| 4 | Context Reduction | `clip()`, `history_text()` | 토큰 예산 관리, 출력 및 히스토리 자르기 |
| 5 | Session Memory | `SessionStore`, `record()`, `ask()` | JSON으로 대화 기록 저장·재개, 작업 메모리 유지 |
| 6 | Delegation | `tool_delegate()` | 읽기 전용 하위 에이전트 생성, 깊이 제한으로 무한 재귀 방지 |

### 7개 도구

| 도구 | 위험 여부 | 설명 |
|------|-----------|------|
| `list_files` | 안전 | 워크스페이스 파일 목록 조회 |
| `read_file` | 안전 | UTF-8 파일 읽기 (행 범위 지정 가능) |
| `search` | 안전 | ripgrep / 문자열 검색 |
| `delegate` | 안전 | 읽기 전용 하위 에이전트에 작업 위임 |
| `run_shell` | **위험** | 셸 명령 실행 (타임아웃 1~120초) |
| `write_file` | **위험** | 파일 생성 및 덮어쓰기 |
| `patch_file` | **위험** | 파일 내 특정 텍스트 블록 교체 |

위험 도구는 `--approval ask`(기본값)일 때 실행 전 사용자 확인을 요청합니다.

### 세션 저장 위치

```
<workspace>/.mini-coding-agent/sessions/<session-id>.json
```

---

## 파일 구조

```
mini_coding_agent/
├── mini_coding_agent.py   # 에이전트 전체 구현 (단일 파일)
├── requirements.txt        # 의존성 (openai>=1.0.0)
├── .env                    # API 키 (OPENAI_API_KEY=sk-...)
└── README.md               # 이 문서
```
