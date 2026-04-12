# OpenHarness + 사내 vLLM 서버 연결 설치 가이드

OpenHarness를 사내 vLLM 서버(OpenAI 호환 API)에 연결하여 사용하는 방법을 안내합니다.

---

## 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [Python 가상환경 구성](#2-python-가상환경-구성)
3. [OpenHarness 설치](#3-openharness-설치)
4. [설정 파일 구성](#4-설정-파일-구성)
5. [실행 방법](#5-실행-방법)
6. [사용 예시](#6-사용-예시)
7. [문제 해결](#7-문제-해결)

---

## 1. 사전 요구사항

| 항목 | 요구 사항 |
|------|-----------|
| Python | 3.10 이상 |
| 사내 vLLM 서버 | OpenAI 호환 API 엔드포인트 (예: `http://vllm-server:8000/v1`) |
| 사내 모델명 | vLLM에 로드된 모델 이름 (예: `meta-llama/Meta-Llama-3-8B-Instruct`) |
| API 키 | 사내 vLLM 서버 담당자에게 발급받은 API 키 |
| 네트워크 | vLLM 서버 접근 가능한 사내 네트워크 연결 |

> **vLLM 서버 정보 확인 방법**  
> 서버 담당자에게 다음 항목을 확인하세요:
> - 엔드포인트 URL (예: `http://192.168.1.100:8000/v1`)
> - 로드된 모델명 (예: `curl http://vllm-server:8000/v1/models` 로 조회 가능)
> - 발급받은 API 키

---

## 2. Python 가상환경 구성

프로젝트 디렉터리를 만들고 가상환경을 구성합니다.

```bash
# 프로젝트 디렉터리 생성
mkdir OpenHarness
cd OpenHarness

# 가상환경 생성 (Python 3.10 이상)
python -m venv .venv
```

### Windows

```bash
# 가상환경 활성화 (PowerShell)
.venv\Scripts\Activate.ps1

# 또는 CMD
.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Python 버전 확인:

```bash
python --version
# Python 3.10.x 이상이어야 합니다
```

---

## 3. OpenHarness 설치

가상환경이 활성화된 상태에서 설치합니다.

```bash
pip install openharness-ai
```

설치 확인:

```bash
oh --version
# openharness 0.1.x
```

> **Windows에서 `oh` 명령을 찾을 수 없는 경우**  
> 가상환경의 Scripts 경로를 직접 사용합니다:  
> `.venv\Scripts\oh.exe --version`

---

## 4. 설정 파일 구성

OpenHarness는 `~/.openharness/` 디렉터리에 설정을 저장합니다.  
아래 두 파일을 직접 생성하면 **대화형 설정 없이** 바로 사용할 수 있습니다.

### 디렉터리 생성

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.openharness"
```

**macOS / Linux:**
```bash
mkdir -p ~/.openharness
```

---

### 4-1. settings.json — 공통 설정

`~/.openharness/settings.json` 파일을 아래 내용으로 생성합니다.  
`YOUR_MODEL_NAME`과 `YOUR_VLLM_ENDPOINT`를 실제 사내 환경 값으로 교체하세요.

```json
{
  "active_profile": "vllm-local",
  "profiles": {
    "vllm-local": {
      "label": "사내 vLLM 서버",
      "provider": "openai",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "YOUR_MODEL_NAME",
      "last_model": "YOUR_MODEL_NAME",
      "base_url": "http://YOUR_VLLM_ENDPOINT/v1"
    }
  }
}
```

**설정 예시 (Llama 3 모델, 서버 IP 192.168.1.100):**

```json
{
  "active_profile": "vllm-local",
  "profiles": {
    "vllm-local": {
      "label": "사내 vLLM 서버",
      "provider": "openai",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "meta-llama/Meta-Llama-3-8B-Instruct",
      "last_model": "meta-llama/Meta-Llama-3-8B-Instruct",
      "base_url": "http://192.168.1.100:8000/v1"
    }
  }
}
```

---

### 4-2. credentials.json — API 키 설정

`~/.openharness/credentials.json` 파일을 생성합니다.  
`사내에서-발급받은-API-키` 부분을 실제 발급받은 키로 교체하세요.

```json
{
  "openai": {
    "api_key": "사내에서-발급받은-API-키"
  }
}
```

> **보안 주의사항**  
> - `credentials.json` 파일에는 API 키가 평문으로 저장됩니다.  
> - 이 파일을 git에 커밋하지 마세요.  
> - Windows에서는 파일 권한을 본인 계정으로만 제한하는 것을 권장합니다.

---

### 4-3. 설정 검증

설정이 올바르게 되었는지 확인합니다.

```bash
python -c "
from openharness.config.settings import load_settings
s = load_settings()
print('active_profile:', s.active_profile)
print('provider:', s.provider)
print('model:', s.model)
print('base_url:', s.base_url)
auth = s.resolve_auth()
print('auth_state:', auth.state)
print('auth_source:', auth.source)
"
```

정상 출력 예시:
```
active_profile: vllm-local
provider: openai
model: meta-llama/Meta-Llama-3-8B-Instruct
base_url: http://192.168.1.100:8000/v1
auth_state: configured
auth_source: file:openai
```

---

## 5. 실행 방법

### 대화형 TUI 모드 (추천)

터미널에서 실행하면 전체 UI 인터페이스가 표시됩니다.

```bash
oh
```

### 단일 프롬프트 (비대화형)

```bash
# 텍스트 출력
oh -p "현재 디렉터리의 파일 목록을 보여줘"

# JSON 출력
oh -p "현재 디렉터리의 파일 목록을 보여줘" --output-format json

# 스트리밍 JSON 출력
oh -p "현재 디렉터리의 파일 목록을 보여줘" --output-format stream-json
```

### 특정 디렉터리에서 실행

```bash
oh --cwd /path/to/project -p "이 프로젝트의 구조를 설명해줘"
```

### Windows (가상환경 미활성화 상태)

```bash
.venv\Scripts\oh.exe -p "안녕하세요"
```

---

## 6. 사용 예시

```bash
# 코드 설명
oh -p "main.py 파일을 읽고 주요 함수를 설명해줘"

# 버그 수정
oh -p "app.py의 버그를 찾아서 고쳐줘"

# 테스트 작성
oh -p "utils.py에 대한 단위 테스트를 작성해줘"

# 리팩터링
oh -p "database.py의 중복 코드를 정리해줘"
```

---

## 7. 문제 해결

### vLLM 서버 연결 확인

OpenHarness 실행 전에 서버 접근을 먼저 확인합니다.

```bash
# 서버 상태 확인
curl http://YOUR_VLLM_ENDPOINT/v1/models

# 정상 응답 예시
# {"object":"list","data":[{"id":"meta-llama/Meta-Llama-3-8B-Instruct",...}]}
```

---

### 오류별 해결 방법

| 오류 메시지 | 원인 | 해결 방법 |
|-------------|------|-----------|
| `Connection refused` | vLLM 서버 미실행 또는 IP/포트 오류 | `base_url` 주소와 서버 상태 확인 |
| `No credentials found` | credentials.json 없거나 내용 오류 | `credentials.json` 파일 내용 재확인 |
| `Model not found` | 모델명 불일치 | `curl .../v1/models` 로 실제 모델명 조회 후 수정 |
| `oh: command not found` | 가상환경 미활성화 | `.venv/Scripts/activate` 실행 또는 전체 경로 사용 |
| `Python version` 오류 | Python 3.10 미만 | Python 3.10 이상 버전으로 재설치 |

---

### 설정 초기화

설정을 처음부터 다시 하려면:

```bash
# Windows
Remove-Item -Recurse "$env:USERPROFILE\.openharness"

# macOS / Linux
rm -rf ~/.openharness
```

이후 [4. 설정 파일 구성](#4-설정-파일-구성)부터 다시 진행합니다.

---

## 빠른 설정 요약 (체크리스트)

```
□ Python 3.10 이상 설치 확인
□ 프로젝트 디렉터리 생성
□ python -m venv .venv 실행
□ 가상환경 활성화
□ pip install openharness-ai 실행
□ oh --version 으로 설치 확인
□ ~/.openharness/ 디렉터리 생성
□ settings.json 생성 (모델명, base_url 수정)
□ credentials.json 생성 (발급받은 API 키 입력)
□ curl 로 vLLM 서버 연결 확인
□ oh -p "안녕" 으로 최종 동작 확인
```
