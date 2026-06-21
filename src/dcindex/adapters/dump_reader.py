"""Read a MySQL dump from disk into a FetchResult. Supports plain text and gzip."""

from __future__ import annotations

import gzip
from pathlib import Path

from dcindex.core.errors import FetchError
from dcindex.core.models import FetchResult, SourceName


def read_dump(path: str | Path, *, source: SourceName = SourceName.DUMP) -> FetchResult:
    p = Path(path)
    if not p.is_file():
        raise FetchError(f"dump file not found: {path}", url=str(path))
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    else:
        text = p.read_text(encoding="utf-8", errors="replace")
    return FetchResult(url=str(p), text=text, source=source)
