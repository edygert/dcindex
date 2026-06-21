"""Pydantic contracts exchanged across the service boundary.

Parsers produce these; services consume/return them; storage maps them to rows. They are also
valid FastAPI request/response models, so a deferred web layer wraps the same services unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from dcindex.core.models import MaterialKind, SessionCategory, SourceName


class SpeakerDTO(BaseModel):
    name: str
    affiliation: str | None = None
    bio: str | None = None


class MaterialDTO(BaseModel):
    """A *link* to supplemental material. dcindex stores the URL only; nothing is downloaded."""

    title: str
    url: str
    kind: MaterialKind = MaterialKind.OTHER


class SessionDTO(BaseModel):
    slug: str  # stable within an event (Outel `hash`, or `<category>-<id>`)
    title: str
    category: SessionCategory = SessionCategory.TALK
    abstract: str | None = None
    track: str | None = None  # village / pagetype tag
    room: str | None = None  # location string
    starts_at: str | None = None  # raw text as published (e.g. "Saturday 14:30-15:30")
    source_url: str = ""
    speakers: list[SpeakerDTO] = Field(default_factory=list)
    materials: list[MaterialDTO] = Field(default_factory=list)


class SessionDetailDTO(BaseModel):
    """A fully-resolved session for display (the `show` command / future detail screen)."""

    id: int
    slug: str
    event_name: str
    event_slug: str
    title: str
    category: SessionCategory = SessionCategory.TALK
    abstract: str | None = None
    track: str | None = None
    room: str | None = None
    starts_at: str | None = None
    source_url: str = ""
    speakers: list[SpeakerDTO] = Field(default_factory=list)
    materials: list[MaterialDTO] = Field(default_factory=list)


class EventDTO(BaseModel):
    slug: str  # canonical edition slug, e.g. "defcon-30"
    name: str  # display, e.g. "DEF CON 30"
    number: int | None = None
    year: int | None = None
    source_url: str = ""
    sessions: list[SessionDTO] = Field(default_factory=list)


class IngestReport(BaseModel):
    source: SourceName
    edition: str | None = None
    from_cache: bool = False

    tables_seen: int = 0
    rows_seen: int = 0
    events_upserted: int = 0
    sessions_upserted: int = 0
    speakers_upserted: int = 0
    materials_upserted: int = 0

    # Per-category session counts (e.g. {"talk": 612, "village": 30}).
    by_category: dict[str, int] = Field(default_factory=dict)

    # Diagnostics — flag missing data and tables we recognized but did not map.
    sessions_without_abstract: int = 0
    sessions_without_speakers: int = 0
    sessions_without_materials: int = 0
    skipped_tables: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)

    errors: list[str] = Field(default_factory=list)
    status: str = "ok"
