"""Read-only views of what has been ingested."""

from __future__ import annotations

from dcindex.storage.repositories import Repository


class StatsService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def overview(self) -> dict[str, int]:
        return self.repo.stats()

    def by_category(self) -> list[dict]:
        return [dict(row) for row in self.repo.stats_by_category()]

    def events(self) -> list[dict]:
        return [dict(row) for row in self.repo.list_events()]
