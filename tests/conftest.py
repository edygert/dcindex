from __future__ import annotations

from pathlib import Path

import pytest

from dcindex.core.config import Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_DUMP = FIXTURES / "sql" / "dc_sample.sql"


@pytest.fixture
def dump_sql() -> str:
    return SAMPLE_DUMP.read_text(encoding="utf-8")


@pytest.fixture
def sample_dump_path() -> Path:
    return SAMPLE_DUMP


@pytest.fixture
def temp_settings(tmp_path: Path) -> Settings:
    return load_settings(data_dir=tmp_path, request_delay=0.0, max_retries=1)
