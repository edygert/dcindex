"""Full-text search over sessions."""

from __future__ import annotations

import re

from dcindex.storage.repositories import Repository

_TERM = re.compile(r"[A-Za-z0-9]+")
_MIN_TERM = 3  # the trigram tokenizer can't match terms shorter than 3 characters


def _safe_fts_query(query: str) -> str:
    """Build an FTS5 query from free text for the **trigram**-tokenized index.

    Each alphanumeric term >= 3 chars becomes a quoted substring match (quoting keeps arbitrary user
    input from tripping FTS5 syntax); terms are AND-ed. With the trigram tokenizer a quoted term
    matches anywhere inside a word, so ``hyper`` finds ``hypervisor`` and ``superhypervisor``. Terms
    shorter than 3 chars are dropped (they can't be matched); an empty result -> matches nothing.
    """
    terms = [t for t in _TERM.findall(query) if len(t) >= _MIN_TERM]
    return " AND ".join(f'"{t}"' for t in terms)


class SearchService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def search(self, query: str, limit: int = 50) -> list[dict]:
        terms = _TERM.findall(query)
        if not terms:
            return []
        # The trigram index can't match terms < 3 chars. If the query has any short term (e.g. "ai",
        # "os", "5g"), fall back to a LIKE scan over the denormalized text so short terms still work;
        # otherwise use the fast, ranked FTS path.
        if any(len(t) < _MIN_TERM for t in terms):
            return [dict(row) for row in self.repo.search_sessions_like(terms, limit)]
        return [dict(row) for row in self.repo.search_sessions(_safe_fts_query(query), limit)]
