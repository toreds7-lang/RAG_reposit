"""
Trace Logger — 세션별 단계 기록 시스템.

매 세션마다 trace_log/YYYYMMDD_HHMMSS_<id>.txt 파일을 생성하고,
모든 파이프라인 단계를 타임스탬프와 함께 append 방식으로 기록합니다.

로그 형식:
    [2026-03-29 14:30:22.123] [SESSION_START] url=http://internal/ session=abc12345
    [2026-03-29 14:30:26.001] [SELECTOR_TRY] type=input selector="#prompt-textarea" result=FOUND
    [2026-03-29 14:31:05.123] [RESPONSE_RECEIVED] length=1250 elapsed_s=39.1
"""

import os
import uuid
from datetime import datetime
from pathlib import Path


class TraceLogger:
    """세션별 trace 로그를 trace_log/*.txt 파일에 기록합니다."""

    def __init__(self, log_dir: str):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        session_id = uuid.uuid4().hex[:8]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{session_id}.txt"
        self._session_file = self._log_dir / filename
        self._session_id = session_id

    @property
    def session_file(self) -> Path:
        return self._session_file

    @property
    def session_id(self) -> str:
        return self._session_id

    def log(self, event: str, **kwargs) -> None:
        """
        이벤트와 key=value 쌍을 타임스탬프와 함께 세션 파일에 기록합니다.

        사용 예:
            tracer.log("SELECTOR_TRY", type="input", selector="#id", result="FOUND")
        """
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # ms precision
        parts = [f"[{ts}]", f"[{event}]"]
        for k, v in kwargs.items():
            # 공백 포함 값은 따옴표로 감쌈
            sv = str(v)
            if " " in sv:
                parts.append(f'{k}="{sv}"')
            else:
                parts.append(f"{k}={sv}")
        line = " ".join(parts)

        with self._session_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
