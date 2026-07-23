from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pipeline.config import Config


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    base = Config.from_env(tmp_path)
    return replace(
        base,
        db_path=tmp_path / "repo.sqlite3",
        cache_dir=tmp_path / "cache",
        exports_dir=tmp_path / "exports",
        github_search_enabled=True,
        hn_enabled=True,
        reddit_enabled=False,
        awesome_enabled=True,
    )
