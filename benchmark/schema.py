"""Data classes for the benchmark.

A `GoldDocument` is what we expect of any test document on disk:
id, title, language, full text, and the list of spans that should be
redacted. A `GoldSpan` is the unit of ground truth — a (start, end,
type, text) tuple. A `PredSpan` is the same shape produced by a
runner; we keep them separate to make code-paths self-documenting.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GoldSpan:
    start: int
    end: int
    type: str
    text: str

    def overlaps(self, other: Span) -> bool:  # noqa: F821
        return not (self.end <= other.start or other.end <= self.start)


@dataclass(frozen=True)
class PredSpan:
    start: int
    end: int
    type: str
    text: str

    def overlaps(self, other: Span) -> bool:  # noqa: F821
        return not (self.end <= other.start or other.end <= self.start)


@dataclass(frozen=True)
class GoldDocument:
    id: str
    title: str
    language: str
    text: str
    gold_spans: tuple[GoldSpan, ...]
    notes: str = ""
    # Mentions the annotator explicitly confirmed must NOT be redacted
    # (type "PUBLIC"). Feed the public-body over-redaction metric; never
    # scored as gold. Absent from older corpus files.
    public_spans: tuple[GoldSpan, ...] = ()

    @classmethod
    def from_json(cls, path: Path | str) -> GoldDocument:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        spans = tuple(
            GoldSpan(
                start=int(s["start"]),
                end=int(s["end"]),
                type=str(s["type"]),
                text=str(s["text"]),
            )
            for s in data["gold_spans"]
        )
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            language=str(data["language"]),
            text=str(data["text"]),
            gold_spans=spans,
            notes=str(data.get("notes", "")),
            public_spans=tuple(
                GoldSpan(
                    start=int(s["start"]),
                    end=int(s["end"]),
                    type=str(s.get("type", "PUBLIC")),
                    text=str(s["text"]),
                )
                for s in data.get("public_spans", [])
            ),
        )


@dataclass
class TypeScore:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


@dataclass
class Score:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    by_type: dict[str, TypeScore] = field(default_factory=dict)


@dataclass
class DocumentResult:
    doc_id: str
    runner_name: str
    score: Score
    pred_spans: list[PredSpan]
    # Same matching with the type constraint dropped — "did it redact
    # the right characters", independent of label taxonomy. Needed to
    # compare systems whose label sets differ from Jude's.
    score_any_type: Score | None = None


@dataclass
class CorpusReport:
    runner_name: str
    per_doc: list[DocumentResult]
    aggregate: Score
    aggregate_any_type: Score | None = None
    # Free-form: timing, memory, negative-class metric, sentence-level
    # score, out-of-schema prediction counts. Serialised verbatim.
    meta: dict = field(default_factory=dict)
