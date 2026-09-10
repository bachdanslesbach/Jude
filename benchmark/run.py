"""Benchmark orchestrator.

Runs registered runners against every gold document in
`benchmark/corpus/`, computes per-runner aggregate F1 plus the
secondary metrics (type-agnostic F1, public-body over-redaction,
sentence-level F1, throughput, peak memory) and prints a markdown
table. Reports can be written to JSON and merged later, so heavy
external models can each run in their own process:

    python -m benchmark.run                          # Jude runners, summary
    python -m benchmark.run --report docs/benchmark.md
    python -m benchmark.run --list                   # registered runners
    python -m benchmark.run --runners pplx-pii-masking --json out/pplx.json
    python -m benchmark.run --render out/*.json --report docs/benchmark-pii-models.md
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .evaluate import aggregate_scores, match_spans, score, score_corpus
from .negative import over_redaction, public_mentions
from .schema import CorpusReport, DocumentResult, GoldDocument, Score
from .sentence_eval import (
    score_sentences,
    sentence_flags_from_spans,
    sentence_gold_labels,
    split_sentences,
)
from .serialize import report_from_dict, report_to_dict

CORPUS_DIR = Path(__file__).parent / "corpus"

DEFAULT_RUNNERS = ("jude-full", "jude-no-public-filter", "spacy-only", "regex-only")


def _load_corpus() -> list[GoldDocument]:
    return [GoldDocument.from_json(p) for p in sorted(CORPUS_DIR.glob("doc_*.json"))]


def _registry() -> dict[str, Callable[[], object]]:
    """name → zero-arg factory. Imports are deferred so listing runners
    does not load any model."""

    def jude_full():
        from .runners.jude_full import JudeFullRunner
        return JudeFullRunner()

    def jude_no_filter():
        from .runners.jude_no_filter import JudeNoFilterRunner
        return JudeNoFilterRunner()

    def spacy_only():
        from .runners.spacy_only import SpacyOnlyRunner
        return SpacyOnlyRunner()

    def regex_only():
        from .runners.regex_only import RegexOnlyRunner
        return RegexOnlyRunner()

    def gliner_base():
        from .runners.nvidia_gliner_pii import gliner_base_jude_labels
        return gliner_base_jude_labels()

    def nvidia_native():
        from .runners.nvidia_gliner_pii import nvidia_native
        return nvidia_native(threshold=0.5)

    def nvidia_native_t03():
        from .runners.nvidia_gliner_pii import nvidia_native
        return nvidia_native(threshold=0.3)

    def nvidia_jude():
        from .runners.nvidia_gliner_pii import nvidia_jude_labels
        return nvidia_jude_labels()

    def pplx():
        from .runners.pplx_pii import PplxPiiRunner
        return PplxPiiRunner()

    def roblox():
        from .runners.roblox_pii import RobloxPiiRunner
        return RobloxPiiRunner()

    return {
        "jude-full": jude_full,
        "jude-no-public-filter": jude_no_filter,
        "spacy-only": spacy_only,
        "regex-only": regex_only,
        "gliner-large-v2.1-jude-labels": gliner_base,
        "nvidia-gliner-pii-native": nvidia_native,
        "nvidia-gliner-pii-native-t03": nvidia_native_t03,
        "nvidia-gliner-pii-jude-labels": nvidia_jude,
        "pplx-pii-masking": pplx,
        "roblox-pii-classifier": roblox,
    }


# --- execution -------------------------------------------------------------


def _peak_rss_mb() -> float:
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru / (1024 * 1024) if sys.platform == "darwin" else ru / 1024


def _attach_sentence_metrics(
    report: CorpusReport,
    pred_flags: list[list[bool]],
    gold_flags: list[list[bool]],
) -> None:
    flat_pred = [f for fs in pred_flags for f in fs]
    flat_gold = [f for fs in gold_flags for f in fs]
    ss = score_sentences(flat_pred, flat_gold)
    report.meta["sentence_level"] = {
        "precision": ss.precision, "recall": ss.recall, "f1": ss.f1,
        "tp": ss.tp, "fp": ss.fp, "fn": ss.fn, "n_sentences": len(flat_gold),
    }


def _attach_span_metrics(report: CorpusReport, docs: list[GoldDocument]) -> None:
    """Public-body over-redaction and the sentence grid, from the
    report's stored predictions. `docs` must align with `report.per_doc`."""

    sents_per_doc = [split_sentences(d.text) for d in docs]
    gold_flags = [sentence_gold_labels(s, d.gold_spans) for s, d in zip(sents_per_doc, docs)]
    pred_flags = [
        sentence_flags_from_spans(s, dr.pred_spans)
        for s, dr in zip(sents_per_doc, report.per_doc)
    ]
    hits = total = 0
    for d, dr in zip(docs, report.per_doc):
        h, t = over_redaction(
            dr.pred_spans,
            public_mentions(d.text, d.gold_spans, explicit=d.public_spans),
        )
        hits += h
        total += t
    report.meta["span_level"] = True
    report.meta["public_body_over_redaction"] = {
        "hits": hits, "total": total, "rate": (hits / total) if total else 0.0,
    }
    _attach_sentence_metrics(report, pred_flags, gold_flags)
    _attach_review_metric(report, docs)


