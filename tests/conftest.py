from __future__ import annotations

from pathlib import Path

import pytest

from jude.store import Store
from jude.types import Mode


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def matter_id(store: Store) -> str:
    m = store.create_matter("test matter", mode=Mode.STRICT)
    return m.id


@pytest.fixture
def smart_matter_id(store: Store) -> str:
    m = store.create_matter(
        "smart matter",
        mode=Mode.SMART,
        zero_retention_attested=True,
    )
    return m.id
