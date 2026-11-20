"""Find relevant source chunks in the persistent ChromaDB collection."""

from functools import lru_cache
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.core.config import settings

LOGGER = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Raised when the vector store cannot be queried."""


@lru_cache(maxsize=1)
def _get_collection() -> Any:
    """Open the configured persistent collection and embedding model."""
    try:
        Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.chroma_persist_directory))
        embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model_name
        )
        return client.get_or_create_collection(
            name=settings.chroma_collection_name,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        LOGGER.exception("Could not initialize ChromaDB")
        raise RetrievalError("The document store is unavailable.") from exc


def retrieve_documents(query: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Return the closest document chunks with their original source metadata."""
    collection = _get_collection()
    result_limit = max(1, limit or settings.retrieval_top_k)
    try:
        results = collection.query(
            query_texts=[query],
            n_results=result_limit,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        LOGGER.exception("ChromaDB query failed")
        raise RetrievalError("Could not search the document store.") from exc

    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []
    matches: list[dict[str, Any]] = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        matches.append(
            {
                "content": text,
                "title": metadata.get("title", ""),
                "source_url": metadata.get("source_url", ""),
                "website_name": metadata.get("website_name", ""),
                "distance": distances[index] if index < len(distances) else None,
            }
        )
    return [match for match in matches if match["content"] and match["source_url"]]
