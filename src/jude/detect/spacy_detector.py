from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from ..types import Detection, DetectionSource, EntityType
from .language import detect_language, split_into_paragraphs

if TYPE_CHECKING:
    import spacy.language


_MODEL_FALLBACKS: dict[str, list[str]] = {
    # English: prefer the transformer pipeline (RoBERTa-base under the
    # hood, ~0.91 F1 OntoNotes vs ~0.85 for _lg). The trf model adds
    # ~400 MB on disk and is slower at inference (still <1s/page on
    # M-series), but the recall gain on short ORG acronyms (UBS) and
    # short city names (Brussels, Luxembourg) is material — see
    # docs/benchmark.md.
    "en": ["en_core_web_trf", "en_core_web_lg", "en_core_web_md"],
    "fr": ["fr_core_news_md"],
    "nl": ["nl_core_news_md"],
}


_LABEL_MAP: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "PER": EntityType.PERSON,
    "ORG": EntityType.ORG,
    "GPE": EntityType.LOC,
    "LOC": EntityType.LOC,
    "FAC": EntityType.LOC,
}


_MONTHS = frozenset(
    {
        # English
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
        "oct", "nov", "dec",
        # French
        "janvier", "février", "fevrier", "mars", "avril", "mai", "juin",
        "juillet", "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
        # Dutch
        "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december",
    }
)


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_PUNCT_STRIP = " \t.,;:'\""

# Section/page-marker patterns. spaCy frequently labels the marker
# *itself* as an ORG. These patterns are document structure that the
# user's tooling injected (Sheet markers from XLSX, anything matching
# `--- ... ---`) and must never be redacted.
_MARKER_RE = re.compile(r"^-{2,}\s*[\w\s:.()-]*?\s*-{2,}$")

# Common labels in legal / business documents that spaCy occasionally
# mislabels as ORG when they appear capitalised at the start of a line
# or in a heading. These are document-structure tokens, not entities.
# Stored normalised (lowercase, no punctuation) for fast lookup.
_SALUTATION_PREFIXES = (
    "dear ", "cher ", "chère ", "chers ", "chères ",
    "monsieur ", "madame ", "mr. ", "mrs. ", "ms. ",
    "geachte ", "geachte heer ", "geachte mevrouw ",
    "sehr geehrter ", "sehr geehrte ", "sehr geehrte herr ",
    "estimado ", "estimada ",
)

_LEGAL_HEADERS = frozenset({
    # Roles in transaction docs
    "buyer", "seller", "purchaser", "vendor", "offtaker", "supplier",
    "lender", "borrower", "guarantor", "obligor", "creditor", "debtor",
    "client", "counsel", "solicitor", "attorney", "advocate",
    "lessor", "lessee", "licensor", "licensee",
    "drafter", "drafters", "parties", "party", "principal", "agent",
    # Document classifications
    "draft", "working draft", "final", "confidential", "privileged",
    "for discussion", "for review", "internal", "executed",
    "annex", "exhibit", "schedule", "appendix",
    # Section labels frequently capitalised at line start
    "subject", "from", "to", "date", "re",
    "memorandum", "memo", "minutes", "agenda",
    "structure", "transaction structure", "background", "recitals",
    "considerations", "definitions", "interpretation",
    "representations", "warranties", "indemnification",
    "termination", "miscellaneous", "boilerplate",
    "governing law", "jurisdiction", "dispute resolution",
    "force majeure", "confidentiality clause",
    "regulatory considerations", "regulatory considerations",
    "control review", "merger control",
    # Common short labels
    "section", "article", "chapter", "clause", "paragraph",
    "title", "heading", "subheading",
    # Bare data-field labels that spaCy sometimes flags
    "iban", "swift", "bic", "vat", "tva", "siren", "siret",
    # Generic firm-organisation labels frequently flagged as ORG
    "firm", "the firm", "associates", "and associates",
    "department", "team", "office",
    # Function / role labels (departments inside organisations)
    "hr", "human resources", "people ops", "people operations",
    "dpo", "data protection officer",
    "cfo", "ceo", "coo", "cto", "general counsel", "in-house counsel",
    "compliance", "compliance team", "legal", "legal team",
    "finance", "operations", "engineering", "product",
    "audit", "audit committee", "supervisory board", "board",
    # Salutations & closings (EN/FR/NL/DE) — common false positives
    "dear", "cher", "chère", "chers", "chères",
    "best regards", "kind regards", "yours sincerely", "yours truly",
    "sincerely", "regards", "best",
    "bien", "bien à vous", "cordialement", "à vous",
    "geachte", "geachte collega", "met vriendelijke groet",
    "collega",
    "mit freundlichen grüßen", "hochachtungsvoll",
    # Adjective + entity-class combinations spaCy fuses badly
    "société anonyme", "belgian société", "french société",
    "luxembourg société", "société à responsabilité limitée",
    # Project-codename-style ALL CAPS ORG-fusions
    "aurora", "atlas", "helios", "eclipse", "solaris",
    # Misc nouns spaCy flags as ORG/LOC for no good reason
    "coentreprise", "joint venture", "joint-venture",
    # Legal-term phrases without intrinsic entity meaning
    "regulation", "directive", "treaty",
    # Litigation roles and defined terms — never identifiers on their own
    "claimant", "claimants", "defendant", "defendants", "respondent",
    "respondents", "applicant", "applicants", "plaintiff", "plaintiffs",
    "appellant", "appellee", "petitioner", "intervener", "witness",
    "undersigned", "counterparty", "target", "company", "group",
    "escrow", "escrow agent", "trustee", "receiver", "liquidator",
    "court", "district court", "tribunal", "the court",
    "demandeur", "demanderesse", "défendeur", "défenderesse", "requérant",
    "requérante", "partie", "parties",
    "eiser", "verweerder", "partij", "partijen",
})

