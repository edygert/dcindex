"""Exception hierarchy for dcindex.

Errors are deliberately granular so the ingester can decide retry/abort policy and so the
(future) TUI/API can surface actionable messages.
"""

from __future__ import annotations


class DcIndexError(Exception):
    """Base class for all dcindex errors."""


class ConfigError(DcIndexError):
    """Invalid or missing configuration."""


class DumpParseError(DcIndexError):
    """A MySQL dump could not be parsed into tables/rows."""

    def __init__(self, message: str, *, table: str | None = None) -> None:
        super().__init__(message)
        self.table = table


class ParseError(DcIndexError):
    """Parsed tables did not match any known DEF CON schedule shape."""


class FetchError(DcIndexError):
    """A network fetch failed (timeout, connection, unexpected status)."""

    def __init__(self, message: str, *, url: str | None = None, status: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status = status


class StorageError(DcIndexError):
    """A database/storage operation failed."""
