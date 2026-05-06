from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from ..types import Detection, DetectionSource, EntityType
from .language import detect_language, split_into_paragraphs

if TYPE_CHECKING:
    import spacy.language


_MODEL_FALLBACKS: dict[str, list[str]] = {
    "en": ["en_core_web_lg", "en_core_web_md"],
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
