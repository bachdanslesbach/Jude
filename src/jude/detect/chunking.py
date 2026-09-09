"""Split long texts into windows a fixed-context model can see whole.

GLiNER's `predict_entities` tokenises with `truncation=True` at the
model's `max_len` (384 word-tokens for the large checkpoints) and does
not say so; anything past that point is never scored. Detectors with
such a limit call `chunk_text` and shift the returned offsets back.

Windows are **balanced**, not greedily filled: a 275-word document
becomes two windows of ~140 words, never 200 + 75. Short windows starve
the model of context and it starts labelling role phrases ("the Firm",
"our client") as entities — measurably so on the benchmark. Windows
break on paragraph boundaries so an entity is not cut in half; an
oversized paragraph is windowed by word count. Every chunk satisfies
`text[offset:offset + len(chunk)] == chunk`, and every whitespace-
delimited token of the input lands in exactly one chunk.
"""

from __future__ import annotations

import math
import re

_WORD_RE = re.compile(r"\S+")
_PARA_RE = re.compile(r"\n+")

# Comfortably below GLiNER's 384-token limit: its tokeniser counts
# punctuation as tokens, so 200 whitespace words is ~250–300 tokens.
DEFAULT_MAX_WORDS = 200


def _units(text: str, max_words: int) -> list[tuple[int, int, int]]:
    """(start, end, n_words) for each paragraph, oversized paragraphs
    pre-split into word windows of at most `max_words`."""

    units: list[tuple[int, int, int]] = []
    pos = 0
    bounds: list[tuple[int, int]] = []
    for m in _PARA_RE.finditer(text):
        if m.start() > pos:
            bounds.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        bounds.append((pos, len(text)))

    for p_start, p_end in bounds:
        words = list(_WORD_RE.finditer(text, p_start, p_end))
        if not words:
            continue
        for i in range(0, len(words), max_words):
            window = words[i:i + max_words]
            units.append((window[0].start(), window[-1].end(), len(window)))
    return units


def _group(units: list[tuple[int, int, int]], cap: int) -> list[list[tuple[int, int, int]]]:
    groups: list[list[tuple[int, int, int]]] = []
    cur: list[tuple[int, int, int]] = []
    cur_words = 0
    for u in units:
        if cur and cur_words + u[2] > cap:
            groups.append(cur)
            cur, cur_words = [], 0
        cur.append(u)
        cur_words += u[2]
    if cur:
        groups.append(cur)
    return groups


def chunk_text(text: str, max_words: int = DEFAULT_MAX_WORDS) -> list[tuple[int, str]]:
    """(offset, chunk) pairs of at most `max_words` whitespace tokens,
    as evenly sized as paragraph boundaries allow."""

    units = _units(text, max_words)
    if not units:
        return []
    total = sum(u[2] for u in units)
    if total <= max_words:
        return [(units[0][0], text[units[0][0]:units[-1][1]])]

    # Smallest cap in [ceil(total / n), max_words] that still yields at
    # most n = ceil(total / max_words) groups — i.e. the most even
    # split. Group count is monotone in the cap, so binary search.
    n_groups = math.ceil(total / max_words)
    lo, hi = math.ceil(total / n_groups), max_words
    while lo < hi:
        mid = (lo + hi) // 2
        if len(_group(units, mid)) <= n_groups:
            hi = mid
        else:
            lo = mid + 1
    groups = _group(units, lo)
    return [(g[0][0], text[g[0][0]:g[-1][1]]) for g in groups]
