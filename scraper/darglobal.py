"""Collector for explicitly selected public DarGlobal pages.

DarGlobal's site is a Next.js SPA whose body content is rendered entirely
by JavaScript.  Plain HTTP requests return an empty shell, so this module
uses Playwright (headless Chromium) to fetch pages after JS hydration.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from urllib.parse import urlsplit

from scraper.common import (
    ScrapedDocument,
    ScrapingError,
    deduplicate_documents,
    make_document,
)
from scraper.dynamic import fetch_rendered_html

LOGGER = logging.getLogger(__name__)
WEBSITE_NAME = "DarGlobal"
ALLOWED_HOSTS = {"darglobal.co.uk", "www.darglobal.co.uk"}

# Wait for the Next.js root to have child content.
NEXT_JS_CONTENT_SELECTOR = "#__next:not(:empty)"


def _is_darglobal_url(url: str) -> bool:
    """Check that a candidate URL belongs to DarGlobal's official domain."""
    parts = urlsplit(url)
    return parts.scheme.lower() in {"http", "https"} and (parts.hostname or "").lower() in ALLOWED_HOSTS


def collect_darglobal_pages(
    page_urls: Iterable[str],
    *,
    min_interval_seconds: float = 2.0,
) -> list[ScrapedDocument]:
    """Collect selected DarGlobal pages using a headless browser.

    The caller provides the page URLs, keeping the initial collection scope
    reviewable. Each page is fetched independently, so one inaccessible URL
    does not prevent other permitted pages from being collected.
    """
    documents: list[ScrapedDocument] = []
    unique_candidates = dict.fromkeys(page_urls)

    for page_url in unique_candidates:
        if not _is_darglobal_url(page_url):
            LOGGER.warning("Skipping URL outside DarGlobal's official domain: %s", page_url)
            continue

        try:
            final_url, title, content = fetch_rendered_html(
                page_url,
                wait_selector=NEXT_JS_CONTENT_SELECTOR,
                min_interval_seconds=min_interval_seconds,
            )
            if not _is_darglobal_url(final_url):
                LOGGER.warning("Skipping redirect outside DarGlobal's domain: %s", final_url)
                continue

            document = make_document(
                source_url=final_url,
                website_name=WEBSITE_NAME,
                title=title,
                content=content,
            )
            if document is not None:
                documents.append(document)
                LOGGER.info("Collected DarGlobal page: %s (%d chars)", final_url, len(content))
            else:
                LOGGER.warning("DarGlobal page rendered but had no text: %s", final_url)
        except (ScrapingError, ValueError) as exc:
            LOGGER.warning("Could not collect DarGlobal page %s: %s", page_url, exc)

    return deduplicate_documents(documents)
