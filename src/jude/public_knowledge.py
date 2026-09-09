"""Public-knowledge whitelist — institutions that should NEVER be redacted.

The bundled known-entities dataset (`src/jude/data/known_entities.json`)
classifies each entry with a boolean `redact` flag:

  * `redact: true`   — public companies (Amazon, Microsoft, etc.).
                       Their corporate identity is public, but in any
                       given matter they may BE the client or a
                       counterparty whose involvement is confidential,
                       so we still pseudonymise them.
  * `redact: false`  — public institutions, regulators, courts, NCAs,
                       DPAs, financial bodies. Their mention in a
                       legal document does not identify a client; on
                       the contrary, redacting them forces the LLM to
                       reason without any regulatory framing.

This module exposes `is_public_no_redact(text, entity_type)` which
matches the surface form against the bundled set's `redact: false`
entries (canonical + aliases, normalised). Used by the redact
pipeline to skip these entities entirely.
"""

from __future__ import annotations

from functools import lru_cache

from .context import _load_bundled  # cached loader, returns dict records
from .types import EntityType, normalize_surface


@lru_cache(maxsize=1)
def _no_redact_index() -> dict[tuple[str, str], dict]:
    """{(normalized_form, type): record} for every bundled entry whose
    `redact` is explicitly false. Loads once per process."""

    index: dict[tuple[str, str], dict] = {}
    for rec in _load_bundled():
        if rec.get("redact", True):
            continue  # default: redactable
        for norm in rec.get("_normalized_aliases", set()):
            index[(norm, rec["type"])] = rec
    return index


# Leading definite/indefinite articles in EN/FR/DE that spaCy commonly
# absorbs into its entity spans ("the European Commission" instead of
# "European Commission"). Stripped before alias lookup so the filter
# still fires.
_LEADING_ARTICLES = (
    "the ", "a ", "an ",
    "le ", "la ", "les ", "l'", "l’", "un ", "une ",
    "der ", "die ", "das ", "den ", "dem ", "des ",
    "el ", "los ", "las ", "il ", "lo ", "gli ", "i ",
    "de ", "het ",
)


@lru_cache(maxsize=1)
def _no_redact_names() -> set[str]:
    """Set of normalised canonical/alias forms regardless of type. Used
    as a fallback when spaCy mislabels a known institution (e.g. it
    sometimes labels 'Bundeskartellamt' as PERSON or LOC)."""

    names: set[str] = set()
    for rec in _load_bundled():
        if rec.get("redact", True):
            continue
        names.update(rec.get("_normalized_aliases", set()))
    return names


# Nationality adjectives NER models glue onto institution names
# ("Belgian SPF Finances", "Autorité de la concurrence française").
# Stripped at either end before alias lookup. Accent-free variants
# included because `normalize_surface` may fold diacritics.
_DEMONYM_TOKENS = frozenset({
    "belgian", "french", "german", "dutch", "swiss", "british", "european",
    "italian", "spanish", "american", "luxembourg", "luxembourgish", "irish",
    "us", "uk", "eu",
    "belge", "belges", "française", "francaise", "français", "francais",
    "allemande", "allemand", "néerlandaise", "neerlandaise", "néerlandais",
    "neerlandais", "suisse", "européenne", "europeenne", "européen", "europeen",
    "italienne", "italien", "espagnole", "espagnol", "britannique",
    "américaine", "americaine", "américain", "americain",
    "belgische", "belgisch", "franse", "frans", "duitse", "duits",
    "nederlandse", "nederlands", "europese", "europees", "britse", "brits",
})


def _strip_demonyms(norm: str) -> str:
    tokens = norm.split()
    while tokens and tokens[0] in _DEMONYM_TOKENS:
        tokens.pop(0)
    while tokens and tokens[-1] in _DEMONYM_TOKENS:
        tokens.pop()
    return " ".join(tokens)


def is_public_no_redact(text: str, entity_type: EntityType) -> bool:
    """True if `text` matches a bundled public-knowledge entity that is
    flagged as `redact: false`. Lookup strategy:

      1. (normalised, type) exact match.
      2. Article-stripped (normalised, type) match.
      3. Type-agnostic name match — covers spaCy's tendency to mislabel
         institutional names as PERSON or LOC. The bundled redact=false
         entries are heavyweight institutions / regulations that no
         real person or place would plausibly share a name with.
      4. Steps 1–3 again with nationality adjectives stripped from
         either end ("Belgian SPF Finances", "Autorité de la
         concurrence française"). A demonym alone never matches.
    """

    norm = normalize_surface(text)
    if not norm:
        return False
    idx = _no_redact_index()
    names = _no_redact_names()

    def _lookup(n: str) -> bool:
        if (n, entity_type.value) in idx:
            return True
        for art in _LEADING_ARTICLES:
            if n.startswith(art):
                stripped = n[len(art):].strip()
                if stripped and (stripped, entity_type.value) in idx:
                    return True
                if stripped and stripped in names:
                    return True
        return n in names

    if _lookup(norm):
        return True
    without_demonyms = _strip_demonyms(norm)
    if without_demonyms and without_demonyms != norm:
        for art in _LEADING_ARTICLES:
            if without_demonyms.startswith(art):
                without_demonyms = without_demonyms[len(art):].strip()
                break
        return _lookup(without_demonyms)
    return False
