"""Synthetic corpus documents: spec → validated gold document.

A *spec* is what a drafting agent (or a person) writes: the document
text plus the distinct identifier surfaces it contains, typed. The
builder finds every occurrence of every surface (the annotation policy
is "every occurrence"), resolves nesting longest-first, and emits the
corpus JSON. The validator enforces the programmatic quality bar
Aymeric suggested: length, density and variety of identifiers, public
mentions present, long-tail traps present, language, no policy
conflicts with the public-knowledge whitelist. The last gate is a
lawyer's review in Word (`benchmark.docx_gold export`).

Spec format (`benchmark/synth/specs/<id>.json`):

    {
      "id": "doc_021_board_minutes_en",
      "title": "Minutes of the board — Project Ganymede",
      "language": "en",                 # en | fr | nl
      "genre": "board minutes",
      "split": "heldout",               # never used for tuning
      "text": "…450–900 words…",
      "entities": [                     # every DISTINCT surface, incl. short forms
        {"surface": "Kestrel Foods NV", "type": "ORG"},
        {"surface": "Kestrel", "type": "ORG"},
        {"surface": "Mr. Van Acker", "type": "PERSON"}
      ],
      "public": ["European Commission", "Article 101 TFEU"],   # must NOT be redacted
      "traps": ["codename", "honorific-only", "bare-domain"],
      "notes": "SHOULD redact: … SHOULD NOT: …"
    }

    python -m benchmark.synth validate benchmark/synth/specs/doc_021_board_minutes_en.json
    python -m benchmark.synth build    benchmark/synth/specs/*.json --out benchmark/corpus
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path

TYPES = ("PERSON", "ORG", "LOC", "EMAIL", "PHONE", "IBAN", "CASE_REF", "URL", "SECRET")
LANGUAGES = ("en", "fr", "nl")
TRAPS = (
    "codename",            # Project Ganymede — bare "Ganymede" later
    "vessel",              # M/V Aurelia
    "honorific-only",      # Mr. Tan after first mention
    "surname-only",        # "Van Acker" alone after "Pieter Van Acker"
    "bare-domain",         # kestrelfoods.example.com without https://
    "bank-acronym",        # BCEE, BIL, KBC as the only mention of the bank
    "acronym-defined",     # Kestrel Foods NV ("KFN") — later "KFN"
    "internal-docket",     # M-2026-GAN-004, ABC-2026-017
    "address",             # Avenue Louise 250, 1050 Brussels
    "adjacent-public",     # a party name right next to a public body
    "role-noise",          # "the Firm", "our client", "Counsel for the Claimant" — NOT identifiers
    "all-caps-header",     # KESTREL FOODS NV in a title line
)
MIN_WORDS, MAX_WORDS = 450, 900
MIN_GOLD, MIN_PUBLIC, MIN_TYPES, MIN_TRAPS = 12, 3, 4, 3


def _occurrences(text: str, surface: str) -> list[tuple[int, int]]:
    """All occurrences of `surface` not glued to another word character."""

    out: list[tuple[int, int]] = []
    pat = re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)")
    for m in pat.finditer(text):
        out.append((m.start(), m.end()))
    return out


def _resolve(spans: Iterable[tuple[int, int, str, str]]) -> list[dict]:
    """Longest-first, non-overlapping; returned sorted by start."""

    kept: list[tuple[int, int, str, str]] = []
    for s in sorted(spans, key=lambda x: (-(x[1] - x[0]), x[0])):
        if any(not (s[1] <= k[0] or k[1] <= s[0]) for k in kept):
            continue
        kept.append(s)
    kept.sort(key=lambda x: x[0])
    return [{"start": s, "end": e, "type": t, "text": txt} for s, e, t, txt in kept]


def build(spec: dict) -> dict:
    text = spec["text"]
    gold_c: list[tuple[int, int, str, str]] = []
    for ent in spec.get("entities", []):
        for s, e in _occurrences(text, ent["surface"]):
            gold_c.append((s, e, ent["type"], text[s:e]))
    gold = _resolve(gold_c)
    pub_c: list[tuple[int, int, str, str]] = []
    for surface in spec.get("public", []):
        for s, e in _occurrences(text, surface):
            if any(not (e <= g["start"] or g["end"] <= s) for g in gold):
                continue  # gold wins where the two overlap
            pub_c.append((s, e, "PUBLIC", text[s:e]))
    public = _resolve(pub_c)
    return {
        "id": spec["id"],
        "title": spec["title"],
        "language": spec["language"],
        "text": text,
        "gold_spans": gold,
        "public_spans": public,
        "notes": spec.get("notes", ""),
        "source": "agent-synthetic",
        "split": spec.get("split", "heldout"),
        "genre": spec.get("genre", ""),
        "traps": spec.get("traps", []),
    }


def validate(spec: dict) -> list[str]:
    """Programmatic quality bar. Empty list == acceptable."""

    errs: list[str] = []
    for key in ("id", "title", "language", "text", "entities"):
        if key not in spec:
            errs.append(f"missing field {key!r}")
    if errs:
        return errs
    if not re.fullmatch(r"doc_\d{3}_[a-z0-9_]+_(en|fr|nl)", spec["id"]):
        errs.append(f"id {spec['id']!r} must look like doc_021_board_minutes_en")
    if spec["language"] not in LANGUAGES:
        errs.append(f"language must be one of {LANGUAGES}")
    if not spec["id"].endswith("_" + spec["language"]):
        errs.append("id suffix must equal language")

    text = spec["text"]
    n_words = len(text.split())
    if not (MIN_WORDS <= n_words <= MAX_WORDS):
        errs.append(f"text has {n_words} words; need {MIN_WORDS}–{MAX_WORDS}")
    if "lorem" in text.lower() or "[…]" in text or "[...]" in text:
        errs.append("placeholder text found")

    seen: set[str] = set()
    for ent in spec["entities"]:
        surface, typ = ent.get("surface", ""), ent.get("type", "")
        if typ not in TYPES:
            errs.append(f"entity {surface!r}: type {typ!r} not in {TYPES}")
        if not surface.strip():
            errs.append("empty entity surface")
            continue
        if surface != surface.strip():
            errs.append(f"entity {surface!r} has edge whitespace")
        if surface in seen:
            errs.append(f"entity {surface!r} listed twice")
        seen.add(surface)
        if not _occurrences(text, surface):
            errs.append(f"entity {surface!r} does not occur in the text (exact, word-bounded)")

    built = build(spec)
    gold, public = built["gold_spans"], built["public_spans"]
    if len(gold) < MIN_GOLD:
        errs.append(f"only {len(gold)} gold spans; need ≥ {MIN_GOLD}")
    types = {g["type"] for g in gold}
    if len(types) < MIN_TYPES:
        errs.append(f"only {len(types)} entity types ({sorted(types)}); need ≥ {MIN_TYPES}")
    for surface in spec.get("public", []):
        if not _occurrences(text, surface):
            errs.append(f"public mention {surface!r} does not occur in the text")
    if len(public) < MIN_PUBLIC:
        errs.append(f"only {len(public)} public mentions; need ≥ {MIN_PUBLIC}")

    traps = spec.get("traps", [])
    unknown = [t for t in traps if t not in TRAPS]
    if unknown:
        errs.append(f"unknown traps {unknown}; choose from {TRAPS}")
    if len(traps) < MIN_TRAPS:
        errs.append(f"only {len(traps)} traps declared; need ≥ {MIN_TRAPS}")

    # Policy conflicts: a gold surface the bundled whitelist says is public.
    try:
        from jude.public_knowledge import is_public_no_redact
        from jude.types import EntityType

        for ent in spec["entities"]:
            try:
                et = EntityType(ent["type"])
            except ValueError:
                continue
            if is_public_no_redact(ent["surface"], et):
                errs.append(
                    f"entity {ent['surface']!r} is on the public-knowledge whitelist "
                    "(redact: false) — either it is public (move to 'public') or the "
                    "document must use an invented name"
                )
    except ImportError:  # pragma: no cover
        pass

    try:
        from jude.detect.language import detect_language

        detected = detect_language(text, supported=LANGUAGES)
        if detected and detected != spec["language"]:
            errs.append(f"text detected as {detected!r}, spec says {spec['language']!r}")
    except ImportError:  # pragma: no cover
        pass
    return errs


# --- CLI --------------------------------------------------------------------


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("specs", nargs="+", type=Path)
    b = sub.add_parser("build")
    b.add_argument("specs", nargs="+", type=Path)
    b.add_argument("--out", type=Path, default=Path(__file__).parent / "corpus")
    b.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    failed = 0
    for path in args.specs:
        spec = _load(path)
        errs = validate(spec)
        if errs:
            failed += 1
            print(f"✗ {path.name}")
            for e in errs:
                print(f"    - {e}")
            continue
        built = build(spec)
        by_type: dict[str, int] = {}
        for g in built["gold_spans"]:
            by_type[g["type"]] = by_type.get(g["type"], 0) + 1
        print(f"✓ {path.name}: {len(spec['text'].split())} words, "
              f"{len(built['gold_spans'])} gold {dict(sorted(by_type.items()))}, "
              f"{len(built['public_spans'])} public, traps {spec.get('traps', [])}")
        if args.cmd == "build":
            out = args.out / f"{spec['id']}.json"
            if out.exists() and not args.force:
                print(f"    exists, skipped (use --force): {out}")
                continue
            out.write_text(json.dumps(built, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"    → {out}")
    if failed:
        raise SystemExit(f"{failed} spec(s) failed validation")


if __name__ == "__main__":
    main()
