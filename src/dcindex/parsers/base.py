"""Shared parser helpers."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

_WS = re.compile(r"\s+")


def strip_html(value: str | None) -> str | None:
    """Collapse an HTML fragment to readable plain text (used for abstracts/bios)."""
    if not value:
        return None
    text = BeautifulSoup(value, "lxml").get_text(" ")
    text = _WS.sub(" ", text).strip()
    return text or None


def clean(value) -> str | None:
    """Normalize whitespace and decode HTML entities. Coerces non-strings to str."""
    if value is None:
        return None
    text = _WS.sub(" ", html.unescape(str(value))).strip()
    return text or None


def strip_wrapping_quotes(value: str | None) -> str | None:
    """Remove a single layer of literal wrapping quotes.

    Outel stores many field values as e.g. ``'Inaae Kim'`` (the quotes are part of the data, not SQL
    syntax). Strip one matching pair of leading/trailing single or double quotes.
    """
    if value is None:
        return None
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v or None


def extract_links(html_text: str | None, base_url: str | None = None) -> list[tuple[str, str]]:
    """Return ``(text, href)`` pairs for every ``<a href>`` with an http(s) URL in an HTML fragment."""
    if not html_text:
        return []
    soup = BeautifulSoup(html_text, "lxml")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if base_url:
            href = urljoin(base_url, href)
        if not href.lower().startswith(("http://", "https://")):
            continue
        if href in seen:
            continue
        seen.add(href)
        label = _WS.sub(" ", a.get_text(" ")).strip()
        out.append((label, href))
    return out
