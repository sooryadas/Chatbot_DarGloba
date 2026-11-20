"""Playwright-based fetcher for JavaScript-rendered pages."""

from __future__ import annotations

import logging
import time
import threading

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

from scraper.common import (
    ScrapingError,
    USER_AGENT,
    canonicalize_url,
    is_allowed_by_robots,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_RENDER_TIMEOUT_MS = 30_000
DEFAULT_WAIT_SELECTOR = "body"
MIN_RENDERED_TEXT_CHARACTERS = 120

_host_last_request: dict[str, float] = {}
_rate_limit_lock = threading.Lock()


def _wait_for_host(host: str, min_interval_seconds: float) -> None:
    """Keep requests to each host at least the configured interval apart."""
    with _rate_limit_lock:
        now = time.monotonic()
        wait_seconds = min_interval_seconds - (
            now - _host_last_request.get(host, 0.0)
        )
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _host_last_request[host] = time.monotonic()


def fetch_rendered_html(
    url: str,
    *,
    wait_selector: str = DEFAULT_WAIT_SELECTOR,
    render_timeout_ms: int = DEFAULT_RENDER_TIMEOUT_MS,
    min_interval_seconds: float = 1.0,
) -> tuple[str, str, str]:
    """Fetch a JS-rendered page and return its URL, title, and visible text.

    Returns the final URL after redirects, the document title, and visible body text.
    Robots rules are checked before the page request.
    """
    from urllib.parse import urlsplit

    normalized_url = canonicalize_url(url)
    parts = urlsplit(normalized_url)

    if not is_allowed_by_robots(normalized_url):
        raise ScrapingError(f"robots.txt disallows collection of {normalized_url}")

    _wait_for_host(parts.netloc, max(0.0, min_interval_seconds))

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                context = browser.new_context(user_agent=USER_AGENT)
                try:
                    page = context.new_page()
                    response = page.goto(
                        normalized_url,
                        wait_until="domcontentloaded",
                        timeout=render_timeout_ms,
                    )
                    if response is None or response.status >= 400:
                        status = response.status if response else "no response"
                        raise ScrapingError(
                            f"Failed to load {normalized_url}: HTTP {status}"
                        )

                    page.wait_for_selector(wait_selector, timeout=render_timeout_ms)
                    # Wait for visible copy, not merely an empty Next.js root element.
                    page.wait_for_function(
                        "minChars => document.body && "
                        "document.body.innerText.trim().length >= minChars",
                        arg=MIN_RENDERED_TEXT_CHARACTERS,
                        timeout=render_timeout_ms,
                    )
                    final_url = page.url
                    title = page.title()
                    visible_text = page.locator("body").inner_text()
                finally:
                    context.close()
            finally:
                browser.close()
    except ScrapingError:
        raise
    except PlaywrightTimeout as exc:
        raise ScrapingError(f"Timed out rendering {normalized_url}") from exc
    except PlaywrightError as exc:
        LOGGER.warning("Playwright failed for %s: %s", normalized_url, exc)
        raise ScrapingError(f"Could not render {normalized_url}: {exc}") from exc

    return final_url, title, visible_text
