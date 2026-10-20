"""Optional JavaScript-rendering Playwright fetch adapter."""

from __future__ import annotations

import importlib.util

from pexon.adapters._html_text import html_to_text
from pexon.config.settings import Settings
from pexon.models.research import FetchedPage
from pexon.ports.errors import FetchError
from pexon.ports.fetch import FetchPort

AVAILABLE = importlib.util.find_spec("playwright") is not None
UNAVAILABLE_REASON = "install playwright and run `playwright install chromium`"


class PlaywrightFetcher(FetchPort):
    """Render a page in Chromium and extract visible text."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "playwright"

    def fetch(self, url: str) -> FetchedPage:
        """Render and extract one page."""
        if not AVAILABLE:
            raise FetchError(UNAVAILABLE_REASON)
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self._settings.playwright_headless)
                page = browser.new_page(user_agent=self._settings.fetch_user_agent)
                page.goto(
                    url,
                    timeout=int(self._settings.fetch_timeout_seconds * 1000),
                    wait_until="networkidle",
                )
                title = page.title()
                markup = page.content()
                browser.close()
        except Exception as exc:
            raise FetchError(f"playwright fetch failed for {url}: {exc}") from exc
        _, text = html_to_text(markup)
        return FetchedPage(
            url=url,
            title=title,
            content=text[: self._settings.fetch_max_chars],
            status_code=200,
            content_type="text/html",
            truncated=len(text) > self._settings.fetch_max_chars,
        )

    def probe(self) -> bool:
        """Render the configured probe page."""
        return bool(self.fetch(self._settings.drill_fetch_url).content)
