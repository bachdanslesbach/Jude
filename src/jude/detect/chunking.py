"""Split long texts into windows a fixed-context model can see whole.

GLiNER's `predict_entities` tokenises with `truncation=True` at the
model's `max_len` (384 word-tokens for the large checkpoints) and does
not say so; anything past that point is never scored. Detectors with
such a limit call `chunk_text` and shift the returned offsets back.

Chunks prefer paragraph boundaries so an entity is not cut in half; an
oversized paragraph is windowed by word count. Every chunk satisfies
`text[offset:offset + len(chunk)] == chunk`, and every whitespace-
delimited token of the input lands in exactly one chunk.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\S+")
_PARA_RE = re.compile(r"\n+")

# Comfortably below GLiNER's 384-token limit: its tokeniser counts
# punctuation as tokens, so 200 whitespace words is ~250–300 tokens.
DEFAULT_MAX_WORDS = 200


def chunk_text(text: str, max_words: int = DEFAULT_MAX_WORDS) -> list[tuple[int, str]]:
    """(offset, chunk) pairs of at most `max_words` whitespace tokens."""

    paragraphs: list[tuple[int, int]] = []
    pos = 0
    for m in _PARA_RE.finditer(text):
        if m.start() > pos:
            paragraphs.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        paragraphs.append((pos, len(text)))

    chunks: list[tuple[int, str]] = []
    cur_start: int | None = None
    cur_end = 0
    cur_words = 0
    for p_start, p_end in paragraphs:
        words = list(_WORD_RE.finditer(text, p_start, p_end))
        if not words:
            continue
        if len(words) > max_words:
            if cur_start is not None:
                chunks.append((cur_start, text[cur_start:cur_end]))
                cur_start = None
                cur_words = 0
            for i in range(0, len(words), max_words):
                w0 = words[i]
                w1 = words[min(i + max_words, len(words)) - 1]
                chunks.append((w0.start(), text[w0.start():w1.end()]))
            continue
        if cur_start is not None and cur_words + len(words) > max_words:
            chunks.append((cur_start, text[cur_start:cur_end]))
            cur_start = None
            cur_words = 0
        if cur_start is None:
            cur_start = words[0].start()
        cur_end = words[-1].end()
        cur_words += len(words)
    if cur_start is not None:
        chunks.append((cur_start, text[cur_start:cur_end]))
    return chunks
