import os
from pathlib import Path
from dotenv import dotenv_values

# Resolve project root
BASE_DIR = Path(__file__).parent

# Load env: prefer .env, fall back to env.txt
_env = dotenv_values(BASE_DIR / ".env") or dotenv_values(BASE_DIR / "env.txt")

# OpenAI settings
OPENAI_API_KEY: str = _env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_MODEL: str = _env.get("LLM_MODEL", "gpt-4o")
EMBEDDING_MODEL: str = _env.get("EMBEDDING_MODEL", "text-embedding-ada-002")
LLM_BASE_URL: str = _env.get("LLM_BASE_URL", "").strip()
EMBEDDING_BASE_URL: str = _env.get("EMBEDDING_BASE_URL", "").strip()

# Paths
PDF_PATH: Path = BASE_DIR / "1706.03762v7.pdf"
CACHE_DIR: Path = BASE_DIR / "cache"
ELEMENTS_CACHE: Path = CACHE_DIR / "elements.pkl"
FAISS_INDEX_CACHE: Path = CACHE_DIR / "faiss.index"
PAGE_IMAGES_DIR: Path = CACHE_DIR / "page_images"

# Rendering / indexing constants
RENDER_DPI: int = 150
EMBED_DIM: int = 1536
FAISS_TOP_K: int = 5
EMBED_BATCH_SIZE: int = 96
