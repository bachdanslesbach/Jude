"""The model-size / throughput / quality ladder, from saved results.

Reads `benchmark/results/*.json`, attaches a parameter count to each
runner, and renders (a) a markdown table sorted by size and (b) a
log–log chart (parameters × pages per second, colour = recall) that
`docs/efficiency-frontier.md` embeds. A page is 3,000 characters.

    python -m benchmark.ladder --results benchmark/results --out docs/assets/efficiency-frontier.png
    python -m benchmark.ladder --results benchmark/results --markdown   # table to stdout
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .serialize import report_from_dict

CHARS_PER_PAGE = 3_000

# Parameters that run per document (millions). Encoders measured with
# sum(p.numel()); pipelines are the sum of their neural components.
#   en_core_web_trf     RoBERTa-base                       125 M
#   fr/nl_core_news_md  CNN, ~15 M each, on FR/NL text only
#   gliner_small/medium/large-v2.1                         ≈ 50 / 90 / 440 M (DeBERTa-v3 backbones)
#   nvidia/gliner-PII   = gliner_large backbone            440 M
#   pplx-pii-masking    Qwen3 0.6B encoder (measured 596 M)
#   roblox              XLM-RoBERTa-large                  560 M
#   qwen3:4b / :8b      4.0 B / 8.2 B (generative)
PARAMS_M: dict[str, float] = {
    "regex-only": 0.0,
    "rules-only": 0.0,
    "spacy-only": 125.0,
    "jude-full-no-gliner": 125.0,
    "gliner-small-v2.1-jude-labels": 50.0,
    "gliner-medium-v2.1-jude-labels": 90.0,
    "gliner-large-v2.1-jude-labels": 440.0,
    "gliner-large-v2.1-jude-labels-cpu": 440.0,
    "nvidia-gliner-pii-native": 440.0,
    "nvidia-gliner-pii-native-t03": 440.0,
    "nvidia-gliner-pii-jude-labels": 440.0,
    "jude-full-gliner-small": 175.0,
    "jude-full-gliner-medium": 215.0,
    "jude-full": 565.0,
    "jude-no-public-filter": 565.0,
    "pplx-pii-masking": 596.0,
    "pplx-pii-masking-cpu": 596.0,
    "roblox-pii-classifier": 560.0,
    "ollama-qwen3-4b": 4_000.0,
    "ollama-qwen3-8b": 8_200.0,
}

# The ladder proper: one row per rung, in the order the page discusses them.
LADDER_ORDER = [
    "rules-only", "regex-only",
    "gliner-small-v2.1-jude-labels", "gliner-medium-v2.1-jude-labels",
    "spacy-only", "jude-full-no-gliner",
    "jude-full-gliner-small", "jude-full-gliner-medium",
    "gliner-large-v2.1-jude-labels", "gliner-large-v2.1-jude-labels-cpu",
    "nvidia-gliner-pii-native", "jude-full",
    "pplx-pii-masking", "pplx-pii-masking-cpu", "roblox-pii-classifier",
    "ollama-qwen3-4b", "ollama-qwen3-8b",
]


def load_reports(results_dir: Path) -> dict:
    reports = {}
    for p in sorted(results_dir.glob("*.json")):
        for d in json.loads(p.read_text(encoding="utf-8")):
            r = report_from_dict(d)
            reports[r.runner_name] = r
    return reports


def rows(reports: dict) -> list[dict]:
    out = []
    for name in LADDER_ORDER:
        r = reports.get(name)
        if r is None:
            continue
        m = r.meta
        cps = m.get("chars_per_sec") or 0.0
        span = m.get("span_level", True)
        pb = m.get("public_body_over_redaction") or {}
        out.append({
            "runner": name,
            "params_m": PARAMS_M.get(name),
            "device": m.get("device", "cpu"),
            "pages_per_s": cps / CHARS_PER_PAGE,
            "s_per_page": (CHARS_PER_PAGE / cps) if cps else None,
            "f1": r.aggregate.f1 if span else None,
            "recall": r.aggregate.recall if span else None,
            "precision": r.aggregate.precision if span else None,
            "over_redaction": pb.get("rate"),
            "sentence_f1": (m.get("sentence_level") or {}).get("f1"),
            "peak_rss_mb": m.get("peak_rss_mb"),
        })
    return out


def _f(x, nd=3, pct=False):  # noqa: ANN001
    if x is None:
        return "—"
    return f"{x:.0%}" if pct else f"{x:.{nd}f}"


def markdown_table(rs: list[dict]) -> str:
    lines = ["| Runner | Params | Device | Pages / s | s / page | Recall | Precision | F1 | Public-body over-redaction | Peak RSS |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rs:
        pm = r["params_m"]
        params = "0" if pm == 0 else (f"{pm/1000:.1f} B" if pm and pm >= 1000 else (f"{pm:.0f} M" if pm else "—"))
        lines.append(
            f"| `{r['runner']}` | {params} | {r['device']} | {_f(r['pages_per_s'], 2)} | "
            f"{_f(r['s_per_page'], 1)} | {_f(r['recall'])} | {_f(r['precision'])} | **{_f(r['f1'])}** | "
            f"{_f(r['over_redaction'], pct=True)} | {_f(r['peak_rss_mb'], 0)} MB |"
        )
    return "\n".join(lines)


def chart(rs: list[dict], out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.subplots_adjust(right=0.68)
    legend_lines: list[str] = []
    n = 0
    for r in rs:
        if r["params_m"] is None or not r["pages_per_s"]:
            continue
        n += 1
        x = max(r["params_m"], 1.0)  # 0 params plotted at 1 M on the log axis
        y = r["pages_per_s"]
        span_level = r["recall"] is not None
        rec = r["recall"] if span_level else (r["sentence_f1"] or 0.0)
        ax.scatter(x, y, s=120 + 500 * (rec ** 4), c=[[0.15, 0.35 + 0.6 * rec, 0.3]],
                   edgecolors="black", linewidths=0.6, alpha=0.85,
                   marker="o" if span_level else "D", zorder=3)
        ax.annotate(str(n), (x, y), ha="center", va="center", fontsize=7,
                    fontweight="bold", color="white", zorder=4)
        pm = r["params_m"]
        size = "0" if pm == 0 else (f"{pm/1000:.1f} B" if pm >= 1000 else f"{pm:.0f} M")
        metric = f"R {rec:.2f}" if span_level else f"sentence F1 {rec:.2f}"
        short = (r["runner"].replace("-v2.1-jude-labels", " (jude labels)")
                 .replace("nvidia-gliner-pii-native", "nvidia-gliner-pii")
                 .replace("-pii-classifier", "").replace("-pii-masking", ""))
        legend_lines.append(f"{n:>2}  {short}\n    {size}, {r['device']} · {metric} · {y:.2f} p/s")
    fig.text(0.66, 0.90, "\n".join(legend_lines), fontsize=6.5, family="monospace",
             va="top", ha="left")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("parameters (M, log) — 0 plotted at 1")
    ax.set_ylabel("pages per second (log), page = 3,000 chars")
    for yv, txt in [(0.1, "1 page / 10 s"), (1.0, "1 page / s"), (10.0, "10 pages / s")]:
        ax.axhline(yv, color="grey", linewidth=0.6, linestyle="--")
        ax.text(1.05, yv * 1.08, txt, fontsize=7, color="grey")
    for xv, txt in [(100, "0.1 B"), (1000, "1 B"), (100_000, "100 B")]:
        ax.axvline(xv, color="grey", linewidth=0.6, linestyle=":")
        ax.text(xv * 1.05, ax.get_ylim()[0] * 1.3 if ax.get_ylim()[0] > 0 else 0.01, txt, fontsize=7, color="grey")
    ax.set_title("Size × speed × recall on the legal corpus (Apple M2, 8 GB; marker area ∝ recall⁴)")
    fig.subplots_adjust(left=0.07, right=0.64, top=0.93, bottom=0.09)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)


def inject(page: Path, table: str, chart_rel: str) -> None:
    """Replace the LADDER_TABLE / LADDER_CHART markers in `page` (keeping
    the markers so the page can be regenerated)."""

    text = page.read_text(encoding="utf-8")
    text = _replace_block(text, "LADDER_TABLE", table)
    text = _replace_block(
        text, "LADDER_CHART",
        f"![Size × speed × recall on the legal corpus]({chart_rel})",
    )
    page.write_text(text, encoding="utf-8")


def _replace_block(text: str, marker: str, body: str) -> str:
    import re

    start, end = f"<!-- {marker} -->", f"<!-- /{marker} -->"
    block = f"{start}\n{body}\n{end}"
    if end in text:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    return text.replace(start, block)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=Path(__file__).parent / "results")
    p.add_argument("--out", type=Path, default=None, help="PNG path for the chart")
    p.add_argument("--markdown", action="store_true", help="print the table")
    p.add_argument("--inject", type=Path, default=None,
                   help="markdown page whose LADDER_TABLE / LADDER_CHART markers receive the table and chart")
    args = p.parse_args(argv)
    rs = rows(load_reports(args.results))
    if args.markdown or not (args.out or args.inject):
        print(markdown_table(rs))
    if args.out:
        chart(rs, args.out)
        print(f"chart written to {args.out}")
    if args.inject:
        rel = args.out.name if args.out else "efficiency-frontier.png"
        inject(args.inject, markdown_table(rs), f"assets/{rel}")
        print(f"table and chart injected into {args.inject}")


if __name__ == "__main__":
    main()
