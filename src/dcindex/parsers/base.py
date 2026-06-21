"""Shared parser helpers."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

import ftfy
from bs4 import BeautifulSoup

_WS = re.compile(r"\s+")
# C0 (except tab/newline/CR) and C1 control characters. C1 codes like U+009D are interpreted as
# terminal escape sequences (OSC), which silently swallow following text in a terminal — they must
# never reach stored fields. ftfy removes most as a side effect of repair; this is the safety net.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _repair(text: str) -> str:
    """Repair mojibake (the Outel dumps are double-encoded UTF-8, e.g. ``â€™`` -> ``'``) and drop
    stray control characters that would corrupt terminal output."""
    return _CONTROL.sub("", ftfy.fix_text(text))


def strip_html(value: str | None) -> str | None:
    """Collapse an HTML fragment to readable plain text (used for abstracts/bios)."""
    if not value:
        return None
    text = BeautifulSoup(value, "lxml").get_text(" ")
    text = _WS.sub(" ", _repair(text)).strip()
    return text or None


def clean(value) -> str | None:
    """Normalize whitespace, decode HTML entities, and repair encoding. Coerces non-strings to str."""
    if value is None:
        return None
    text = _WS.sub(" ", _repair(html.unescape(str(value)))).strip()
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
