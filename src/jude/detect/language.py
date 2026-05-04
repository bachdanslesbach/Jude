from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0


def detect_language(
    text: str,
    supported: tuple[str, ...] = ("en", "fr"),
    min_confidence: float = 0.6,
    min_chars: int = 20,
) -> str | None:
    """Best-effort language detection for a chunk of text.

    Returns one of `supported` if the detector is confident enough, or
    None if it cannot decide. Short or whitespace-only inputs return None.
    """

    s = text.strip()
    if len(s) < min_chars:
        return None
    try:
        for cand in detect_langs(s):
            if cand.lang in supported and cand.prob >= min_confidence:
                return cand.lang
    except LangDetectException:
        return None
    return None


def split_into_paragraphs(text: str) -> list[tuple[int, str]]:
    """Split `text` into paragraphs, returning `(start_offset, paragraph)` pairs.

    A paragraph is any run of non-empty content separated by one or more
    blank lines. Offsets are absolute character indices into `text`.
    """

    import re

    out: list[tuple[int, str]] = []
    cursor = 0
    for match in re.finditer(r"\n\s*\n+", text):
        chunk = text[cursor:match.start()]
        if chunk.strip():
            out.append((cursor, chunk))
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        out.append((cursor, tail))
    return out
