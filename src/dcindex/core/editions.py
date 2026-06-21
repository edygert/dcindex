"""DEF CON edition parsing. Pure functions — no I/O.

DEF CON 1 was 1993, so ``year = 1992 + number``. Outel publishes MySQL dumps for DC26–DC33
(2018–2025) as ``dc<NN>_mysqldump.txt`` under ``defcon<NN>/``. Keeping edition identity in one place
means the ingester, cache, and parsers never reconstruct slugs inconsistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BASE_YEAR = 1992  # DEF CON 1 -> 1993

# Accept: "dc30", "defcon30", "defcon-30", "def con 30", a bare number "30", or a year "2022".
_NUMBER = re.compile(r"(?:def\s*con|defcon|dc)[\s_-]*0*(\d{1,2})", re.IGNORECASE)
_BARE_NUMBER = re.compile(r"^\s*0*(\d{1,2})\s*$")
_YEAR = re.compile(r"^\s*(19|20)(\d{2})\s*$")
# In a filename/URL, e.g. ".../defcon30/dc30_mysqldump.txt"
_IN_PATH = re.compile(r"(?:defcon|dc)[\s_-]*0*(\d{1,2})", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EditionInfo:
    slug: str  # canonical, e.g. "defcon-30"
    number: int  # DEF CON number, e.g. 30
    year: int  # 4-digit, e.g. 2022
    name: str  # display, e.g. "DEF CON 30"


def _build(number: int) -> EditionInfo:
    return EditionInfo(
        slug=f"defcon-{number}",
        number=number,
        year=_BASE_YEAR + number,
        name=f"DEF CON {number}",
    )


def from_number(number: int) -> EditionInfo:
    return _build(number)


def from_year(year: int) -> EditionInfo | None:
    number = year - _BASE_YEAR
    return _build(number) if number >= 1 else None


def parse_edition(token: str | None) -> EditionInfo | None:
    """Parse an edition from a token like ``dc30``/``defcon-30``/``30``/``2022``. None if absent."""
    if not token:
        return None
    token = token.strip()

    m = _YEAR.match(token)
    if m:
        return from_year(int(m.group(0)))

    m = _NUMBER.search(token) or _BARE_NUMBER.match(token)
    if m:
        number = int(m.group(1))
        if number >= 1:
            return _build(number)
    return None


def edition_from_path(path_or_url: str) -> EditionInfo | None:
    """Best-effort edition from a dump filename/URL, e.g. ``.../defcon30/dc30_mysqldump.txt``."""
    m = _IN_PATH.search(path_or_url)
    if not m:
        return None
    number = int(m.group(1))
    return _build(number) if number >= 1 else None


def dump_url_for(edition: EditionInfo) -> str:
    """The canonical Outel dump URL for an edition."""
    return f"https://defcon.outel.org/defcon{edition.number}/dc{edition.number}_mysqldump.txt"
