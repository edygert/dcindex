"""Persistent cache of downloaded dump files — fetch once, reuse forever.

``ingest-url`` calls :meth:`DumpCache.fetch_cached`. On a cache hit it returns the local copy and
**never touches the network**; otherwise it fetches the dump text via the polite ``HttpClient``,
writes it under ``<data_dir>/dumps/`` and returns it. ``refresh=True`` forces a re-fetch (e.g. when a
year's schedule was updated after first download).
"""

from __future__ import annotations

from pathlib import Path

from dcindex.adapters.http_client import HttpClient, Notify
from dcindex.core.config import Settings
from dcindex.core.editions import EditionInfo
from dcindex.core.logging import get_logger
from dcindex.core.models import FetchResult, SourceName


class DumpCache:
    def __init__(self, settings: Settings, *, client: HttpClient | None = None) -> None:
        self.settings = settings
        self._client = client  # injectable for tests
        self.log = get_logger()

    def path_for(self, edition: EditionInfo) -> Path:
        return self.settings.dump_dir / f"dc{edition.number}_mysqldump.txt"

    def is_cached(self, edition: EditionInfo) -> bool:
        return self.path_for(edition).is_file()

    def fetch_cached(
        self,
        url: str,
        edition: EditionInfo,
        *,
        refresh: bool = False,
        notify: Notify | None = None,
    ) -> FetchResult:
        path = self.path_for(edition)
        if path.is_file() and not refresh:
            self.log.info("dump cache hit: %s", path)
            text = path.read_text(encoding="utf-8", errors="replace")
            return FetchResult(url=url, text=text, source=SourceName.URL, from_cache=True)

        self.log.info("fetching dump: %s", url)
        text = self._get(url, notify=notify)
        self.settings.dump_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.log.info("cached dump -> %s (%d bytes)", path, len(text))
        return FetchResult(url=url, text=text, source=SourceName.URL, from_cache=False)

    def _get(self, url: str, *, notify: Notify | None) -> str:
        if self._client is not None:
            return self._client.get(url).text
        with HttpClient(self.settings, notify=notify) as client:
            return client.get(url).text
