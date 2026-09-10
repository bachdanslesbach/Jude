"""The unverified-term report — the fail-closed half of "no misses".

No detector reaches recall 1. What turns 0.97 into a guarantee is a
review step that is cheap and exhaustive: after redaction, list every
capitalised phrase and every identifier-shaped token that was neither
redacted nor recognised as public, in context, for one confirmation
pass. The detectors find what they can; this report shows the lawyer
exactly what they did not decide.

Noise is tolerated — a section heading, a defined term — a silent miss
is not. The filters below remove only what is never an identifier:
public bodies and statutes (the whitelist), legal roles and section
labels, months, currencies, demonyms, stop-words, and single common
words at the start of a sentence (unless the same word also appears
capitalised mid-sentence, which is how a name behaves).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from .detect.language import detect_language
from .detect.patterns import _DOMAIN_RE
from .detect.spacy_detector import _DEMONYMS, _LEGAL_HEADERS, _MONTHS, _stopwords_for
from .public_knowledge import is_public_no_redact
from .types import EntityType

_CAP = "A-ZÀ-ÝÆØ"
_CAP_WORD = rf"[{_CAP}][\w'’.-]*"
_CONNECTORS = r"(?:de|du|des|d'|d’|la|le|les|of|van|der|den|von|zu|y|di|da|&)"
_PHRASE_RE = re.compile(
    rf"(?<![\w'’]){_CAP_WORD}(?:(?:\s+{_CONNECTORS})*\s+{_CAP_WORD})*"
)
# Docket / matter / reference shapes: letters and digits mixed, with
# hyphens, slashes or colons — HIP-NOTUSE-2026-0098, B6-127/26,
# 1:26-cv-00489-RGA. Never a plain number, never a plain word.
_IDENTIFIER_RE = re.compile(
    r"(?<![\w/:-])(?=[\w/:.-]*\d)(?=[\w/:.-]*[A-Za-z])[A-Z0-9][\w/:.-]{3,}(?<![.:,;])"
)

_REVIEW_NOISE = frozenset({
    # document structure
    "article", "articles", "section", "sections", "clause", "clauses", "annex", "annexes",
    "schedule", "schedules", "exhibit", "exhibits", "appendix", "paragraph", "chapter",
    "part", "page", "pages", "date", "dated", "re", "subject", "from", "to", "cc", "bcc",
    "dear", "yours", "regards", "sincerely", "faithfully", "truly", "recitals", "whereas",
    "now", "therefore", "background", "summary", "introduction", "conclusion",
    "conclusions", "recommendation", "recommendations", "analysis", "facts", "issue",
    "issues", "question", "questions", "answer", "note", "notes", "memorandum", "memo",
    "draft", "confidential", "privileged", "attorney", "attorneys", "work", "product",
    "agenda", "minutes", "action", "actions", "item", "items", "overview", "details",
    "detail", "context", "objective", "objectives", "option", "options", "risk", "risks",
    "status", "update", "updates", "version", "phase", "step", "steps", "project",
    "definitions", "interpretation", "scope", "purpose", "term", "terms", "duration",
    "termination", "notices", "governing", "law", "laws", "jurisdiction", "counterparts",
    "entire", "agreement", "agreements", "amendment", "waiver", "severability",
    "assignment", "force", "majeure", "confidentiality", "data", "protection", "privacy",
    "compliance", "liability", "limitation", "indemnity", "indemnification", "warranties",
    "representations", "covenants", "undertakings", "events", "default", "remedies",
    "costs", "expenses", "taxes", "tax", "interest", "payment", "payments", "invoice",
    "invoices", "completion", "closing", "signing", "effective", "deadline", "total",
    "subtotal", "amount", "price", "fee", "fees", "rate", "rates", "condition",
    "conditions", "board", "directors", "shareholders", "meeting", "general", "special",
    "resolution", "resolutions", "commission", "regulation", "regulations", "directive",
    "act", "code", "authority", "authorities", "government", "state", "states", "member",
    "members", "union", "national", "federal", "regional", "local", "public", "private",
    "internal", "external", "group", "company", "companies", "holdings", "holding",
    "bank", "banks", "court", "courts", "tribunal", "counsel", "client", "clients",
    "customer", "customers", "supplier", "suppliers", "target", "targets", "key", "main",
    "new", "old", "first", "second", "third", "last", "final", "initial", "next",
    # numbering, currencies, units, time
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
    "eur", "usd", "gbp", "chf", "jpy", "cad", "aud", "sek", "nok", "dkk", "pln",
    "m", "bn", "k", "q1", "q2", "q3", "q4", "h1", "h2", "fy", "ytd", "am", "pm",
    "cet", "cest", "gmt", "utc", "id", "no", "nr", "ref", "tel", "fax", "email", "e-mail",
    "www", "http", "https", "pdf", "docx", "xlsx", "p", "pp", "vs", "cf", "eg", "ie",
    "etc", "nb", "ps",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag",
    # greetings / closings
    "yes", "ok", "thanks", "thank", "best", "kind", "hello", "hi", "bonjour", "bonsoir",
    "cordialement", "merci", "madame", "monsieur", "messieurs", "mesdames", "maître",
    "maîtres", "geachte", "beste", "groeten", "hoogachtend",
    # honorifics on their own
    "dr", "mr", "mrs", "ms", "mx", "prof", "me", "mme", "mlle", "dhr", "mevr",
})

_TRAILING_PUNCT = ".,;:'’\"”)]"


@dataclass(frozen=True)
class UnverifiedTerm:
    text: str
    count: int
    occurrences: tuple[tuple[int, int], ...]
    context: str


def _span_of(d) -> tuple[int, int]:  # noqa: ANN001 — Detection, PredSpan or dict
    if isinstance(d, dict):
        return int(d["start"]), int(d["end"])
    return int(d.start), int(d.end)


def _sentence_initial(text: str, start: int) -> bool:
    i = start - 1
    while i >= 0 and text[i] in " \t\"“”'’()[]«»":
        i -= 1
    if i < 0:
        return True
    return text[i] in ".!?:;\n•*"


def _normalise(s: str) -> str:
    s = re.sub(r"[^\w\s&-]", "", s).strip().lower()
    return re.sub(r"\s+", " ", s)


@lru_cache(maxsize=4)
def _noise_for(lang: str) -> frozenset[str]:
    return frozenset(
        _REVIEW_NOISE | _LEGAL_HEADERS | _DEMONYMS | _MONTHS
        | _stopwords_for(lang) | _stopwords_for("en")
    )


def _clean(text: str, start: int, end: int) -> tuple[int, int]:
    """Drop trailing punctuation and a possessive from a candidate."""

    while end > start and text[end - 1] in _TRAILING_PUNCT:
        # keep a dot that belongs to a short abbreviation: "Inc.", "S.A."
        if text[end - 1] == "." and "." in text[start:end - 1].split()[-1][:-0 or None]:
            break
        if text[end - 1] == "." and len(text[start:end - 1].split()[-1]) <= 3:
            break
        end -= 1
    if text[start:end].endswith(("'s", "’s")):
        end -= 2
    return start, end


def _is_noise_token(tok: str, noise: frozenset[str]) -> bool:
    n = _normalise(tok)
    return (
        not n
        or len(n) == 1
        or n in noise
        or is_public_no_redact(tok, EntityType.ORG)
    )


def unverified_terms(
    text: str,
    detections: Iterable = (),  # noqa: ANN001
    lang: str | None = None,
) -> list[UnverifiedTerm]:
    """Capitalised phrases and identifier-shaped tokens in `text` that
    no detection covers and no rule declares non-identifying. Grouped
    by surface (case-insensitive), ordered by first occurrence."""

    dets = sorted(_span_of(d) for d in detections)
    lang = lang or detect_language(text, supported=("en", "fr", "nl")) or "en"
    noise = _noise_for(lang)

    def covered(s: int, e: int) -> bool:
        return any(s < de and e > ds for ds, de in dets)

    # Identifier-shaped tokens first; mask them so the phrase scan does
    # not split "B6-127/26" at the slash.
    candidates: list[tuple[int, int, bool]] = []  # (start, end, identifier?)
    masked = list(text)
    # Bare domains are lowercase and would never make the capitalised
    # scan; they identify a business as surely as its name.
    for rx in (_IDENTIFIER_RE, _DOMAIN_RE):
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if any(cs <= s and e <= ce for cs, ce, _ in candidates):
                continue
            candidates.append((s, e, True))
            for i in range(s, e):
                masked[i] = " "
    masked_text = "".join(masked)
    for m in _PHRASE_RE.finditer(masked_text):
        s, e = _clean(text, m.start(), m.end())
        if e > s:
            candidates.append((s, e, False))

    groups: dict[str, list[tuple[int, int, bool, bool]]] = {}
    order: list[str] = []
    for s, e, is_ident in sorted(candidates):
        surface = text[s:e]
        if covered(s, e):
            continue
        key = _normalise(surface)
        if not key:
            continue
        if not is_ident:
            if key in noise or is_public_no_redact(surface, EntityType.ORG):
                continue
            tokens = [t for t in surface.split() if _normalise(t)]
            if all(_is_noise_token(t, noise) for t in tokens):
                continue
        groups.setdefault(key, []).append((s, e, is_ident, _sentence_initial(text, s)))
        if key not in order:
            order.append(key)

    out: list[UnverifiedTerm] = []
    for key in order:
        occ = groups[key]
        s0, e0, is_ident, _ = occ[0]
        surface = text[s0:e0]
        single_word = len(surface.split()) == 1
        all_caps = surface.isupper() and len(surface) >= 2
        if (single_word and not is_ident and not all_caps
                and all(si for _, _, _, si in occ)):
            continue  # a common word capitalised only by sentence position
        ctx_s, ctx_e = max(0, s0 - 40), min(len(text), e0 + 40)
        context = (text[ctx_s:s0] + "⟦" + surface + "⟧" + text[e0:ctx_e]).replace("\n", " ")
        out.append(UnverifiedTerm(
            text=surface,
            count=len(occ),
            occurrences=tuple((s, e) for s, e, _, _ in occ),
            context=("…" if ctx_s > 0 else "") + context + ("…" if ctx_e < len(text) else ""),
        ))
    return out
