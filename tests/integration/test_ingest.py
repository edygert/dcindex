"""End-to-end ingest of a local dump. Pins the metadata-only invariant: ingest writes only the DB
(+ provenance rows); it never reaches the network and never writes a media/binary asset file."""

from __future__ import annotations

import httpx
import respx

from dcindex.core.models import SourceName
from dcindex.services import ServiceContainer


def test_ingest_dump_end_to_end(temp_settings, sample_dump_path):
    with ServiceContainer(temp_settings) as app_:
        report = app_.ingest.ingest_dump(str(sample_dump_path), edition="dc30")

        assert report.status == "ok"
        assert report.edition == "defcon-30"
        assert report.source is SourceName.DUMP
        assert report.sessions_upserted == 5
        assert report.by_category == {"talk": 2, "demolab": 1, "village": 1, "page": 1}
        assert report.speakers_upserted == 3
        assert report.materials_upserted > 0
        assert report.skipped_tables == ["random_extra"]

        # search + show round-trip
        hits = app_.search.search("kernels")
        assert hits and hits[0]["title"] == "Breaking Kernels"
        detail = app_.sessions.get(hits[0]["id"])
        assert any("github.com" in m.url for m in detail.materials)

    # Invariant: no binary asset files anywhere under the data dir (only the sqlite DB + WAL).
    files = [p for p in temp_settings.data_dir.rglob("*") if p.is_file()]
    assert files, "expected a database file"
    allowed_suffixes = {".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".log"}
    for p in files:
        name = p.name
        assert (
            p.suffix in allowed_suffixes
            or name.startswith("dcindex.sqlite3")
            or name == "dcindex.log"
        ), f"unexpected file written: {p}"


def test_ingest_dump_idempotent(temp_settings, sample_dump_path):
    with ServiceContainer(temp_settings) as app_:
        app_.ingest.ingest_dump(str(sample_dump_path), edition="dc30")
        app_.ingest.ingest_dump(str(sample_dump_path), edition="dc30")
        assert app_.stats.overview()["sessions"] == 5  # no duplication on re-ingest


@respx.mock
def test_ingest_url_caches(temp_settings, dump_sql):
    url = "https://defcon.outel.org/defcon30/dc30_mysqldump.txt"
    route = respx.get(url).mock(return_value=httpx.Response(200, text=dump_sql))
    with ServiceContainer(temp_settings) as app_:
        r1 = app_.ingest.ingest_url(url, edition="dc30")
        assert r1.from_cache is False and r1.sessions_upserted == 5
        r2 = app_.ingest.ingest_url(url, edition="dc30")
        assert r2.from_cache is True
    assert route.call_count == 1  # second ingest served from the dump cache
