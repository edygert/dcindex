"""Application settings.

Resolution order (pydantic-settings): explicit kwargs > env vars (``DCINDEX_*``) > values in
``~/.config/dcindex/config.toml`` > defaults. Paths follow the XDG base-dir spec.

Scope note: dcindex is local-first. Its only network operation is fetching a published Outel
schedule **dump text file** (``ingest-url``); fetched dumps are cached under ``dumps/`` so the
network is touched at most once per edition. There is no media/asset downloading anywhere.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_UA = "dcindex/0.1 (+local DEF CON schedule indexer; contact via config)"


def _xdg(env: str, default_sub: str) -> Path:
    base = os.environ.get(env)
    root = Path(base) if base else Path.home() / default_sub
    return root / "dcindex"


def _default_data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share")


def _default_config_file() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "config.toml"


def _toml_source() -> dict[str, Any]:
    path = _default_config_file()
    if path.is_file():
        with path.open("rb") as fh:
            return tomllib.load(fh)
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DCINDEX_", extra="ignore")

    # storage
    data_dir: Path = Field(default_factory=_default_data_dir)

    # politeness for the one optional network call (fetching a dump text file)
    request_delay: float = 1.0  # seconds between requests (a small random jitter is added)
    max_retries: int = 3  # retries on timeout / 5xx / 429, with exponential backoff + Retry-After
    timeout: float = 60.0  # dumps can be several MB
    user_agent: str = DEFAULT_UA

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dcindex.sqlite3"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def dump_dir(self) -> Path:
        """Persistent cache of downloaded dump files — fetch once, reuse forever."""
        return self.data_dir / "dumps"

    @property
    def log_file(self) -> Path:
        return self.data_dir / "dcindex.log"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.dump_dir.mkdir(parents=True, exist_ok=True)


def load_settings(**overrides: Any) -> Settings:
    """Build Settings from TOML + env + overrides (overrides win)."""
    merged: dict[str, Any] = {**_toml_source(), **overrides}
    return Settings(**merged)
