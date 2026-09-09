"""Sentence-level evaluation.

Some PII systems are message-level classifiers ("does this text give
or ask for PII?") rather than span extractors. Scoring them with span
F1 would be meaningless; scoring them only on their own chat data
would say nothing about legal documents. The fair middle ground is to
split each corpus document into sentences, mark a sentence positive
iff it overlaps a gold span, and score the classifier's per-sentence
verdicts. Span runners are projected onto the same grid (a sentence is
positive iff any predicted span overlaps it) so every system gets one
row in the same table.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .schema import GoldSpan, PredSpan, Score

# Split on newlines, or on sentence-final punctuation followed by
# whitespace. Deliberately simple: abbreviations ("Mr. Smith") produce
# an extra boundary, which only makes the grid finer.
_BOUNDARY_RE = re.compile(r"\n+|(?<=[.!?])\s+")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) offsets of non-empty, whitespace-trimmed sentences."""

    out: list[tuple[int, int]] = []
    pos = 0
    for m in _BOUNDARY_RE.finditer(text):
        seg = _trim(text, pos, m.start())
        if seg:
            out.append(seg)
        pos = m.end()
    seg = _trim(text, pos, len(text))
    if seg:
        out.append(seg)
    return out


def _trim(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _overlaps(sent: tuple[int, int], span) -> bool:
    s, e = sent
    return not (e <= span.start or span.end <= s)


def sentence_gold_labels(
    sentences: Sequence[tuple[int, int]],
    gold_spans: Iterable[GoldSpan],
) -> list[bool]:
    golds = list(gold_spans)
    return [any(_overlaps(s, g) for g in golds) for s in sentences]


def sentence_flags_from_spans(
    sentences: Sequence[tuple[int, int]],
    pred_spans: Iterable[PredSpan],
) -> list[bool]:
    preds = list(pred_spans)
    return [any(_overlaps(s, p) for p in preds) for s in sentences]


def score_sentences(pred: Sequence[bool], gold: Sequence[bool]) -> Score:
    if len(pred) != len(gold):
        raise ValueError("pred and gold must have the same length")
    tp = sum(1 for p, g in zip(pred, gold) if p and g)
    fp = sum(1 for p, g in zip(pred, gold) if p and not g)
    fn = sum(1 for p, g in zip(pred, gold) if g and not p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return Score(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn)
