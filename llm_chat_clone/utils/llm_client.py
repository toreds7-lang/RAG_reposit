from typing import Generator
import streamlit as st
from openai import OpenAI
import httpx
import config


@st.cache_data(ttl=60, show_spinner=False)
def fetch_available_models(base_url: str, api_key: str) -> list:
    """
    Discover models from the local OpenAI-compatible API.
    Falls back to the hardcoded list if the server is unreachable.
    """
    try:
        resp = httpx.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=3.0,
        )
        resp.raise_for_status()
        data = resp.json()
        models = [m["id"] for m in data.get("data", [])]
        return models if models else config.FALLBACK_MODELS
    except Exception:
        return config.FALLBACK_MODELS


def get_local_client() -> OpenAI:
    """Return an OpenAI client pointed at the local LLM server."""
    return OpenAI(
        base_url=config.LOCAL_LLM_BASE_URL,
        api_key=config.LOCAL_LLM_API_KEY,
    )


def get_openai_client() -> OpenAI:
    """Return an OpenAI client pointed at the commercial OpenAI API."""
    return OpenAI(api_key=config.OPENAI_API_KEY)


def stream_chat(
    client: OpenAI,
    model: str,
    messages: list,
    params: dict,
) -> Generator[str, None, None]:
    """
    Stream chat completions from the local model.
    Checks st.session_state["stop_requested"] on every chunk.
    Passes top_k via extra_body; falls back silently if the server rejects it.
    """
    extra_body = {"top_k": params["top_k"]} if params.get("top_k") else {}

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            top_p=params["top_p"],
            extra_body=extra_body if extra_body else None,
        )
    except Exception:
        # Retry without extra_body if the server rejected it
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            top_p=params["top_p"],
        )

    try:
        for chunk in stream:
            if st.session_state.get("stop_requested", False):
                break
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    finally:
        stream.close()
