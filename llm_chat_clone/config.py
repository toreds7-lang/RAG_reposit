import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI (for embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"

# Local LLM server (OpenAI-compatible, e.g. LM Studio, Ollama, vLLM)
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")

# Fallback model list if the local server is unreachable
FALLBACK_MODELS = ["gpt-oss-20b", "Kimi-K2.5", "GLM-4.5", "HCP-Latest-Model"]

# --- Commercial OpenAI API toggle ---
USE_OPENAI_API = True
OPENAI_CHAT_MODEL = "gpt-4o-mini"
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]

# RAG chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 5

# LLM defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 40
DEFAULT_MAX_TOKENS = 2048


if __name__ == "__main__":
    print(f"OPENAI_API_KEY   : {'set' if OPENAI_API_KEY else 'NOT SET'}")
    print(f"LOCAL_LLM_BASE_URL: {LOCAL_LLM_BASE_URL}")
    print(f"EMBEDDING_MODEL  : {EMBEDDING_MODEL}")
    print(f"FALLBACK_MODELS  : {FALLBACK_MODELS}")
