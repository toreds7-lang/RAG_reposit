# 회사 PC 설치 가이드

집 PC에서 만든 이 프로젝트를 회사 PC에서 동일하게 돌리기 위한 단계입니다.
Git으로 코드를 받아와서 아래 순서대로 진행하면 됩니다.

## 사전 요구 사항

- **Windows 10/11**
- **Python 3.11** 설치 — `python --version` 으로 확인 (반드시 3.11.x)
- **Git** 설치
- **인터넷 접속** 필요한 곳:
  - `pypi.org` (pip 패키지 설치 — 최초 1회만)
  - `api.openai.com` (LLM 호출 — 매번)
  - **Whisper 모델 다운로드는 필요 없음** — `models/tiny.pt` (약 72 MB) 가 git 저장소에 포함되어 있음
- **마이크** 가 연결되어 있고, 브라우저(Chrome/Edge) 에서 마이크 권한 허용 가능해야 함
- **HuggingFace 접속은 필요하지 않음** (Qwen3-TTS는 deferred — `TTS_FUTURE.md` 참고)
- **ffmpeg 설치는 필요하지 않음** (앱에서 WAV를 직접 디코드함)

## 설치 순서

### 1. 저장소 받기

```powershell
cd D:\작업폴더
git clone <리포지토리 URL> qwen_stt_test
cd qwen_stt_test
```

### 2. Python 3.11 가상환경 만들기

```powershell
py -3.11 -m venv .venv
```

`py -3.11` 명령이 안 되면 Python 3.11 설치 후 다시 시도. Python 3.12/3.13 으로
만들면 일부 패키지(`numba` 등) 가 안 깔릴 수 있으니 반드시 3.11 사용.

### 3. 가상환경 활성화

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

(만약 실행 정책 오류가 나면 한 번만:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`)

CMD:
```cmd
.\.venv\Scripts\activate.bat
```

Git Bash:
```bash
source .venv/Scripts/activate
```

활성화되면 프롬프트 앞에 `(.venv)` 가 보입니다.

### 4. 파이썬 패키지 설치

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

torch CPU 버전이 자동으로 같이 설치됩니다 (약 200 MB). 첫 설치는 5–10분 정도 걸릴 수 있음.

### 5. `.env` 파일 만들기

`.env` 는 **git에 올라가 있지 않습니다** (API 키 노출 방지). 회사 PC에서 직접 만들어야 합니다.

프로젝트 루트(`qwen_stt_test/`) 에 `.env` 파일을 만들고 아래 내용 입력:

```
OPENAI_API_KEY=sk-여기에_본인_키_입력
LLM_MODEL=gpt-4o-mini
```

집 PC `.env` 의 키를 그대로 복사해도 되고, 새로 발급받아도 됩니다.

### 6. 실행

```powershell
streamlit run app.py
```

자동으로 브라우저가 열리고 `http://localhost:8501` 로 접속됩니다.
Whisper 모델은 프로젝트 안의 `models/tiny.pt` 에서 바로 로드되므로
**별도 다운로드가 발생하지 않습니다** (약 0.3초 만에 로딩 완료).

## 사용법

1. 마이크 권한 허용 (브라우저가 처음 한 번 물어봄)
2. **Record** 버튼 클릭 → 말하기 → **Stop** 클릭
3. 잠시 기다리면 (Whisper 변환 → GPT 응답) 채팅 형식으로 결과 표시
4. 다음 질문도 같은 방식으로 반복 (이전 대화 맥락 유지됨)
5. 사이드바의 **Clear chat** 으로 대화 초기화

## 자주 발생하는 문제

| 증상 | 해결 |
|---|---|
| `streamlit: command not found` | 가상환경 활성화 안 된 상태. `.venv` 활성화 후 다시 시도 |
| 마이크 버튼이 회색 | 브라우저에서 마이크 권한 거부됨 — 주소창 자물쇠 → 마이크 허용 |
| `OPENAI_API_KEY ... not set` | `.env` 파일 위치/내용 확인. 키 앞뒤 공백, 따옴표 들어가지 않게 |
| `models/tiny.pt` 파일이 없다 | git clone 이 정상적으로 끝났는지 확인. 75 MB 파일이라 LFS 가 필요한 경우 `git lfs pull` 실행 |
| 응답이 너무 느림 | Whisper tiny 는 CPU 에서도 빠른 편. 느리면 GPT API 응답 지연일 가능성 — 인터넷 상태 확인 |

## 미래 작업 (TTS 추가)

음성 출력(Qwen3-TTS) 통합은 `TTS_FUTURE.md` 에 별도로 문서화되어 있습니다.
회사 PC 에서는 HuggingFace 접속이 막혀 있으므로 집에서 모델을 먼저 받은 뒤
`%USERPROFILE%\.cache\huggingface\hub\` 캐시를 통째로 복사해 와야 합니다.
