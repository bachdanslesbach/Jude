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
      "language": "en",                 # en | fr
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
LANGUAGES = ("en", "fr")  # corpus policy: English and French only
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


# Real banks named by acronym may recur across documents (KBC finances
# half of Flanders); everything else an agent invents must be unique.
_ALLOWED_SHARED = frozenset({
    "kbc", "cbc", "ing", "belfius", "bnp", "bnp paribas", "bnp paribas fortis",
    "ubs", "bcee", "bil", "deutsche bank", "crédit agricole", "credit agricole",
    "société générale", "societe generale", "rabobank", "abn amro", "hsbc",
})
_HONORIFIC_RE = re.compile(
    r"^(?:Mr|Mrs|Ms|Mx|Dr|Prof|Me|M|Mme|Mlle|Maître|Monsieur|Madame|Dhr|Mevr|"
    r"Meester|Avv|Herr|Frau|Sir|Dame)\.?\s+"
)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")


def _last_token(surface: str) -> str | None:
    s = _HONORIFIC_RE.sub("", surface.strip())
    toks = [t for t in re.split(r"[\s'’-]+", s) if t]
    if not toks:
        return None
    last = toks[-1]
    return last if len(last) >= 4 and last[0].isupper() else None


def _bounded(surface: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)")


def collisions(
    spec: dict,
    corpus_dir: Path | str,
    specs_dir: Path | str | None = None,
) -> list[str]:
    """Surfaces of `spec` already used by another corpus document — or
    by a sibling spec in `specs_dir` that has not been built yet (agents
    drafting in parallel cannot see each other's work otherwise).

    Checked: exact PERSON/ORG/LOC surfaces (in the other document's
    gold or text), surnames shared between PERSON spans, exact
    identifiers, and 4+-digit runs (years excluded) shared between
    case references — the "0417" fingerprint. Banks by acronym, bare
    city names, "postcode city", bare first names and anything under
    `public` are allowed to recur.
    """

    errs: list[str] = []
    others = []
    for p in sorted(Path(corpus_dir).glob("doc_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("id") != spec.get("id"):
            others.append(d)
    seen_ids = {d["id"] for d in others}
    if specs_dir is not None:
        for p in sorted(Path(specs_dir).glob("doc_*.json")):
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
                if s.get("id") in seen_ids or s.get("id") == spec.get("id") or "text" not in s:
                    continue
                others.append(build(s))
            except (ValueError, KeyError):
                continue  # a sibling still being written is not our problem
    for ent in spec.get("entities", []):
        s, t = ent["surface"], ent["type"]
        if s.lower() in _ALLOWED_SHARED:
            continue
        if t == "LOC" and (not re.search(r"\d", s) or re.fullmatch(r"\d{4,5}\s+[^\d]+", s)):
            continue  # bare city / region names and "postcode city" recur legitimately; addresses must not
        if t == "PERSON" and len(_HONORIFIC_RE.sub("", s).split()) < 2:
            continue  # a bare first name is not a fingerprint
        pat = _bounded(s)
        last = _last_token(s) if t == "PERSON" else None
        runs = [r for r in re.findall(r"\d{4,}", s) if not _YEAR_RE.match(r)] if t == "CASE_REF" else []
        for d in others:
            golds = d.get("gold_spans", [])
            if any(g["text"] == s for g in golds) or pat.search(d.get("text", "")):
                errs.append(f"{t} {s!r} already used in {d['id']}")
                break
            if last and any(
                g["type"] == "PERSON" and _last_token(g["text"]) == last for g in golds
            ):
                errs.append(f"surname {last!r} (in {s!r}) already used in {d['id']}")
                break
            hit = next(
                (r for r in runs for g in golds if g["type"] == "CASE_REF" and r in g["text"]),
                None,
            )
            if hit:
                errs.append(f"reference fingerprint {hit!r} (in {s!r}) already used in {d['id']}")
                break
    return errs


def sweep(corpus_dir: Path | str) -> list[str]:
    """Cross-document reuse inside an existing corpus: surnames, ORG
    surfaces and reference fingerprints present in ≥ 2 documents."""

    import collections

    by_surname: dict[str, set[str]] = collections.defaultdict(set)
    by_org: dict[str, set[str]] = collections.defaultdict(set)
    by_run: dict[str, set[str]] = collections.defaultdict(set)
    for p in sorted(Path(corpus_dir).glob("doc_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for g in d.get("gold_spans", []):
            if g["type"] == "PERSON":
                last = _last_token(g["text"])
                if last:
                    by_surname[last].add(d["id"])
            elif g["type"] == "ORG" and g["text"].lower() not in _ALLOWED_SHARED:
                by_org[g["text"]].add(d["id"])
            elif g["type"] == "CASE_REF":
                for r in re.findall(r"\d{4,}", g["text"]):
                    if not _YEAR_RE.match(r):
                        by_run[r].add(d["id"])
    out = []
    for label, table in (("surname", by_surname), ("ORG", by_org), ("reference run", by_run)):
        for key, ids in sorted(table.items(), key=lambda kv: -len(kv[1])):
            if len(ids) >= 2:
                out.append(f"{label} {key!r} in {len(ids)} documents: {', '.join(sorted(ids))}")
    return out


def validate(
    spec: dict,
    corpus_dir: Path | str | None = None,
    specs_dir: Path | str | None = None,
) -> list[str]:
    """Programmatic quality bar. Empty list == acceptable. With
    `corpus_dir`, also refuse names / numbers already used elsewhere
    (and, with `specs_dir`, in sibling specs not yet built)."""

    errs: list[str] = []
    if corpus_dir is not None and "entities" in spec:
        errs.extend(collisions(spec, corpus_dir, specs_dir=specs_dir))
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
    corpus_default = Path(__file__).parent / "corpus"
    v = sub.add_parser("validate")
    v.add_argument("specs", nargs="+", type=Path)
    specs_default = Path(__file__).parent / "synth" / "specs"
    v.add_argument("--corpus", type=Path, default=corpus_default,
                   help="existing corpus to check name/number collisions against (default: benchmark/corpus)")
    v.add_argument("--specs", type=Path, default=specs_default,
                   help="sibling specs (not yet built) to check collisions against (default: benchmark/synth/specs)")
    b = sub.add_parser("build")
    b.add_argument("specs", nargs="+", type=Path)
    b.add_argument("--out", type=Path, default=corpus_default)
    b.add_argument("--corpus", type=Path, default=corpus_default)
    b.add_argument("--specs-dir", type=Path, default=specs_default)
    b.add_argument("--force", action="store_true")
    s = sub.add_parser("sweep", help="report names / numbers reused across corpus documents")
    s.add_argument("--corpus", type=Path, default=corpus_default)
    args = p.parse_args(argv)

    if args.cmd == "sweep":
        findings = sweep(args.corpus)
        for f in findings:
            print(f)
        print(f"{len(findings)} reuse(s) found" if findings else "no cross-document reuse")
        return

    failed = 0
    for path in args.specs:
        spec = _load(path)
        sd = args.specs if args.cmd == "validate" else args.specs_dir
        errs = validate(
            spec,
            corpus_dir=args.corpus if args.corpus.exists() else None,
            specs_dir=sd if sd.exists() else None,
        )
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
