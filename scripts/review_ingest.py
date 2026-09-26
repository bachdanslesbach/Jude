"""Bring a lawyer's Word review back into the corpus, in one step.

For every review copy in `review/` that was saved in Word *after* its
corpus record was written, re-ingest it (highlights → gold spans; the
document's split, title and notes are kept), print what the review
changed, re-render both benchmark pages from the stored predictions
(no model runs), and show the held-out headline before and after.

    python scripts/review_ingest.py            # or double-click
    scripts/Réintégrer la relecture.command
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "review"
CORPUS = ROOT / "benchmark" / "corpus"
RESULTS = ROOT / "benchmark" / "results"
PY = sys.executable

JUDE_RUNNERS = ("jude-full", "jude-full-gliner-small", "jude-full-no-gliner",
                "jude-no-public-filter", "rules-only", "spacy-only", "regex-only")


def heldout_line() -> str:
    page = ROOT / "docs" / "benchmark-pii-models.md"
    if not page.exists():
        return "—"
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `jude-full` |") and "(" in line and line.count("|") == 4:
            return line
    return "—"


def run(args: list[str]) -> str:
    p = subprocess.run([PY, "-m", *args], cwd=ROOT, capture_output=True, text=True)
    return (p.stdout or "") + (p.stderr or "")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from benchmark.docx_gold import saved_since_export

    before = heldout_line()
    todo = saved_since_export(REVIEW)
    unknown = [p for p in saved_since_export(REVIEW, include_unknown=True) if p not in todo]
    if unknown:
        print("Ignorés (absents du manifeste d'export — ré-exportez-les d'abord) : "
              + ", ".join(p.name for p in unknown) + "\n")
    if not todo:
        print("Aucun fichier de review/ n'a été enregistré dans Word depuis son export : rien à réintégrer.")
        return 0

    print(f"{len(todo)} document(s) enregistré(s) dans Word depuis l'export :\n")
    for docx in todo:
        out = run(["benchmark.docx_gold", "ingest", str(docx), "--id", docx.stem, "--force"])
        changes = [l for l in out.splitlines()
                   if re.match(r"\s+[+\-~] ", l) or l.startswith("text changed") or "warning" in l]
        summary = next((l for l in out.splitlines() if "gold spans" in l and "chars" in l), "").strip()
        status = "aucun changement de surlignage" if not changes else f"{len(changes)} ligne(s) de changement"
        print(f"— {docx.stem}: {status}")
        for l in changes:
            print("   " + l.strip())
        if summary:
            print("   " + summary.split(": ", 1)[-1])
        if "Traceback" in out or "Error" in out:
            print("   !! erreur — sortie complète :")
            print(out)
        print()

    print("Re-scoring des prédictions enregistrées (aucun modèle à relancer)…")
    all_json = sorted(str(p) for p in RESULTS.glob("*.json"))
    run(["benchmark.run", "--render", *all_json, "--title", "PII models on legal documents",
         "--prelude", "benchmark/report_prelude.md", "--postlude", "benchmark/report_postlude.md",
         "--report", "docs/benchmark-pii-models.md"])
    jude_json = [str(RESULTS / f"{r}.json") for r in JUDE_RUNNERS if (RESULTS / f"{r}.json").exists()]
    run(["benchmark.run", "--render", *jude_json, "--report", "docs/benchmark.md"])
    after = heldout_line()
    print("\njude-full par part (dev | heldout) — avant :")
    print("  " + before)
    print("après :")
    print("  " + after)
    # A re-ingested copy is now in sync with the corpus: record it so the
    # next run only picks up files saved again.
    from benchmark.docx_gold import write_manifest
    write_manifest(REVIEW, todo)
    print("\nTerminé. Dites à Claude : « corpus relu : " + ", ".join(d.stem[:7] for d in todo) + " ».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
