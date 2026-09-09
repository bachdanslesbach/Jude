"""Span-level precision/recall/F1 with lenient overlap matching.

A predicted span is a TP iff it (a) overlaps a gold span by at least
one character AND (b) has the same `type`. Each gold matches at most
one pred, picked greedily by largest overlap so the most specific
prediction is credited (not the first one in input order).

`score(..., type_strict=False)` drops constraint (b). That variant is
reported alongside the strict one when comparing systems whose label
taxonomies differ from Jude's: it answers "did it redact the right
characters" independently of what it called them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .schema import (
    CorpusReport,
    DocumentResult,
    GoldDocument,
    GoldSpan,
    PredSpan,
    Score,
    TypeScore,
)


def _overlap(a: GoldSpan | PredSpan, b: GoldSpan | PredSpan) -> int:
    return max(0, min(a.end, b.end) - max(a.start, b.start))


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return p, r, f1


def match_spans(
    preds: list[PredSpan],
    golds: list[GoldSpan],
    *,
    type_strict: bool = True,
) -> tuple[dict[int, int], dict[int, int]]:
    """Greedy largest-overlap-first one-to-one matching.

    Returns (pred_idx → gold_idx, gold_idx → pred_idx). Exposed so the
    error-analysis tooling can list exactly which spans were missed or
    spurious under the same rule the score uses.
    """

    edges: list[tuple[int, int, int]] = []
    for pi, p in enumerate(preds):
        for gi, g in enumerate(golds):
            if type_strict and p.type != g.type:
                continue
            ov = _overlap(p, g)
            if ov > 0:
                edges.append((pi, gi, ov))

    edges.sort(key=lambda e: -e[2])
    pred_matched: dict[int, int] = {}
    gold_matched: dict[int, int] = {}
    for pi, gi, _ov in edges:
        if pi in pred_matched or gi in gold_matched:
            continue
        pred_matched[pi] = gi
        gold_matched[gi] = pi
    return pred_matched, gold_matched


def score(
    pred_spans: Iterable[PredSpan],
    gold_spans: Iterable[GoldSpan],
    *,
    type_strict: bool = True,
) -> Score:
    """Lenient-overlap matching, type-strict by default.

    Algorithm:
      1. For each predicted span, find the gold span (of the same type,
         unless `type_strict=False`) with the largest character overlap.
      2. Each gold can be claimed by at most one pred. We process preds
         in order of decreasing overlap so the strongest match wins.
      3. Counts: TP = matched preds; FP = unmatched preds; FN =
         unmatched golds.
    """

    preds = list(pred_spans)
    golds = list(gold_spans)
    pred_matched, gold_matched = match_spans(preds, golds, type_strict=type_strict)

    tp = len(pred_matched)
    fp = len(preds) - tp
    fn = len(golds) - len(gold_matched)
    p, r, f1 = _f1(tp, fp, fn)

    by_type_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    for pi, p_span in enumerate(preds):
        if pi in pred_matched:
            # Credit the TP to the gold's type so per-type recall stays
            # meaningful in type-agnostic mode.
            by_type_counts[golds[pred_matched[pi]].type]["tp"] += 1
        else:
            by_type_counts[p_span.type]["fp"] += 1
    for gi, g_span in enumerate(golds):
        if gi not in gold_matched:
            by_type_counts[g_span.type]["fn"] += 1

    by_type: dict[str, TypeScore] = {}
    for t, c in by_type_counts.items():
        tp_t, fp_t, fn_t = c["tp"], c["fp"], c["fn"]
        p_t, r_t, f1_t = _f1(tp_t, fp_t, fn_t)
        by_type[t] = TypeScore(
            precision=p_t, recall=r_t, f1=f1_t,
            tp=tp_t, fp=fp_t, fn=fn_t,
        )

    return Score(
        precision=p, recall=r, f1=f1,
        tp=tp, fp=fp, fn=fn,
        by_type=by_type,
    )


def aggregate_scores(scores: Iterable[Score]) -> Score:
    """Micro-average: sum TP/FP/FN across documents, overall and per type."""

    tp = fp = fn = 0
    by_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    for s in scores:
        tp += s.tp
        fp += s.fp
        fn += s.fn
        for t, ts in s.by_type.items():
            by_type[t]["tp"] += ts.tp
            by_type[t]["fp"] += ts.fp
            by_type[t]["fn"] += ts.fn
    p, r, f1 = _f1(tp, fp, fn)
    agg_by_type = {}
    for t, c in by_type.items():
        p_t, r_t, f1_t = _f1(c["tp"], c["fp"], c["fn"])
        agg_by_type[t] = TypeScore(
            precision=p_t, recall=r_t, f1=f1_t,
            tp=c["tp"], fp=c["fp"], fn=c["fn"],
        )
    return Score(precision=p, recall=r, f1=f1, tp=tp, fp=fp, fn=fn, by_type=agg_by_type)


def score_corpus(
    runner,
    documents: Iterable[GoldDocument],
) -> CorpusReport:
    """Run `runner.predict(text)` on each document, score, and aggregate."""

    per_doc: list[DocumentResult] = []
    for doc in documents:
        preds = list(runner.predict(doc.text))
        per_doc.append(DocumentResult(
            doc_id=doc.id,
            runner_name=runner.name,
            score=score(preds, doc.gold_spans),
            pred_spans=preds,
            score_any_type=score(preds, doc.gold_spans, type_strict=False),
        ))

    return CorpusReport(
        runner_name=runner.name,
        per_doc=per_doc,
        aggregate=aggregate_scores(d.score for d in per_doc),
        aggregate_any_type=aggregate_scores(
            d.score_any_type for d in per_doc if d.score_any_type is not None
        ),
    )
