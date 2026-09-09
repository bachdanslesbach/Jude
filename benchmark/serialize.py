"""JSON round-trip for `CorpusReport`.

Each external model is 0.6–1.2 B parameters; on an 8 GB laptop they
cannot share a process with Jude's own transformer + GLiNER stack.
Runners therefore execute one per process, dump their report to JSON,
and `benchmark.run --render` merges the files into a single markdown
report.
"""

from __future__ import annotations

from dataclasses import asdict

from .schema import CorpusReport, DocumentResult, PredSpan, Score, TypeScore


def _score_to_dict(s: Score | None) -> dict | None:
    if s is None:
        return None
    return {
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
        "tp": s.tp,
        "fp": s.fp,
        "fn": s.fn,
        "by_type": {t: asdict(ts) for t, ts in s.by_type.items()},
    }


def _score_from_dict(d: dict | None) -> Score | None:
    if d is None:
        return None
    return Score(
        precision=float(d["precision"]),
        recall=float(d["recall"]),
        f1=float(d["f1"]),
        tp=int(d["tp"]),
        fp=int(d["fp"]),
        fn=int(d["fn"]),
        by_type={t: TypeScore(**ts) for t, ts in d.get("by_type", {}).items()},
    )


def report_to_dict(r: CorpusReport) -> dict:
    return {
        "runner_name": r.runner_name,
        "aggregate": _score_to_dict(r.aggregate),
        "aggregate_any_type": _score_to_dict(r.aggregate_any_type),
        "meta": dict(r.meta),
        "per_doc": [
            {
                "doc_id": d.doc_id,
                "score": _score_to_dict(d.score),
                "score_any_type": _score_to_dict(d.score_any_type),
                "pred_spans": [asdict(p) for p in d.pred_spans],
            }
            for d in r.per_doc
        ],
    }


def report_from_dict(d: dict) -> CorpusReport:
    name = str(d["runner_name"])
    per_doc = [
        DocumentResult(
            doc_id=str(x["doc_id"]),
            runner_name=name,
            score=_score_from_dict(x["score"]),  # type: ignore[arg-type]
            pred_spans=[PredSpan(**p) for p in x.get("pred_spans", [])],
            score_any_type=_score_from_dict(x.get("score_any_type")),
        )
        for x in d.get("per_doc", [])
    ]
    return CorpusReport(
        runner_name=name,
        per_doc=per_doc,
        aggregate=_score_from_dict(d["aggregate"]),  # type: ignore[arg-type]
        aggregate_any_type=_score_from_dict(d.get("aggregate_any_type")),
        meta=dict(d.get("meta", {})),
    )
