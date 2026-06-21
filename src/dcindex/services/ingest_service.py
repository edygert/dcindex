"""IngestService — read a dump -> parse -> map -> persist, producing an IngestReport.

Two entry points share one core flow:

* ``ingest_dump(path)`` — a local dump file (offline).
* ``ingest_url(url, refresh=...)`` — fetch a published Outel dump text **once**, cache it under
  ``dumps/``, then ingest the cached copy. Re-running ingests from cache with no network call.

The only data fetched over the network is the dump SQL text itself; no media or file assets are ever
downloaded. Material links are recorded as metadata only.
"""

from __future__ import annotations

from collections.abc import Callable

from dcindex.adapters.dump_cache import DumpCache
from dcindex.adapters.dump_reader import read_dump
from dcindex.core.config import Settings
from dcindex.core.editions import EditionInfo, edition_from_path, parse_edition
from dcindex.core.errors import DcIndexError
from dcindex.core.logging import get_logger
from dcindex.core.models import FetchResult, SessionCategory
from dcindex.dto.contracts import IngestReport
from dcindex.parsers import schedule
from dcindex.parsers.mysqldump import parse_dump
from dcindex.storage.repositories import Repository
from dcindex.storage.snapshots import SnapshotStore

Progress = Callable[[str], None]


class IngestService:
    def __init__(
        self,
        settings: Settings,
        repo: Repository,
        snapshots: SnapshotStore,
        dump_cache: DumpCache,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.snapshots = snapshots
        self.dump_cache = dump_cache
        self.log = get_logger()

    # ------------------------------------------------------------------ public API
    def ingest_dump(
        self,
        path: str,
        *,
        edition: str | None = None,
        categories: list[str] | None = None,
        progress: Progress | None = None,
    ) -> IngestReport:
        ed = self._resolve_edition(edition, path)
        say = progress or (lambda _m: None)
        say(f"{ed.slug}: reading {path}")
        result = read_dump(path)
        return self._ingest(result, ed, categories, say)

    def ingest_url(
        self,
        url: str | None = None,
        *,
        edition: str | None = None,
        refresh: bool = False,
        categories: list[str] | None = None,
        progress: Progress | None = None,
    ) -> IngestReport:
        ed = self._resolve_edition(edition, url or "")
        say = progress or (lambda _m: None)
        fetch_url = url or _default_dump_url(ed)
        if self.dump_cache.is_cached(ed) and not refresh:
            say(f"{ed.slug}: using cached dump")
        else:
            say(f"{ed.slug}: downloading {fetch_url}")
        result = self.dump_cache.fetch_cached(fetch_url, ed, refresh=refresh, notify=say)
        return self._ingest(result, ed, categories, say)

    # ------------------------------------------------------------------ core flow
    def _ingest(
        self,
        result: FetchResult,
        edition: EditionInfo,
        categories: list[str] | None,
        say: Progress,
    ) -> IngestReport:
        say(f"{edition.slug}: parsing dump")
        tables = parse_dump(result.text)
        cats = _category_set(categories)

        say(f"{edition.slug}: mapping {len(tables)} tables")
        mapped = schedule.map_tables(
            tables, edition, categories=cats, source_url=result.url
        )
        event = mapped.event

        say(f"{edition.slug}: saving {len(event.sessions)} sessions")
        source_id = self.repo.get_or_create_source(result.source.value)
        snapshot_id = self.snapshots.record(result.url, result.text, path=result.url)
        counts = self.repo.save_event(event, source_id, snapshot_id)
        self.repo.prune_orphan_speakers()
        self.repo.commit()

        report = IngestReport(
            source=result.source,
            edition=edition.slug,
            from_cache=result.from_cache,
            tables_seen=mapped.tables_seen,
            rows_seen=mapped.rows_seen,
            events_upserted=counts.events,
            sessions_upserted=counts.sessions,
            speakers_upserted=counts.speakers,
            materials_upserted=counts.materials,
            by_category=dict(counts.by_category),
            skipped_tables=sorted(set(mapped.skipped_tables)),
        )
        self._add_diagnostics(report, event)
        self.log.info(
            "ingested %s: %d sessions, %d speakers, %d materials (%d tables, %d skipped)",
            edition.slug, report.sessions_upserted, report.speakers_upserted,
            report.materials_upserted, report.tables_seen, len(report.skipped_tables),
        )
        return report

    @staticmethod
    def _add_diagnostics(report: IngestReport, event) -> None:
        report.sessions_without_abstract = sum(1 for s in event.sessions if not s.abstract)
        report.sessions_without_speakers = sum(1 for s in event.sessions if not s.speakers)
        report.sessions_without_materials = sum(1 for s in event.sessions if not s.materials)
        if not event.sessions:
            report.anomalies.append("0 sessions mapped from dump")
            report.status = "error"
        if report.skipped_tables:
            report.anomalies.append("unmapped tables: " + ", ".join(report.skipped_tables))

    @staticmethod
    def _resolve_edition(edition: str | None, path_or_url: str) -> EditionInfo:
        ed = parse_edition(edition) if edition else edition_from_path(path_or_url)
        if ed is None:
            raise DcIndexError(
                "could not determine DEF CON edition; pass --edition (e.g. dc30) "
                f"(from {path_or_url!r})"
            )
        return ed


def _category_set(categories: list[str] | None) -> set[SessionCategory] | None:
    if not categories:
        return None
    out: set[SessionCategory] = set()
    for c in categories:
        try:
            out.add(SessionCategory(c.strip().lower()))
        except ValueError as exc:
            valid = ", ".join(sc.value for sc in SessionCategory)
            raise DcIndexError(f"unknown category {c!r}; valid: {valid}") from exc
    return out


def _default_dump_url(edition: EditionInfo) -> str:
    from dcindex.core.editions import dump_url_for

    return dump_url_for(edition)
