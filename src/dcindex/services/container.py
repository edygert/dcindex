"""ServiceContainer — the dependency-injection root.

Builds settings -> connection -> repositories -> services and hands the caller (the CLI today, a TUI
or FastAPI app later) a single object exposing only services. Construct one per process; close it.
"""

from __future__ import annotations

from dcindex.adapters.dump_cache import DumpCache
from dcindex.core.config import Settings, load_settings
from dcindex.core.logging import configure_logging
from dcindex.storage import migrations
from dcindex.storage.db import connect
from dcindex.storage.repositories import Repository
from dcindex.storage.snapshots import SnapshotStore

from .ingest_service import IngestService
from .search_service import SearchService
from .session_service import SessionService
from .stats_service import StatsService


class ServiceContainer:
    def __init__(self, settings: Settings | None = None, *, ensure_schema: bool = True) -> None:
        self.settings = settings or load_settings()
        self.settings.ensure_dirs()
        configure_logging(self.settings.log_file)
        self.conn = connect(self.settings.db_path)
        if ensure_schema:
            migrations.apply(self.conn)
        self.repo = Repository(self.conn)
        self.snapshots = SnapshotStore(self.repo)
        self.dump_cache = DumpCache(self.settings)

        # Public service API — the only surface the frontends touch.
        self.ingest = IngestService(self.settings, self.repo, self.snapshots, self.dump_cache)
        self.search = SearchService(self.repo)
        self.sessions = SessionService(self.repo)
        self.stats = StatsService(self.repo)

    def init_db(self) -> int:
        """Explicitly (re)apply the schema. Returns the schema version."""
        return migrations.apply(self.conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> ServiceContainer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
