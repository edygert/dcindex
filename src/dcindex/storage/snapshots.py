"""Provenance store for ingested dumps.

We do NOT copy multi-MB dump files into a content-addressed store (they already live in the
``dumps/`` cache or wherever the user pointed us). Instead we record a row: the dump's sha256, its
on-disk path, and its size — enough to detect "already ingested this exact dump" and to trace any
session back to the file it came from.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .repositories import Repository


class SnapshotStore:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def record(self, url: str, text: str, path: str | None = None) -> int:
        """Record provenance for an ingested dump. ``path`` defaults to the provenance url."""
        sha = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        nbytes = len(text.encode("utf-8", "replace"))
        return self.repo.record_snapshot(url, sha, path or url, nbytes)

    @staticmethod
    def sha256_of_file(path: Path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