# Determiners and possessives that turn a role into a phrase spaCy or
# GLiNER then label as an entity: "the Client", "our client", "its
# counsel". Stripped before the stop-list lookup.
_ROLE_PREFIXES = (
    "the ", "our ", "its ", "your ", "their ", "his ", "her ", "my ", "a ", "an ",
    "le ", "la ", "les ", "notre ", "nos ", "votre ", "vos ", "leur ", "leurs ",
    "de ", "het ", "onze ", "uw ", "hun ",
)

# "Counsel for the Claimant", "attorneys for Defendant", "conseil de la
# partie" — a role, whoever fills it.
_COUNSEL_FOR_RE = re.compile(
    r"^(?:counsel|attorneys?|solicitors?|lawyers?|advocates?|avocats?|conseils?|"
    r"advocaten?|raadsman|raadslieden)\s+(?:for|of|to|pour|de|van|voor)\s+"
    r"(?:the\s+|la\s+|le\s+|les\s+|de\s+|het\s+)?\w+$"
)

# Single-token demonyms and language adjectives that NER models label
# as LOC / NORP. Never identifiers.
_DEMONYMS = frozenset({
    "dutch", "french", "belgian", "german", "british", "english", "american",
    "swiss", "italian", "spanish", "luxembourgish", "irish", "european",
    "norwegian", "swedish", "danish", "finnish", "austrian", "polish",
    "portuguese", "greek", "japanese", "chinese", "indian", "canadian",
    "australian", "flemish", "walloon",
    "belge", "belges", "français", "française", "allemand", "allemande",
    "néerlandais", "néerlandaise", "suisse", "italien", "italienne",
    "espagnol", "espagnole", "européen", "européenne", "britannique",
    "américain", "américaine", "luxembourgeois", "luxembourgeoise",
    "belgisch", "belgische", "frans", "franse", "duits", "duitse",
    "nederlands", "nederlandse", "europees", "europese", "brits", "britse",
})


@lru_cache(maxsize=8)
def _load_model(name: str) -> spacy.language.Language:
    import spacy

    try:
        return spacy.load(name, disable=["lemmatizer", "tagger", "attribute_ruler"])
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{name}' is not installed. Run:\n"
            f"  python -m spacy download {name}"
        ) from e


def _resolve_model_for_language(lang: str, overrides: dict[str, str]) -> str | None:
    if lang in overrides:
        return overrides[lang]
    import spacy.util

    for candidate in _MODEL_FALLBACKS.get(lang, []):
        if spacy.util.is_package(candidate):
            return candidate
    return None


@lru_cache(maxsize=4)
def _stopwords_for(lang: str) -> frozenset[str]:
    if lang == "en":
        from spacy.lang.en.stop_words import STOP_WORDS
    elif lang == "fr":
        from spacy.lang.fr.stop_words import STOP_WORDS
    elif lang == "nl":
        from spacy.lang.nl.stop_words import STOP_WORDS
    else:
        return frozenset()
    return frozenset(STOP_WORDS)


