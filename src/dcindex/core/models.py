"""Small value types + enums shared across layers.

Richer data carriers (Event/Session/Speaker/Material) live in ``dcindex.dto.contracts`` as pydantic
models — they double as the service-boundary contract and (later) FastAPI response models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceName(StrEnum):
    DUMP = "dump"  # a MySQL dump read from a local file (ingest-dump)
    FILE = "file"  # a generic file on disk
    URL = "url"  # a dump fetched over HTTP and cached (ingest-url)


class SessionCategory(StrEnum):
    """The kind of schedule activity a session represents (one Outel table family each)."""

    TALK = "talk"  # events table
    DEMOLAB = "demolab"  # demolabs table
    WORKSHOP = "workshop"  # workshops table
    TRAINING = "training"  # training table
    CONTEST = "contest"  # contests table
    VILLAGE = "village"  # villages table
    PAGE = "page"  # DC32/33 consolidated `pages` table


class MaterialKind(StrEnum):
    PDF = "pdf"
    SLIDES = "slides"
    WHITEPAPER = "whitepaper"
    VIDEO = "video"
    AUDIO = "audio"
    TOOL = "tool"  # code repos, releases (e.g. github)
    ARCHIVE = "archive"
    FORUM = "forum"  # forum.defcon.org thread/article
    SOCIAL = "social"  # twitter/discord/linkedin/etc.
    LINK = "link"  # a generic web page
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Outcome of reading a dump, regardless of which reader produced it.

    ``text`` holds the raw dump SQL. ``url`` is a provenance label (file path or HTTP URL).
    """

    url: str
    text: str
    source: SourceName
    from_cache: bool = False
