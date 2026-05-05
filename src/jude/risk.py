"""Heuristic re-identification risk assessor.

Pseudonymisation alone is not anonymisation. An entity can remain
identifiable from context — most obviously through specific financial
figures, dates, case references, or via a public-knowledge tag whose
own population of candidates is small (e.g. "DMA-designated gatekeeper"
narrows to seven entities).

This module flags those structural signals so the user can notice them
before sending a redacted prompt. It is *not* a formal k-anonymity
guarantee; treat it as a checklist that mirrors what a careful human
reader would notice.

Scoring is deliberately conservative. Each signal contributes a small
integer; totals map to LOW (0–1) / MEDIUM (2–3) / HIGH (4+). The
reasons list is exposed verbatim to the UI.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel

from .types import Entity, Mode

# Co-occurrence signals are evaluated within the same paragraph as the
# pseudonym mention. Paragraphs are separated by one or more blank lines.
# This is more legible than a fixed-character window: a reader looking at
# the redacted document immediately understands "the same paragraph"
# without having to count characters.

# Currency figure: optional symbol/code, then digits with separators,
# optionally a decimal part, optionally a magnitude word.
_CURRENCY_RE = re.compile(
    r"(?:[€$£¥]|EUR|USD|GBP|CHF|SEK|JPY)\s?"
    r"\d{1,3}(?:[,. ]\d{3})+"
    r"(?:\.\d+)?"
    r"(?:\s?(?:million|billion|trillion|m|bn|bn\.|M|Bn|Tn))?",
)

# Specific calendar dates (English + French long forms; ISO; numeric).
_MONTHS_EN = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_MONTHS_FR = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    "septembre|octobre|novembre|décembre|decembre"
)
_DATE_RE = re.compile(
    rf"(?:"
    rf"\b\d{{1,2}}\s+(?:{_MONTHS_EN}|{_MONTHS_FR})\s+\d{{4}}\b"   # 13 October 2023
    rf"|\b(?:{_MONTHS_EN})\s+\d{{1,2}},?\s+\d{{4}}\b"             # October 13, 2023
    rf"|\b\d{{4}}-\d{{2}}-\d{{2}}\b"                              # 2023-10-13
    rf"|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b"                          # 13/10/2023
    rf")",
    re.IGNORECASE,
)

# EU case references covered by the regex detector — same patterns.
_CASE_REF_RE = re.compile(
    r"(?:Case|Affaire|Aff\.?)\s*[CT]-\d+/\d{2}(?:\s*P)?"
    r"|ECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[A-Z0-9.]+",
    re.IGNORECASE,
)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAssessment(BaseModel):
    entity_id: int
    pseudonym: str
    level: RiskLevel
    score: int
    reasons: list[str]


def assess_risks(
    text: str,
    entities: list[Entity],
    mode: Mode,
) -> list[RiskAssessment]:
    """Score every entity for structural re-identification risk in `text`."""

    out: list[RiskAssessment] = []
    for ent in entities:
        out.append(_score_one(text, ent, mode))
    out.sort(key=lambda r: r.score, reverse=True)
    return out


def _score_one(text: str, ent: Entity, mode: Mode) -> RiskAssessment:
    score = 0
    reasons: list[str] = []

    # Find all pseudonym mentions in the text (word-boundary matched).
    pattern = re.compile(rf"(?<!\w){re.escape(ent.pseudonym)}(?!\w)")
    mentions = [(m.start(), m.end()) for m in pattern.finditer(text)]

    # --- public-knowledge tag signals ---
    if mode == Mode.SMART and ent.public_context:
        score += 1
        reasons.append(
            "Public-knowledge tag attached — narrows the population of "
            "candidate entities."
        )
        if _canonical_in_context(ent):
            score += 3
            reasons.append(
                "The entity's canonical name appears inside its own public "
                "context tag (the tag itself leaks the identity)."
            )

    # --- co-occurrence signals (only when the entity is actually mentioned) ---
    if mentions:
        neighbourhood_text = _gather_paragraphs_containing(text, mentions)
        if _CURRENCY_RE.search(neighbourhood_text):
            score += 1
            reasons.append(
                "A specific currency figure appears in the same paragraph "
                "as the pseudonym."
            )
        if _DATE_RE.search(neighbourhood_text):
            score += 1
            reasons.append(
                "A specific calendar date appears in the same paragraph "
                "as the pseudonym."
            )
        if _CASE_REF_RE.search(neighbourhood_text):
            score += 1
            reasons.append(
                "A specific EU case reference appears in the same paragraph "
                "as the pseudonym."
            )

    return RiskAssessment(
        entity_id=ent.id,  # type: ignore[arg-type]
        pseudonym=ent.pseudonym,
        level=_level_for(score),
        score=score,
        reasons=reasons,
    )


def _canonical_in_context(ent: Entity) -> bool:
    if not ent.public_context:
        return False
    return ent.canonical.lower() in ent.public_context.lower()


def _gather_paragraphs_containing(
    text: str, mentions: list[tuple[int, int]]
) -> str:
    """Return the concatenation of every paragraph containing at least one
    of the mentions. Paragraphs are runs of non-blank lines separated by
    blank lines. Each paragraph is included at most once."""

    if not mentions:
        return ""
    paragraphs = _split_paragraphs(text)
    keep: list[str] = []
    for p_start, p_text in paragraphs:
        p_end = p_start + len(p_text)
        if any(p_start <= m_start < p_end for m_start, _ in mentions):
            keep.append(p_text)
    return "\n\n".join(keep)


def _split_paragraphs(text: str) -> list[tuple[int, str]]:
    """(start_offset, paragraph_text) for each non-empty paragraph."""

    out: list[tuple[int, str]] = []
    cursor = 0
    for match in re.finditer(r"\n\s*\n+", text):
        chunk = text[cursor:match.start()]
        if chunk.strip():
            out.append((cursor, chunk))
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        out.append((cursor, tail))
    return out


def _level_for(score: int) -> RiskLevel:
    if score >= 4:
        return RiskLevel.HIGH
    if score >= 2:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
