from __future__ import annotations

from pathlib import Path


class TextAdapter:
    """Plain-text reader/writer."""

    @staticmethod
    def read(path: Path | str) -> str:
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    def write(path: Path | str, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")
