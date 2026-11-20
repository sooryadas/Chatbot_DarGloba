"""Collector for explicitly selected public Wasalt pages."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from urllib.parse import urlsplit

from scraper.common import (
    ScrapedDocument,
    ScrapingError,
    deduplicate_documents,
    fetch_html,
    html_to_text,
    make_document,
)

LOGGER = logging.getLogger(__name__)
WEBSITE_NAME = "Wasalt"
ALLOWED_HOSTS = {
    "wasalt.com",
    "www.wasalt.com",
    "wasalt.sa",
    "www.wasalt.sa",
}


def _is_wasalt_url(url: str) -> bool:
    """Check that a candidate URL belongs to an official Wasalt domain."""
    parts = urlsplit(url)
    return (
        parts.scheme.lower() in {"http", "https"}
        and (parts.hostname or "").lower() in ALLOWED_HOSTS
    )


def collect_wasalt_pages(
    page_urls: Iterable[str],
    *,
    min_interval_seconds: float = 1.0,
) -> list[ScrapedDocument]:
    """Collect selected Wasalt pages that its robots.txt permits.

    The caller supplies URLs to keep the initial crawl scope reviewable.
    Arabic and English page text are both preserved as returned by the site.
    Each page is handled independently so a failed page does not stop the rest.
    """
    documents: list[ScrapedDocument] = []
    unique_candidates = dict.fromkeys(page_urls)

    for page_url in unique_candidates:
        if not _is_wasalt_url(page_url):
            LOGGER.warning("Skipping URL outside Wasalt's official domains: %s", page_url)
            continue

        try:
            final_url, html = fetch_html(
                page_url,
                min_interval_seconds=min_interval_seconds,
            )
            if not _is_wasalt_url(final_url):
                LOGGER.warning("Skipping redirect outside Wasalt's domains: %s", final_url)
                continue

            title, content = html_to_text(html)
            document = make_document(
                source_url=final_url,
                website_name=WEBSITE_NAME,
                title=title,
                content=content,
            )
            if document is not None:
                documents.append(document)
        except (ScrapingError, ValueError) as exc:
            LOGGER.warning("Could not collect Wasalt page %s: %s", page_url, exc)

    return deduplicate_documents(documents)
