from __future__ import annotations

import os
from pathlib import Path


def jude_home() -> Path:
    base = os.environ.get("JUDE_HOME")
    if base:
        return Path(base)
    return Path.home() / ".jude"


def default_db_path() -> Path:
    p = jude_home() / "jude.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
