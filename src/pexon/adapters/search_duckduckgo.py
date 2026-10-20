"""Keyless DuckDuckGo HTML search."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from pexon.config.settings import Settings
from pexon.models.research import Source
from pexon.ports.errors import SearchError
from pexon.ports.search import SearchPort

AVAILABLE = True
UNAVAILABLE_REASON = ""
_HREF = re.compile(r'href="([^"]+)"')


class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._mode: str | None = None
        self._href = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class") or ""
        if tag == "a" and "result__a" in classes:
            self._mode = "title"
            self._href = values.get("href") or ""
            self._buffer = []
        elif tag in {"a", "div", "span"} and "result__snippet" in classes:
            self._mode = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._mode:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._mode == "title" and tag == "a":
            self.results.append(
                {"url": self._href, "title": "".join(self._buffer).strip(), "snippet": ""}
            )
            self._mode = None
        elif self._mode == "snippet" and tag in {"a", "div", "span"}:
            if self.results:
                self.results[-1]["snippet"] = "".join(self._buffer).strip()
            self._mode = None


class DuckDuckGoSearch(SearchPort):
    """Scrapes DuckDuckGo's public HTML endpoint; requires no key."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = settings.search_timeout_seconds
        self._headers = {
            "User-Agent": settings.deep_research_user_agent,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
        }

    @property
    def provider(self) -> str:
        return "duckduckgo"

    def search(self, query: str, max_results: int) -> list[Source]:
        """Query DuckDuckGo HTML and parse result anchors."""
        try:
            response = httpx.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "de-de"},
                headers=self._headers,
                timeout=self._timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as exc:
            raise SearchError(f"duckduckgo request failed: {exc}") from exc
        parser = _DDGParser()
        parser.feed(response.text)
        sources: list[Source] = []
        for item in parser.results:
            url = self._unwrap(item["url"])
            if not url.startswith("http"):
                continue
            sources.append(
                Source(
                    url=url,
                    title=html.unescape(item["title"]),
                    snippet=html.unescape(item["snippet"]),
                    provider=self.provider,
                )
            )
            if len(sources) >= max_results:
                break
        if not sources:
            raise SearchError("duckduckgo returned no parseable results")
        return sources

    @staticmethod
    def _unwrap(url: str) -> str:
        if url.startswith("//"):
            url = "https:" + url
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(target)
        return url

    def probe(self) -> bool:
        """One-result real search."""
        return bool(self.search("AI Governance Banken", 1))


# Backwards-compatible alias for the registry's historical adapter name.
DDGSearch = DuckDuckGoSearch
