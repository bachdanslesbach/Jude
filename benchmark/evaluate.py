"""Span-level precision/recall/F1 with lenient overlap matching.

A predicted span is a TP iff it (a) overlaps a gold span by at least
one character AND (b) has the same `type`. Each gold matches at most
one pred, picked greedily by largest overlap so the most specific
prediction is credited (not the first one in input order).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

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


def score(
    pred_spans: Iterable[PredSpan],
    gold_spans: Iterable[GoldSpan],
) -> Score:
    """Lenient-overlap, type-strict matching.

    Algorithm:
      1. For each predicted span, find the gold span (of the same type)
         with the largest character overlap (>0).
      2. Each gold can be claimed by at most one pred. We process preds
         in order of decreasing overlap so the strongest match wins.
      3. Counts: TP = matched preds; FP = unmatched preds; FN =
         unmatched golds.
    """

    preds = list(pred_spans)
    golds = list(gold_spans)

    # Build (pred_idx, gold_idx, overlap) candidate edges.
    edges: list[tuple[int, int, int]] = []
    for pi, p in enumerate(preds):
        for gi, g in enumerate(golds):
            if p.type != g.type:
                continue
            ov = _overlap(p, g)
            if ov > 0:
                edges.append((pi, gi, ov))

    # Greedy match by descending overlap.
    edges.sort(key=lambda e: -e[2])
    pred_matched: dict[int, int] = {}
    gold_matched: dict[int, int] = {}
    for pi, gi, _ov in edges:
        if pi in pred_matched or gi in gold_matched:
            continue
        pred_matched[pi] = gi
        gold_matched[gi] = pi

    tp = len(pred_matched)
    fp = len(preds) - tp
    fn = len(golds) - len(gold_matched)
    p, r, f1 = _f1(tp, fp, fn)

    # Per-type breakdown.
    by_type_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    for pi, p_span in enumerate(preds):
        if pi in pred_matched:
            by_type_counts[p_span.type]["tp"] += 1
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


def score_corpus(
    runner,  # noqa: ANN001
    documents: Iterable[GoldDocument],
) -> CorpusReport:
    """Run `runner.predict(text)` on each document, score, and aggregate."""

    per_doc: list[DocumentResult] = []
    agg_tp = agg_fp = agg_fn = 0
    agg_by_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    for doc in documents:
        preds = list(runner.predict(doc.text))
        s = score(preds, doc.gold_spans)
        per_doc.append(DocumentResult(
            doc_id=doc.id, runner_name=runner.name, score=s, pred_spans=preds
        ))
        agg_tp += s.tp
        agg_fp += s.fp
        agg_fn += s.fn
        for t, ts in s.by_type.items():
            agg_by_type[t]["tp"] += ts.tp
            agg_by_type[t]["fp"] += ts.fp
            agg_by_type[t]["fn"] += ts.fn

    p, r, f1 = _f1(agg_tp, agg_fp, agg_fn)
    aggregate_by_type = {}
    for t, c in agg_by_type.items():
        p_t, r_t, f1_t = _f1(c["tp"], c["fp"], c["fn"])
        aggregate_by_type[t] = TypeScore(
            precision=p_t, recall=r_t, f1=f1_t,
            tp=c["tp"], fp=c["fp"], fn=c["fn"],
        )
    aggregate = Score(
        precision=p, recall=r, f1=f1,
        tp=agg_tp, fp=agg_fp, fn=agg_fn,
        by_type=aggregate_by_type,
    )
    return CorpusReport(
        runner_name=runner.name,
        per_doc=per_doc,
        aggregate=aggregate,
    )
