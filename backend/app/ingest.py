"""Command-line entry point for indexing collected JSONL documents."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.services.ingestion import IngestionError, ingest_jsonl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "raw" / "collected_documents.jsonl"


def main() -> int:
    """Parse input options, index the records, and print a short summary."""
    parser = argparse.ArgumentParser(
        description="Chunk scraped pages and store them in persistent ChromaDB."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"JSONL input path (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument("--chunk-size-words", type=int, default=180)
    parser.add_argument("--overlap-words", type=int, default=30)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    try:
        summary = ingest_jsonl(
            args.input,
            chunk_size_words=args.chunk_size_words,
            overlap_words=args.overlap_words,
        )
    except (IngestionError, ValueError) as exc:
        logging.error("Ingestion stopped: %s", exc)
        return 1

    logging.info(
        "Indexed %d records into %d chunks (%d skipped).",
        summary["records_indexed"],
        summary["chunks_indexed"],
        summary["records_skipped"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