def _attach_review_metric(report: CorpusReport, docs: list[GoldDocument]) -> None:
    """How many of this runner's misses the unverified-term report
    would put in front of the reviewer, and at what cost in items."""

    from jude.review import unverified_terms

    misses = surfaced = items = 0
    for d, dr in zip(docs, report.per_doc):
        golds = list(d.gold_spans)
        _, gm = match_spans(list(dr.pred_spans), golds)
        missed = [g for i, g in enumerate(golds) if i not in gm]
        terms = unverified_terms(d.text, dr.pred_spans, lang=d.language)
        items += len(terms)
        occ = [(s, e) for t in terms for s, e in t.occurrences]
        misses += len(missed)
        surfaced += sum(1 for g in missed if any(s < g.end and e > g.start for s, e in occ))
    report.meta["review"] = {
        "misses": misses,
        "misses_surfaced": surfaced,
        "items": items,
        "items_per_doc": (items / len(docs)) if docs else 0.0,
    }


def rescore(report: CorpusReport, docs: list[GoldDocument]) -> CorpusReport:
    """Re-score a report's stored predictions against the current gold.

    Gold changes under review; predictions are what a run costs. Every
    score (per document, aggregate, any-type, public-body, sentence
    grid) is recomputed in place; timing and memory meta are kept.
    Documents no longer in the corpus are dropped; corpus documents
    the run never saw are listed in `meta["missing_docs"]` — those need
    a re-run. Sentence-level-only reports are returned untouched.
    """

    if not report.meta.get("span_level", True):
        return report
    by_id = {d.id: d for d in docs}
    per_doc: list[DocumentResult] = []
    kept_docs: list[GoldDocument] = []
    for dr in report.per_doc:
        doc = by_id.get(dr.doc_id)
        if doc is None:
            continue
        per_doc.append(DocumentResult(
            doc_id=dr.doc_id,
            runner_name=dr.runner_name,
            score=score(dr.pred_spans, doc.gold_spans),
            pred_spans=dr.pred_spans,
            score_any_type=score(dr.pred_spans, doc.gold_spans, type_strict=False),
        ))
        kept_docs.append(doc)
    report.per_doc = per_doc
    report.aggregate = aggregate_scores(d.score for d in per_doc)
    report.aggregate_any_type = aggregate_scores(
        d.score_any_type for d in per_doc if d.score_any_type is not None
    )
    _attach_span_metrics(report, kept_docs)
    seen = {d.doc_id for d in per_doc}
    missing = [d.id for d in docs if d.id not in seen]
    if missing:
        report.meta["missing_docs"] = missing
    else:
        report.meta.pop("missing_docs", None)
    return report


def run_one(name: str, factory: Callable[[], object], docs: list[GoldDocument]) -> CorpusReport:
    t0 = time.perf_counter()
    runner = factory()
    load_seconds = time.perf_counter() - t0

    if getattr(runner, "sentence_level_only", False):
        sents_per_doc = [split_sentences(d.text) for d in docs]
        gold_flags = [sentence_gold_labels(s, d.gold_spans) for s, d in zip(sents_per_doc, docs)]
        t0 = time.perf_counter()
        pred_flags = []
        for d, sents in zip(docs, sents_per_doc):
            got_sents, flags = runner.predict_sentences(d.text)  # type: ignore[attr-defined]
            assert got_sents == sents, "runner must use benchmark.sentence_eval.split_sentences"
            pred_flags.append(flags)
        seconds = time.perf_counter() - t0
        report = CorpusReport(
            runner_name=getattr(runner, "name", name),
            per_doc=[],
            aggregate=Score(0.0, 0.0, 0.0, 0, 0, 0),
        )
        report.meta["span_level"] = False
        _attach_sentence_metrics(report, pred_flags, gold_flags)
    else:
        t0 = time.perf_counter()
        report = score_corpus(runner, docs)
        seconds = time.perf_counter() - t0
        _attach_span_metrics(report, docs)

    chars = sum(len(d.text) for d in docs)
    report.meta.update({
        "n_docs": len(docs),
        "load_seconds": load_seconds,
        "seconds": seconds,
        "chars_per_sec": (chars / seconds) if seconds else None,
        "peak_rss_mb": _peak_rss_mb(),
        "device": getattr(runner, "device", "cpu"),
    })
    extra = getattr(runner, "extra_meta", None)
    if callable(extra):
        report.meta.update(extra())
    return report


