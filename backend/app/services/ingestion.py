"""Chunk collected pages and store their text and source metadata in ChromaDB."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.services.retrieval import RetrievalError, _get_collection

LOGGER = logging.getLogger(__name__)
DEFAULT_CHUNK_SIZE_WORDS = 180
DEFAULT_CHUNK_OVERLAP_WORDS = 30
UPSERT_BATCH_SIZE = 100


class IngestionError(RuntimeError):
    """Raised when collected data cannot be loaded or indexed."""


def chunk_text(
    text: str,
    *,
    chunk_size_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Split text into readable word chunks with a small overlap between them."""
    if chunk_size_words < 1:
        raise ValueError("chunk_size_words must be greater than zero")
    if overlap_words < 0 or overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be non-negative and smaller than chunk size")

    words = text.split()
    if not words:
        return []

    step_size = chunk_size_words - overlap_words
    chunks: list[str] = []
    for start in range(0, len(words), step_size):
        chunk = " ".join(words[start : start + chunk_size_words])
        if chunk:
            chunks.append(chunk)
        if start + chunk_size_words >= len(words):
            break
    return chunks


def _read_jsonl_records(input_path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield valid JSON objects from a JSON Lines file, with their line numbers."""
    try:
        with input_path.open("r", encoding="utf-8") as input_file:
            for line_number, line in enumerate(input_file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    LOGGER.warning("Skipping invalid JSON on line %d: %s", line_number, exc)
                    continue
                if not isinstance(record, dict):
                    LOGGER.warning("Skipping non-object record on line %d", line_number)
                    continue
                yield line_number, record
    except OSError as exc:
        raise IngestionError(f"Could not read input file {input_path}: {exc}") from exc


def _chunk_id(source_url: str, chunk_index: int) -> str:
    """Create a stable id for a source URL and chunk position."""
    source_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return f"{source_hash}-{chunk_index:06d}"


def _prepare_record(
    record: dict[str, Any],
    *,
    chunk_size_words: int,
    overlap_words: int,
) -> tuple[list[str], list[str], list[dict[str, str | int]]] | None:
    """Validate a raw page and prepare its chunk text, ids, and metadata."""
    source_url = record.get("source_url")
    content = record.get("content")
    if not isinstance(source_url, str) or not source_url.strip():
        return None
    if not isinstance(content, str) or not content.strip():
        return None

    chunks = chunk_text(
        content,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words,
    )
    title = str(record.get("title") or "")
    website_name = str(record.get("website_name") or "")
    collected_at = str(record.get("collected_at") or "")
    ids = [_chunk_id(source_url, index) for index in range(len(chunks))]
    metadatas: list[dict[str, str | int]] = [
        {
            "source_url": source_url,
            "website_name": website_name,
            "title": title,
            "collected_at": collected_at,
            "chunk_index": index,
        }
        for index in range(len(chunks))
    ]
    return chunks, ids, metadatas


def _upsert_page_chunks(
    collection: Any,
    *,
    source_url: str,
    chunks: list[str],
    ids: list[str],
    metadatas: list[dict[str, str | int]],
) -> None:
    """Upsert a page's chunks, then remove stale chunks from an older version."""
    existing = collection.get(where={"source_url": source_url}, include=["metadatas"])
    old_ids = set(existing.get("ids", []))

    for batch_start in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch_end = batch_start + UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[batch_start:batch_end],
            documents=chunks[batch_start:batch_end],
            metadatas=metadatas[batch_start:batch_end],
        )

    stale_ids = old_ids.difference(ids)
    if stale_ids:
        collection.delete(ids=list(stale_ids))


def ingest_jsonl(
    input_path: Path,
    *,
    chunk_size_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> dict[str, int]:
    """Index every valid JSONL page into the configured persistent collection.

    ChromaDB uses the Sentence Transformer embedding function configured by the
    retrieval service, so ingestion and question search share the same vectors.
    """
    if not input_path.is_file():
        raise IngestionError(f"Input file does not exist: {input_path}")

    try:
        collection = _get_collection()
        totals = {"records_read": 0, "records_indexed": 0, "records_skipped": 0, "chunks_indexed": 0}
        for line_number, record in _read_jsonl_records(input_path):
            totals["records_read"] += 1
            prepared = _prepare_record(
                record,
                chunk_size_words=chunk_size_words,
                overlap_words=overlap_words,
            )
            if prepared is None:
                LOGGER.warning("Skipping record missing URL or content on line %d", line_number)
                totals["records_skipped"] += 1
                continue

            chunks, ids, metadatas = prepared
            if not chunks:
                LOGGER.warning("Skipping empty document on line %d", line_number)
                totals["records_skipped"] += 1
                continue

            source_url = str(record["source_url"])
            _upsert_page_chunks(
                collection,
                source_url=source_url,
                chunks=chunks,
                ids=ids,
                metadatas=metadatas,
            )
            totals["records_indexed"] += 1
            totals["chunks_indexed"] += len(chunks)
    except RetrievalError as exc:
        raise IngestionError(str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Ingestion failed")
        raise IngestionError("Could not add documents to ChromaDB.") from exc

    return totals
