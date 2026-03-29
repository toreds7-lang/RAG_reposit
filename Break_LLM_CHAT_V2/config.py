"""
Central configuration for the LangChain agent system (V2).
All settings are loaded from environment variables (or a .env file).
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


def _bool(val: str, default: bool) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


@dataclass
class AgentConfig:
    # Orchestrator LLM settings (사내 API LLM — 낮은 성능)
    vllm_base_url: str = ""        # VLLM_BASE_URL  e.g. "http://10.0.0.5:8000/v1"
    vllm_model: str = ""           # VLLM_MODEL     e.g. "mistral-7b-instruct"
    vllm_api_key: str = "EMPTY"    # VLLM_API_KEY   usually ignored by vLLM

    # Web chat LLM settings (고성능 reasoning 모델)
    llm_chat_url: str = ""         # LLM_CHAT_URL   e.g. "http://internal-llm-chat/"
    llm_chat_headless: bool = False
    llm_chat_page_load_wait: int = 3

    # Agent behavior
    agent_max_iterations: int = 10
    agent_verbose: bool = True
    agent_use_react: str = "auto"  # "auto" | "true" | "false"

    # Selector auto-discovery
    selector_discovery_enabled: bool = True
    selector_html_max_chars: int = 60000

    # Self-healing selector
    selector_cache_file: str = "selector_cache.json"
    selector_failure_threshold: int = 3  # N회 실패 시 자동 재발견

    # Trace logging
    trace_log_dir: str = "trace_log"


def load_config() -> AgentConfig:
    """Load AgentConfig from environment variables."""
    cfg = AgentConfig(
        vllm_base_url=os.environ.get("VLLM_BASE_URL", ""),
        vllm_model=os.environ.get("VLLM_MODEL", ""),
        vllm_api_key=os.environ.get("VLLM_API_KEY", "EMPTY"),

        llm_chat_url=os.environ.get("LLM_CHAT_URL", ""),
        llm_chat_headless=_bool(os.environ.get("LLM_CHAT_HEADLESS"), False),
        llm_chat_page_load_wait=int(os.environ.get("LLM_CHAT_PAGE_LOAD_WAIT", "3")),

        agent_max_iterations=int(os.environ.get("AGENT_MAX_ITERATIONS", "10")),
        agent_verbose=_bool(os.environ.get("AGENT_VERBOSE"), True),
        agent_use_react=os.environ.get("AGENT_USE_REACT", "auto"),

        selector_discovery_enabled=_bool(os.environ.get("SELECTOR_DISCOVERY_ENABLED"), True),
        selector_html_max_chars=int(os.environ.get("SELECTOR_HTML_MAX_CHARS", "60000")),

        selector_cache_file=os.environ.get("SELECTOR_CACHE_FILE", "selector_cache.json"),
        selector_failure_threshold=int(os.environ.get("SELECTOR_FAILURE_THRESHOLD", "3")),

        trace_log_dir=os.environ.get("TRACE_LOG_DIR", "trace_log"),
    )

    missing = []
    if not cfg.vllm_base_url:
        missing.append("VLLM_BASE_URL")
    if not cfg.vllm_model:
        missing.append("VLLM_MODEL")
    if not cfg.llm_chat_url:
        missing.append("LLM_CHAT_URL")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in the values."
        )

    return cfg
