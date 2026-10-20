"""Small HTML-to-text extractor shared by fetch adapters."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SPACE = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "iframe"}:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3", "tr"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "iframe"} and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = _SPACE.sub(" ", raw)
        return _BLANKS.sub("\n\n", raw).strip()


def html_to_text(markup: str) -> tuple[str, str]:
    """Return (title, readable text)."""
    parser = _TextParser()
    parser.feed(markup)
    return parser.title.strip(), parser.text()
