"""
Selector Store — URL별 CSS selector 영속 캐시 + 실패 카운터.

selector_cache.json 파일에 URL별로 발견된 selector를 저장합니다.
실패 횟수가 threshold에 도달하면 should_rediscover()가 True를 반환하여
self-healing 루프를 트리거합니다.

캐시 파일 구조:
{
  "http://internal-llm/": {
    "discovered_at": "2026-03-29T14:30:25",
    "failures": 0,
    "input_selectors": [...],
    "send_button_selectors": [...],
    "loading_indicators": [...],
    "response_selectors": [...]
  }
}
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# DiscoveredSelectors는 selector_analyzer에 정의되어 있으나,
# 순환 의존 방지를 위해 여기서는 duck-typing으로 처리합니다.


class SelectorStore:
    """URL별 selector를 JSON 파일에 저장하고 실패 카운터를 관리합니다."""

    def __init__(self, cache_file: str, failure_threshold: int = 3):
        self._cache_file = Path(cache_file)
        self._threshold = failure_threshold
        self._data: dict = self._load_file()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, url: str):
        """
        URL에 해당하는 캐시된 DiscoveredSelectors를 반환합니다.
        캐시가 없으면 None을 반환합니다.
        반환 타입은 DiscoveredSelectors이지만, 순환 의존 방지를 위해
        dict를 반환하고 호출자가 변환합니다.
        """
        entry = self._data.get(url)
        if entry is None:
            return None
        return {
            "input_selectors": entry.get("input_selectors", []),
            "send_button_selectors": entry.get("send_button_selectors", []),
            "loading_indicators": entry.get("loading_indicators", []),
            "response_selectors": entry.get("response_selectors", []),
        }

    def save(self, url: str, discovered) -> None:
        """
        DiscoveredSelectors(또는 동일 필드를 가진 객체)를 URL 키로 저장합니다.
        실패 카운터는 0으로 초기화합니다.
        """
        self._data[url] = {
            "discovered_at": datetime.now().isoformat(timespec="seconds"),
            "failures": 0,
            "input_selectors": list(getattr(discovered, "input_selectors", [])),
            "send_button_selectors": list(getattr(discovered, "send_button_selectors", [])),
            "loading_indicators": list(getattr(discovered, "loading_indicators", [])),
            "response_selectors": list(getattr(discovered, "response_selectors", [])),
        }
        self._save_file()
        logger.debug("Selector cache saved for %s", url)

    def mark_failure(self, url: str) -> int:
        """
        해당 URL의 실패 카운터를 1 증가시키고, 현재 총 실패 횟수를 반환합니다.
        캐시 항목이 없으면 새로 생성합니다.
        """
        if url not in self._data:
            self._data[url] = {"failures": 0}
        self._data[url]["failures"] = self._data[url].get("failures", 0) + 1
        count = self._data[url]["failures"]
        self._save_file()
        logger.debug("Selector failure count for %s: %d", url, count)
        return count

    def reset_failures(self, url: str) -> None:
        """해당 URL의 실패 카운터를 0으로 초기화합니다."""
        if url in self._data:
            self._data[url]["failures"] = 0
            self._save_file()

    def should_rediscover(self, url: str) -> bool:
        """실패 횟수가 threshold 이상이면 True를 반환합니다."""
        failures = self._data.get(url, {}).get("failures", 0)
        return failures >= self._threshold

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load_file(self) -> dict:
        if self._cache_file.exists():
            try:
                with self._cache_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read selector cache (%s); starting fresh.", exc)
        return {}

    def _save_file(self) -> None:
        try:
            with self._cache_file.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning("Could not write selector cache: %s", exc)
