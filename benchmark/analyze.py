"""Error analysis over saved benchmark JSON.

Lists, per runner, what was missed (FN), what was spurious (FP), and
which public-body mentions were redacted — the raw material for the
failure taxonomy in `docs/benchmark-pii-models.md`.

    python -m benchmark.analyze benchmark/results/pplx-pii-masking.json
    python -m benchmark.analyze benchmark/results/*.json --type ORG --limit 15
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .evaluate import match_spans
from .negative import public_mentions
from .run import _load_corpus
from .serialize import report_from_dict


def analyze(report, docs, *, only_type: str | None, limit: int, type_strict: bool) -> str:
    by_id = {d.id: d for d in docs}
    fns: dict[str, list[str]] = defaultdict(list)
    fps: dict[str, list[str]] = defaultdict(list)
    type_confusions: Counter[tuple[str, str]] = Counter()
    public_hits: list[str] = []

    for dr in report.per_doc:
        doc = by_id[dr.doc_id]
        golds = list(doc.gold_spans)
        preds = list(dr.pred_spans)
        pm, gm = match_spans(preds, golds, type_strict=type_strict)
        # Type confusions: a pred that overlaps a gold of another type
        # and was not matched under the strict rule.
        if type_strict:
            pm_any, _ = match_spans(preds, golds, type_strict=False)
            for pi, gi in pm_any.items():
                if pi not in pm and preds[pi].type != golds[gi].type:
                    type_confusions[(golds[gi].type, preds[pi].type)] += 1
        for gi, g in enumerate(golds):
            if gi not in gm and (only_type is None or g.type == only_type):
                fns[g.type].append(f"{dr.doc_id[:7]} {g.text!r}")
        for pi, p in enumerate(preds):
            if pi not in pm and (only_type is None or p.type == only_type):
                fps[p.type].append(f"{dr.doc_id[:7]} {p.text!r}")
        for m in public_mentions(doc.text, golds, explicit=doc.public_spans):
            if any(not (m.end <= p.start or p.end <= m.start) for p in preds):
                public_hits.append(f"{dr.doc_id[:7]} {m.text!r} ({m.canonical})")

    out = [f"## {report.runner_name}"]
    a = report.aggregate
    out.append(f"F1 {a.f1:.3f}  P {a.precision:.3f}  R {a.recall:.3f}  TP {a.tp} FP {a.fp} FN {a.fn}")
    for t, ts in sorted(a.by_type.items()):
        out.append(f"  {t:9s} F1 {ts.f1:.3f}  P {ts.precision:.3f} R {ts.recall:.3f}  ({ts.tp}/{ts.fp}/{ts.fn})")
    if type_confusions:
        out.append("\n### Type confusions (gold → predicted)")
        for (g, p), n in type_confusions.most_common():
            out.append(f"  {g} → {p}: {n}")
    out.append("\n### False negatives (missed)")
    for t, xs in sorted(fns.items()):
        out.append(f"  [{t}] {len(xs)}")
        for x in xs[:limit]:
            out.append(f"      {x}")
        if len(xs) > limit:
            out.append(f"      … +{len(xs) - limit} more")
    out.append("\n### False positives (spurious)")
    for t, xs in sorted(fps.items()):
        out.append(f"  [{t}] {len(xs)}")
        for x in xs[:limit]:
            out.append(f"      {x}")
        if len(xs) > limit:
            out.append(f"      … +{len(xs) - limit} more")
    out.append(f"\n### Public-body mentions redacted ({len(public_hits)})")
    for x in public_hits[:limit]:
        out.append(f"      {x}")
    if len(public_hits) > limit:
        out.append(f"      … +{len(public_hits) - limit} more")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--type", default=None, help="Restrict FN/FP listing to one entity type")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--any-type", action="store_true", help="Match without the type constraint")
    args = p.parse_args(argv)

    docs = _load_corpus()
    for f in args.files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for d in data if isinstance(data, list) else [data]:
            report = report_from_dict(d)
            if not report.meta.get("span_level", True):
                print(f"## {report.runner_name}\n(sentence-level only; no spans)\n")
                continue
            print(analyze(report, docs, only_type=args.type, limit=args.limit,
                          type_strict=not args.any_type))
            print()


if __name__ == "__main__":
    main()
