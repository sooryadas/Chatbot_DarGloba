"""Shared helpers for collecting permitted public website content."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)
USER_AGENT = "RealEstateIntelligenceBot/0.1 (public content research)"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0
TRACKING_QUERY_KEYS = {"fbclid", "gclid"}


class ScrapingError(RuntimeError):
    """Raised when a page cannot be safely or reliably collected."""


@dataclass(frozen=True)
class ScrapedDocument:
    """A normalized page record ready for storage or later ingestion."""

    source_url: str
    website_name: str
    title: str
    content: str
    collected_at: str

    def to_dict(self) -> dict[str, str]:
        """Return the record as a JSON-friendly dictionary."""
        return {
            "source_url": self.source_url,
            "website_name": self.website_name,
            "title": self.title,
            "content": self.content,
            "collected_at": self.collected_at,
        }


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})
_retry_policy = Retry(
    total=3,
    connect=3,
    read=3,
    status=3,
    backoff_factor=1,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD"}),
    respect_retry_after_header=True,
)
_session.mount("http://", HTTPAdapter(max_retries=_retry_policy))
_session.mount("https://", HTTPAdapter(max_retries=_retry_policy))

_robots_cache: dict[str, RobotFileParser] = {}
_robots_lock = threading.Lock()
_host_last_request: dict[str, float] = {}
_rate_limit_lock = threading.Lock()


def canonicalize_url(url: str) -> str:
    """Normalize a URL for stable links and duplicate detection."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Expected an absolute HTTP(S) URL, got: {url!r}")

    hostname = (parts.hostname or "").lower()
    if not hostname:
        raise ValueError(f"URL has no hostname: {url!r}")
    netloc = hostname
    if parts.port and not (
        (parts.scheme.lower() == "http" and parts.port == 80)
        or (parts.scheme.lower() == "https" and parts.port == 443)
    ):
        netloc = f"{hostname}:{parts.port}"

    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query_items), ""))


def resolve_url(base_url: str, href: str) -> str:
    """Resolve a page link and normalize it to an absolute HTTP(S) URL."""
    return canonicalize_url(urljoin(base_url, href.strip()))


def _load_robots_parser(origin: str, timeout: int) -> RobotFileParser:
    """Fetch and parse robots.txt, failing closed if it cannot be checked."""
    with _robots_lock:
        cached_parser = _robots_cache.get(origin)
        if cached_parser is not None:
            return cached_parser

        robots_url = f"{origin}/robots.txt"
        try:
            response = _session.get(robots_url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ScrapingError(f"Could not check crawl rules at {robots_url}: {exc}") from exc

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        _robots_cache[origin] = parser
        return parser


def is_allowed_by_robots(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Return whether this crawler may fetch the URL under its robots.txt rules."""
    normalized_url = canonicalize_url(url)
    parts = urlsplit(normalized_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    parser = _load_robots_parser(origin, timeout)
    return parser.can_fetch(USER_AGENT, normalized_url)


def _wait_for_host(host: str, min_interval_seconds: float) -> None:
    """Keep requests to each host at least the configured interval apart."""
    with _rate_limit_lock:
        now = time.monotonic()
        wait_seconds = min_interval_seconds - (now - _host_last_request.get(host, 0.0))
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _host_last_request[host] = time.monotonic()


def fetch_html(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    min_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
) -> tuple[str, str]:
    """Fetch a permitted HTML page, returning its final URL and response body.

    Robots rules are checked before the page request. A failed robots.txt lookup
    stops collection so a network error cannot accidentally be treated as permission.
    """
    normalized_url = canonicalize_url(url)
    parts = urlsplit(normalized_url)
    if not is_allowed_by_robots(normalized_url, timeout=timeout):
        raise ScrapingError(f"robots.txt disallows collection of {normalized_url}")

    _wait_for_host(parts.netloc, max(0.0, min_interval_seconds))
    try:
        response = _session.get(normalized_url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("Request failed for %s: %s", normalized_url, exc)
        raise ScrapingError(f"Could not fetch {normalized_url}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ScrapingError(f"Expected an HTML page at {normalized_url}, got {content_type!r}")
    return response.url, response.text


def html_to_text(html: str) -> tuple[str, str]:
    """Extract a page title and readable text, dropping non-content elements."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for element in soup(
        ["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]
    ):
        element.decompose()
    text = " ".join(soup.stripped_strings)
    return title, " ".join(text.split())


def make_document(
    *, source_url: str, website_name: str, title: str, content: str
) -> ScrapedDocument | None:
    """Build a normalized source record, skipping pages without useful text."""
    normalized_content = " ".join(content.split())
    if not normalized_content:
        LOGGER.info("Skipping empty page: %s", source_url)
        return None
    return ScrapedDocument(
        source_url=canonicalize_url(source_url),
        website_name=website_name.strip(),
        title=" ".join(title.split()),
        content=normalized_content,
        collected_at=datetime.now(timezone.utc).isoformat(),
    )


def deduplicate_documents(
    documents: list[ScrapedDocument],
) -> list[ScrapedDocument]:
    """Keep the first record for each canonical URL or identical page content."""
    unique_documents: list[ScrapedDocument] = []
    seen_urls: set[str] = set()
    seen_content: set[str] = set()
    for document in documents:
        content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
        if document.source_url in seen_urls or content_hash in seen_content:
            continue
        seen_urls.add(document.source_url)
        seen_content.add(content_hash)
        unique_documents.append(document)
    return unique_documents
