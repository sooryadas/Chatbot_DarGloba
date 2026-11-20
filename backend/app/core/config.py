"""Small environment-based settings for the backend service."""

from dataclasses import dataclass
import os
from pathlib import Path


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Configuration shared by the API, retrieval, and answer services."""

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    openrouter_timeout_seconds: int = _read_int("OPENROUTER_TIMEOUT_SECONDS", 45)
    chroma_persist_directory: Path = Path(
        os.getenv("CHROMA_PERSIST_DIRECTORY", "data/chroma")
    )
    chroma_collection_name: str = os.getenv(
        "CHROMA_COLLECTION_NAME", "real_estate_documents"
    )
    embedding_model_name: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )
    retrieval_top_k: int = _read_int("RETRIEVAL_TOP_K", 4)
    chat_history_turn_limit: int = _read_int("CHAT_HISTORY_TURN_LIMIT", 6)


settings = Settings()