# --- rendering -------------------------------------------------------------


def _f(x: float | None, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _render_summary_table(reports: list[CorpusReport]) -> str:
    out = [
        "| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        m = r.meta
        a = r.aggregate
        span_level = m.get("span_level", True)
        pb = m.get("public_body_over_redaction")
        pb_s = f"{pb['hits']}/{pb['total']} ({pb['rate']:.0%})" if pb else "—"
        rv = m.get("review")
        rv_s = f"{rv['misses_surfaced']}/{rv['misses']}" if rv else "—"
        rv_items = f"{rv['items_per_doc']:.0f}" if rv else "—"
        sl = m.get("sentence_level")
        rss = m.get("peak_rss_mb")
        cps = m.get("chars_per_sec")
        out.append(
            f"| `{r.runner_name}` | "
            + (f"{a.precision:.3f} | {a.recall:.3f} | **{a.f1:.3f}** | " if span_level else "— | — | — | ")
            + (f"{r.aggregate_any_type.f1:.3f} | " if (span_level and r.aggregate_any_type) else "— | ")
            + f"{pb_s} | {rv_s} | {rv_items} | "
            + (f"{sl['f1']:.3f} | " if sl else "— | ")
            + (f"{cps:,.0f} | " if cps else "— | ")
            + (f"{rss:,.0f} MB |" if rss else "— |")
        )
    return "\n".join(out)


def _render_sentence_table(reports: list[CorpusReport]) -> str:
    out = ["| Runner | Precision | Recall | F1 | TP | FP | FN |",
           "|---|---|---|---|---|---|---|"]
    for r in reports:
        sl = r.meta.get("sentence_level")
        if not sl:
            continue
        out.append(
            f"| `{r.runner_name}` | {sl['precision']:.3f} | {sl['recall']:.3f} | "
            f"**{sl['f1']:.3f}** | {sl['tp']} | {sl['fp']} | {sl['fn']} |"
        )
    return "\n".join(out)


def _render_per_type_table(report: CorpusReport) -> str:
    out = [f"### {report.runner_name} — per type",
           "| Type | Precision | Recall | F1 | TP | FP | FN |",
           "|---|---|---|---|---|---|---|"]
    for t, ts in sorted(report.aggregate.by_type.items()):
        out.append(
            f"| {t} | {ts.precision:.3f} | {ts.recall:.3f} | {ts.f1:.3f} | "
            f"{ts.tp} | {ts.fp} | {ts.fn} |"
        )
    return "\n".join(out)


def _render_per_doc_table(reports: list[CorpusReport]) -> str:
    reports = [r for r in reports if r.meta.get("span_level", True)]
    docs = sorted({d.doc_id for r in reports for d in r.per_doc})
    headers = ["Document"] + [r.runner_name for r in reports]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    by_runner = {r.runner_name: {d.doc_id: d.score for d in r.per_doc} for r in reports}
    for d in docs:
        row = [d]
        for r in reports:
            s = by_runner[r.runner_name].get(d)
            row.append(f"{s.f1:.3f}" if s else "—")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_notes(reports: list[CorpusReport]) -> str:
    lines: list[str] = []
    for r in reports:
        m = r.meta
        bits: list[str] = []
        if m.get("model"):
            rev = (m.get("revision") or "")[:8]
            bits.append(f"model `{m['model']}`" + (f" @ `{rev}`" if rev else ""))
        if m.get("device"):
            bits.append(f"device {m['device']}")
        if m.get("load_seconds") is not None:
            bits.append(f"load {m['load_seconds']:.1f} s")
        if m.get("threshold") is not None:
            bits.append(f"threshold {m['threshold']}")
        if m.get("out_of_schema"):
            bits.append("out-of-schema predictions dropped: " + ", ".join(
                f"{k}×{v}" for k, v in sorted(m["out_of_schema"].items())
            ))
        if m.get("mean_document_sensitivity") is not None:
            bits.append(f"mean document sensitivity {m['mean_document_sensitivity']:.2f}")
        if m.get("missing_docs"):
            bits.append(f"**not run on {len(m['missing_docs'])} corpus document(s)**: "
                        + ", ".join(m["missing_docs"]))
        lines.append(f"- **`{r.runner_name}`** — " + "; ".join(bits) + ".")
        for n in m.get("notes", []):
            lines.append(f"  - {n}")
    return "\n".join(lines)


def _full_report(reports: list[CorpusReport], title: str, prelude: str | None = None) -> str:
    n_docs = next((r.meta.get("n_docs") for r in reports if r.meta.get("n_docs")), None)
    n_docs = n_docs or max((len(r.per_doc) for r in reports), default=0)
    parts = [
        # Jekyll front matter so GitHub Pages renders the page through
        # the site layout instead of serving raw markdown.
        "---",
        f"title: {title}",
        "layout: default",
        "---",
        "",
        f"# {title}",
        "",
        *([prelude.rstrip(), ""] if prelude else []),
        f"Span-level F1 across the {n_docs}-document gold corpus in "
        "`benchmark/corpus/`. Lenient overlap matching, type-strict "
        "(the *any type* column drops the type constraint). "
        "*Public-body over-redaction*: share of whitelisted institution / "
        "statute mentions (not covered by gold) that the runner redacted — "
        "lower is better. *Sentence F1*: every runner projected onto a "
        "sentence grid (positive iff it flags any character of the "
        "sentence), the only level at which message classifiers can be "
        "compared. Throughput and peak RSS measured on this machine, one "
        "runner per process.",
        "",
        "## Aggregate",
        "",
        _render_summary_table(reports),
        "",
        "## Sentence level",
        "",
        _render_sentence_table(reports),
        "",
        "## Per document (F1)",
        "",
        _render_per_doc_table(reports),
        "",
        "## Per entity type",
        "",
    ]
    for r in reports:
        if r.meta.get("span_level", True):
            parts.append(_render_per_type_table(r))
            parts.append("")
    parts += ["## Runner notes", "", _render_notes(reports), ""]
    return "\n".join(parts)


# --- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runners", default=None,
                        help="Comma-separated runner names (default: Jude runners)")
    parser.add_argument("--list", action="store_true", help="List registered runners and exit")
    parser.add_argument("--json", type=Path, default=None,
                        help="Write the reports of this run to a JSON file")
    parser.add_argument("--render", nargs="*", type=Path, default=None,
                        help="Render a report from previously written JSON files instead of running")
    parser.add_argument("--report", type=Path, default=None,
                        help="Write the full markdown report to this path")
    parser.add_argument("--title", default="Jude redaction benchmark")
    parser.add_argument("--prelude", type=Path, default=None,
                        help="Markdown file inserted after the title (methodology, systems, …)")
    parser.add_argument("--postlude", type=Path, default=None,
                        help="Markdown file appended after the tables (analysis, conclusions)")
    args = parser.parse_args(argv)

    registry = _registry()
    if args.list:
        for name in registry:
            print(name)
        return

    if args.render is not None:
        reports: list[CorpusReport] = []
        for p in args.render:
            data = json.loads(p.read_text(encoding="utf-8"))
            reports.extend(report_from_dict(d) for d in (data if isinstance(data, list) else [data]))
        # Stored predictions, current gold: a corpus review must not
        # require re-running every model.
        corpus = _load_corpus()
        if corpus:
            for r in reports:
                rescore(r, corpus)
                if r.meta.get("missing_docs"):
                    print(f"  {r.runner_name}: not run on {len(r.meta['missing_docs'])} corpus "
                          f"document(s) — {', '.join(r.meta['missing_docs'][:5])}"
                          f"{' …' if len(r.meta['missing_docs']) > 5 else ''}; re-run to include them.")
    else:
        docs = _load_corpus()
        if not docs:
            raise SystemExit(f"No documents found in {CORPUS_DIR}")
        print(f"Loaded {len(docs)} documents from {CORPUS_DIR}")
        names = [n.strip() for n in args.runners.split(",")] if args.runners else list(DEFAULT_RUNNERS)
        unknown = [n for n in names if n not in registry]
        if unknown:
            raise SystemExit(f"Unknown runner(s): {unknown}. See --list.")
        reports = []
        for n in names:
            print(f"  Running {n} ...", flush=True)
            reports.append(run_one(n, registry[n], docs))
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps([report_to_dict(r) for r in reports], indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"JSON written to {args.json}")

    print()
    print(_render_summary_table(reports))

    if args.report:
        prelude = args.prelude.read_text(encoding="utf-8") if args.prelude else None
        body = _full_report(reports, args.title, prelude)
        if args.postlude:
            body += "\n" + args.postlude.read_text(encoding="utf-8").rstrip() + "\n"
        args.report.write_text(body, encoding="utf-8")
        print(f"\nFull report written to {args.report}")


if __name__ == "__main__":
    main()