def _normalize_span(
    text: str,
    start: int,
    end: int,
    lang: str,
) -> tuple[str, int, int] | None:
    """Trim a span to a sane shape; reject if it still looks like noise.

    Returns the (possibly shortened) `(text, start, end)` triple, or None to
    drop the span entirely. The trimming is conservative: it only removes
    leading/trailing whitespace-or-punctuation and content past a newline,
    never internal characters.
    """

    s = text
    # Reject `--- Sheet: X ---` / `--- Page N ---` markers that adapters
    # inject as structural annotation. spaCy sometimes labels them ORG;
    # they're never real content.
    if _MARKER_RE.match(s.strip()):
        return None
    # Strip common salutation prefixes that spaCy fuses into PERSON
    # spans ("Cher Pierre", "Dear John", "Geachte collega"). The result
    # is the bare name, with offsets adjusted accordingly.
    for sal in _SALUTATION_PREFIXES:
        if s.lower().startswith(sal):
            cut = len(sal)
            s = s[cut:]
            start += cut
            break
    # Reject common legal-document section labels and role headers that
    # spaCy mislabels as ORG when they appear capitalised at line start.
    normalised_label = re.sub(r"[^\w\s]", "", s).strip().lower()
    normalised_label = re.sub(r"\s+", " ", normalised_label)
    if normalised_label in _LEGAL_HEADERS or normalised_label in _DEMONYMS:
        return None
    for pre in _ROLE_PREFIXES:
        if normalised_label.startswith(pre):
            rest = normalised_label[len(pre):].strip()
            if rest in _LEGAL_HEADERS or rest in _DEMONYMS:
                return None
    if _COUNSEL_FOR_RE.match(normalised_label):
        return None
    # Drop everything past the first newline — spaCy frequently fuses
    # consecutive header lines like "Maître X\nDe:" into one entity.
    if "\n" in s:
        s = s.split("\n", 1)[0]
        end = start + len(s)

    # Strip trailing punctuation (": ," etc.) that spaCy includes by accident.
    while s and s[-1] in _PUNCT_STRIP:
        s = s[:-1]
        end -= 1
    while s and s[0] in _PUNCT_STRIP:
        s = s[1:]
        start += 1

    if not s.strip():
        return None

    tokens = s.split()
    if not tokens:
        return None

    # Spans of 6+ tokens are almost always parser overreach.
    if len(tokens) > 5:
        return None

    # Anything containing a recognizable date is not an entity for our purposes.
    if _YEAR_RE.search(s):
        return None
    lower_tokens = [t.strip(_PUNCT_STRIP).lower() for t in tokens]
    if any(t in _MONTHS for t in lower_tokens):
        return None

    # All-stopword spans ("Notre", "conteste les pratiques") are noise.
    stop = _stopwords_for(lang)
    non_empty = [t for t in lower_tokens if t]
    if non_empty and all(t in stop for t in non_empty):
        return None

    # A single fully lowercase token is almost never a real ORG/PERSON/LOC.
    if len(tokens) == 1 and s == s.lower():
        return None

    return (s, start, end)


class SpacyDetector:
    """spaCy-based NER with per-paragraph language routing.

    For each paragraph we detect its dominant language (using `langdetect`)
    and run *only* the matching spaCy model. This prevents the French model
    from hallucinating English content (and vice versa) — the dominant
    cause of false positives in v0.2.

    Per-language model selection prefers the larger `_lg` package when
    installed, falling back to `_md`. Override with the `models` argument.
    """

    def __init__(
        self,
        languages: tuple[str, ...] = ("en", "fr", "nl"),
        models: dict[str, str] | None = None,
    ):
        self.languages = languages
        self.model_overrides = models or {}

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        paragraphs = split_into_paragraphs(text) or [(0, text)]
        for offset, chunk in paragraphs:
            lang = detect_language(chunk, supported=self.languages)
            if lang is None:
                lang = self.languages[0]
            model_name = _resolve_model_for_language(lang, self.model_overrides)
            if model_name is None:
                # Detected language has no installed model — fall back to
                # the first supported language whose model IS installed,
                # rather than silently skipping the paragraph.
                for fallback in self.languages:
                    if fallback == lang:
                        continue
                    fb_model = _resolve_model_for_language(
                        fallback, self.model_overrides
                    )
                    if fb_model:
                        model_name = fb_model
                        lang = fallback
                        break
            if model_name is None:
                continue
            nlp = _load_model(model_name)
            doc = nlp(chunk)
            for ent in doc.ents:
                etype = _LABEL_MAP.get(ent.label_)
                if etype is None:
                    continue
                normalized = _normalize_span(
                    ent.text, ent.start_char, ent.end_char, lang
                )
                if normalized is None:
                    continue
                surface, rel_start, rel_end = normalized
                out.append(
                    Detection(
                        text=surface,
                        start=offset + rel_start,
                        end=offset + rel_end,
                        entity_type=etype,
                        source=DetectionSource.SPACY,
                        confidence=0.85,
                    )
                )
        return out
