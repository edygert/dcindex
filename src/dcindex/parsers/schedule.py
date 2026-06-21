"""Map parsed Outel DEF CON dump tables into the EventDTO contract.

Verified against real dumps (DC26–DC33). The schema drifts year to year, so this is a tolerant
**registry of per-table mappers** keyed by table name; each year maps whatever tables it has. The
core (``events`` + ``speakers``) is identical every year:

* ``events``  — talks/briefings. Columns: day, hour, starttime, endtime, continuation, village
  (track tag), track (**location**), title, speaker, hash, desc (HTML), modflag, autoincre.
  ``continuation='Y'`` rows are multi-hour repeats of the same talk → deduped by ``hash``.
* ``speakers`` — joined to a talk by the shared ``hash`` (not a numeric FK).

Other activity tables (demolabs/workshops/training/contests/villages, and the DC32/33 consolidated
``pages``) carry explicit URL columns plus links embedded as HTML in their description. ``vendors``
and CMS/utility tables are skipped (and reported), per the configured scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dcindex.core.editions import EditionInfo
from dcindex.core.models import SessionCategory
from dcindex.dto.contracts import EventDTO, MaterialDTO, SessionDTO, SpeakerDTO

from .base import clean, extract_links, strip_html, strip_wrapping_quotes
from .materials import classify
from .mysqldump import ParsedTable

# table name (lowercase) -> session category
SESSION_TABLES: dict[str, SessionCategory] = {
    "events": SessionCategory.TALK,
    "demolabs": SessionCategory.DEMOLAB,
    "workshops": SessionCategory.WORKSHOP,
    "training": SessionCategory.TRAINING,
    "contests": SessionCategory.CONTEST,
    "villages": SessionCategory.VILLAGE,
    "pages": SessionCategory.PAGE,
}

# Recognized non-session tables we deliberately do not map (so they don't show up as "unknown").
SKIP_TABLES = {
    "speakers",  # consumed as the talk speaker index, not a session table
    "vendors",  # excluded per scope (no downloadable materials)
    "articles", "documents", "map_matrix", "dcannouncements", "callfors", "pge", "pages_meta",
    "schema_version",
}

# Explicit URL-bearing columns on the non-talk activity tables (lowercased), in display order.
_URL_COLUMNS = [
    ("forumpage", "Forum"),
    ("forumarticle", "Forum"),
    ("webpage", "Website"),
    ("weblink", "Link"),
    ("linkurl", "Link"),
    ("homepage", "Home page"),
    ("schedulepage", "Schedule"),
    ("dcforumpage", "DEF CON forum"),
    ("dcvillagespage", "DEF CON villages"),
    ("dcvillagedesclink", "Village info"),
    ("villagelogourl", "Logo"),
    ("videostreamurl", "Video stream"),
    ("twitter", "Twitter"),
    ("link", "Link"),
] + [(f"socialmedialink{i}", "Social") for i in range(1, 8)]


@dataclass
class MapResult:
    event: EventDTO
    tables_seen: int = 0
    rows_seen: int = 0
    mapped_tables: list[str] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)


def _lower_rows(table: ParsedTable) -> list[dict]:
    return [{(k.lower() if isinstance(k, str) else k): v for k, v in row.items()} for row in table.rows]


def _pick(row: dict, *names: str) -> str | None:
    for n in names:
        if n in row:
            v = strip_wrapping_quotes(clean(row[n]))
            if v:
                return v
    return None


def _as_url(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if v.lower().startswith(("http://", "https://")):
        return v
    # Accept a bare domain like "www.example.com/foo" (Outel stores some links without a scheme).
    if re.match(r"^[\w-]+\.[\w.-]+(?:/\S*)?$", v) and " " not in v:
        return "https://" + v
    return None


def _dedupe_materials(materials: list[MaterialDTO]) -> list[MaterialDTO]:
    seen: set[str] = set()
    out: list[MaterialDTO] = []
    for m in materials:
        if m.url in seen:
            continue
        seen.add(m.url)
        out.append(m)
    return out


def _links_from_columns(row: dict) -> list[MaterialDTO]:
    out: list[MaterialDTO] = []
    for col, label in _URL_COLUMNS:
        if col not in row:
            continue
        url = _as_url(strip_wrapping_quotes(clean(row[col])))
        if url:
            out.append(MaterialDTO(title=label, url=url, kind=classify(url, hint=label)))
    return out


def _links_from_html(value) -> list[MaterialDTO]:
    text = strip_wrapping_quotes(value if isinstance(value, str) else None) or (
        value if isinstance(value, str) else ""
    )
    out: list[MaterialDTO] = []
    for label, href in extract_links(text):
        out.append(MaterialDTO(title=label or "Link", url=href, kind=classify(href, hint=label)))
    return out


def _forum_source(materials: list[MaterialDTO]) -> str:
    """Pick a representative source URL: prefer a forum.defcon.org link, else the first link."""
    for m in materials:
        host = (urlparse(m.url).hostname or "").lower()
        if "forum.defcon.org" in host:
            return m.url
    return materials[0].url if materials else ""


# --------------------------------------------------------------------------- speaker index

def _build_speaker_index(table: ParsedTable | None) -> dict[str, list[SpeakerDTO]]:
    index: dict[str, list[SpeakerDTO]] = {}
    if table is None:
        return index
    for row in _lower_rows(table):
        h = clean(row.get("hash"))
        name = strip_wrapping_quotes(clean(row.get("speaker")))
        if not h or not name:
            continue
        bucket = index.setdefault(h, [])
        if all(sp.name != name for sp in bucket):
            bucket.append(SpeakerDTO(name=name))
    return index


def _inline_speakers(value: str | None) -> list[SpeakerDTO]:
    text = strip_wrapping_quotes(clean(value))
    if not text:
        return []
    parts = re.split(r"\s*(?:,|&| and )\s*", text)
    out: list[SpeakerDTO] = []
    for p in parts:
        p = p.strip()
        if p and all(sp.name != p for sp in out):
            out.append(SpeakerDTO(name=p))
    return out


# --------------------------------------------------------------------------- per-table mappers

def _format_when(row: dict) -> str | None:
    day = clean(row.get("day")) or ""
    day = day.split("_", 1)[-1] if "_" in day else day
    start = clean(row.get("starttime"))
    end = clean(row.get("endtime"))
    span = f"{start}-{end}" if start and end else (start or "")
    when = f"{day} {span}".strip()
    return when or None


def _map_events(table: ParsedTable, speaker_index: dict[str, list[SpeakerDTO]]) -> list[SessionDTO]:
    sessions: list[SessionDTO] = []
    seen_hashes: set[str] = set()
    for row in _lower_rows(table):
        if str(clean(row.get("continuation")) or "").upper() == "Y":
            continue
        h = clean(row.get("hash"))
        title = _pick(row, "title")
        if not title:
            continue
        slug = h or title
        if slug in seen_hashes:
            continue
        seen_hashes.add(slug)

        abstract = strip_html(strip_wrapping_quotes(row.get("desc")) or row.get("desc"))
        speakers = speaker_index.get(h or "", []) or _inline_speakers(row.get("speaker"))
        materials = _dedupe_materials(_links_from_html(row.get("desc")))
        sessions.append(
            SessionDTO(
                slug=slug,
                title=title,
                category=SessionCategory.TALK,
                abstract=abstract,
                track=_pick(row, "village"),
                room=_pick(row, "track"),
                starts_at=_format_when(row),
                source_url=_forum_source(materials),
                speakers=speakers,
                materials=materials,
            )
        )
    return sessions


def _map_activity(table: ParsedTable, category: SessionCategory) -> list[SessionDTO]:
    sessions: list[SessionDTO] = []
    for row in _lower_rows(table):
        title = _pick(row, "name", "title")
        if not title:
            continue
        ident = clean(row.get("id")) or clean(row.get("autoincre")) or title
        desc_raw = row.get("descript") if "descript" in row else row.get("description")
        if "villagedesc" in row:
            desc_raw = row.get("villagedesc")
        abstract = strip_html(strip_wrapping_quotes(desc_raw) or desc_raw)

        materials = _dedupe_materials(_links_from_columns(row) + _links_from_html(desc_raw))
        track = _pick(row, "pagetype", "tagname")
        room = _pick(row, "location", "villageloc", "talkloc", "venue")
        sessions.append(
            SessionDTO(
                slug=f"{category.value}-{ident}",
                title=title,
                category=category,
                abstract=abstract,
                track=track,
                room=room,
                starts_at=_pick(row, "sessiontimes"),
                source_url=_forum_source(materials),
                speakers=[],
                materials=materials,
            )
        )
    return sessions


# --------------------------------------------------------------------------- entry point

def map_tables(
    tables: dict[str, ParsedTable],
    edition: EditionInfo,
    *,
    categories: set[SessionCategory] | None = None,
    source_url: str = "",
) -> MapResult:
    """Map parsed dump tables into a single EventDTO for ``edition``."""
    include = categories or set(SESSION_TABLES.values())
    speaker_index = _build_speaker_index(tables.get("speakers"))

    event = EventDTO(
        slug=edition.slug,
        name=edition.name,
        number=edition.number,
        year=edition.year,
        source_url=source_url,
    )
    result = MapResult(event=event)

    for key, table in tables.items():
        result.tables_seen += 1
        result.rows_seen += len(table.rows)
        category = SESSION_TABLES.get(key)
        if category is None or category not in include:
            if key not in SKIP_TABLES:
                result.skipped_tables.append(table.name)
            continue
        if not table.rows:
            continue
        if category is SessionCategory.TALK:
            sessions = _map_events(table, speaker_index)
        else:
            sessions = _map_activity(table, category)
        if sessions:
            event.sessions.extend(sessions)
            result.mapped_tables.append(table.name)

    return result
