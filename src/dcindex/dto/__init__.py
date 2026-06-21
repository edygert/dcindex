"""Service-boundary contracts (pydantic). The only data shapes the CLI/ingest/TUI/API exchange."""

from .contracts import (
    EventDTO,
    IngestReport,
    MaterialDTO,
    SessionDetailDTO,
    SessionDTO,
    SpeakerDTO,
)

__all__ = [
    "EventDTO",
    "IngestReport",
    "MaterialDTO",
    "SessionDetailDTO",
    "SessionDTO",
    "SpeakerDTO",
]
