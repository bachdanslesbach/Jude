"""Benchmark orchestrator.

Runs every registered runner against every gold document in
`benchmark/corpus/`, computes per-runner aggregate F1, and prints a
markdown table to stdout. With `--report path.md` it also writes the
full report (per-document breakdown + per-type breakdown) to disk so
we can commit the latest score next to the code.

    python -m benchmark.run                    # print summary
    python -m benchmark.run --report docs/benchmark.md   # write full report
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .evaluate import score_corpus
from .schema import CorpusReport, GoldDocument

CORPUS_DIR = Path(__file__).parent / "corpus"


def _load_corpus() -> list[GoldDocument]:
    docs = []
    for p in sorted(CORPUS_DIR.glob("doc_*.json")):
        docs.append(GoldDocument.from_json(p))
    return docs


def _all_runners():
    from .runners.jude_full import JudeFullRunner
    from .runners.jude_no_filter import JudeNoFilterRunner
    from .runners.regex_only import RegexOnlyRunner
    from .runners.spacy_only import SpacyOnlyRunner

    return [
        JudeFullRunner(),
        JudeNoFilterRunner(),
        SpacyOnlyRunner(),
        RegexOnlyRunner(),
    ]


def _render_summary_table(reports: list[CorpusReport]) -> str:
    out = ["| Runner | Precision | Recall | F1 | TP | FP | FN |",
           "|---|---|---|---|---|---|---|"]
    for r in reports:
        a = r.aggregate
        out.append(
            f"| `{r.runner_name}` | {a.precision:.3f} | {a.recall:.3f} | "
            f"**{a.f1:.3f}** | {a.tp} | {a.fp} | {a.fn} |"
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
    """Per-document F1 across runners — shows where each runner under- or
    over-performs the average."""

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


def _full_report(reports: list[CorpusReport]) -> str:
    parts = [
        "# Jude redaction benchmark",
        "",
        "Span-level F1 across the 5-document gold corpus in "
        "`benchmark/corpus/`. Lenient overlap matching, type-strict.",
        "",
        "## Aggregate",
        "",
        _render_summary_table(reports),
        "",
        "## Per document (F1)",
        "",
        _render_per_doc_table(reports),
        "",
        "## Per entity type",
        "",
    ]
    for r in reports:
        parts.append(_render_per_type_table(r))
        parts.append("")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=None,
                        help="Write the full markdown report to this path")
    args = parser.parse_args()

    docs = _load_corpus()
    if not docs:
        raise SystemExit(f"No documents found in {CORPUS_DIR}")
    print(f"Loaded {len(docs)} documents from {CORPUS_DIR}")

    runners = _all_runners()
    reports = []
    for r in runners:
        print(f"  Running {r.name} ...")
        reports.append(score_corpus(r, docs))

    print()
    print(_render_summary_table(reports))

    if args.report:
        args.report.write_text(_full_report(reports), encoding="utf-8")
        print(f"\nFull report written to {args.report}")


if __name__ == "__main__":
    main()
