"""Run both public site collectors and save their records as JSON Lines."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path

from scraper.common import ScrapedDocument
from scraper.darglobal import collect_darglobal_pages
from scraper.wasalt import collect_wasalt_pages

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DARGLOBAL_URLS = (
    "https://darglobal.co.uk/",
    "https://darglobal.co.uk/about",
    "https://darglobal.co.uk/projects",
    "https://darglobal.co.uk/media",
    "https://darglobal.co.uk/investor-relations",
    "https://darglobal.co.uk/contact",
    "https://darglobal.co.uk/careers",
)
DEFAULT_WASALT_URLS = ("https://wasalt.com/",)
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "collected_documents.jsonl"


def _parse_url_list(value: str | None, defaults: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated URL setting or use its default URL list."""
    if not value:
        return defaults
    return tuple(url.strip() for url in value.split(",") if url.strip())


def collect_all_documents(
    *,
    darglobal_urls: Iterable[str] = DEFAULT_DARGLOBAL_URLS,
    wasalt_urls: Iterable[str] = DEFAULT_WASALT_URLS,
    min_interval_seconds: float = 1.0,
) -> list[ScrapedDocument]:
    """Run both site collectors and merge their results by source URL."""
    darglobal_documents = collect_darglobal_pages(
        darglobal_urls,
        min_interval_seconds=min_interval_seconds,
    )
    wasalt_documents = collect_wasalt_pages(
        wasalt_urls,
        min_interval_seconds=min_interval_seconds,
    )

    # Keep identical text from different sites: each source remains useful for citations.
    unique_by_url: dict[str, ScrapedDocument] = {}
    for document in (*darglobal_documents, *wasalt_documents):
        unique_by_url.setdefault(document.source_url, document)
    return list(unique_by_url.values())


def save_documents_jsonl(
    documents: Iterable[ScrapedDocument], output_path: Path
) -> int:
    """Write one JSON document per line and return the number of records saved."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as output_file:
        for document in documents:
            output_file.write(json.dumps(document.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    """Collect the configured pages and write the raw JSONL file."""
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    darglobal_urls = _parse_url_list(
        os.getenv("DARGLOBAL_START_URLS"), DEFAULT_DARGLOBAL_URLS
    )
    wasalt_urls = _parse_url_list(os.getenv("WASALT_START_URLS"), DEFAULT_WASALT_URLS)
    output_path = Path(os.getenv("SCRAPER_OUTPUT_PATH", str(DEFAULT_OUTPUT_PATH)))

    try:
        documents = collect_all_documents(
            darglobal_urls=darglobal_urls,
            wasalt_urls=wasalt_urls,
        )
        saved_count = save_documents_jsonl(documents, output_path)
    except OSError:
        LOGGER.exception("Could not write collected records to %s", output_path)
        return 1

    LOGGER.info("Saved %d collected records to %s", saved_count, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
