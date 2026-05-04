from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from ..types import Detection, DetectionSource, EntityType

if TYPE_CHECKING:
    import spacy.language


_DEFAULT_MODELS: dict[str, str] = {
    "en": "en_core_web_md",
    "fr": "fr_core_news_md",
}


_LABEL_MAP: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "PER": EntityType.PERSON,
    "ORG": EntityType.ORG,
    "GPE": EntityType.LOC,
    "LOC": EntityType.LOC,
    "FAC": EntityType.LOC,
}


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


class SpacyDetector:
    """spaCy-based NER for PERSON / ORG / LOC across configured languages.

    Runs each configured model and merges detections — language detection
    is not yet performed. For mixed-language documents, multiple models will
    each contribute their findings.
    """

    def __init__(
        self,
        languages: tuple[str, ...] = ("en", "fr"),
        models: dict[str, str] | None = None,
    ):
        self.models = {**_DEFAULT_MODELS, **(models or {})}
        self.languages = languages

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for lang in self.languages:
            model_name = self.models.get(lang)
            if not model_name:
                continue
            nlp = _load_model(model_name)
            doc = nlp(text)
            for ent in doc.ents:
                etype = _LABEL_MAP.get(ent.label_)
                if etype is None:
                    continue
                out.append(
                    Detection(
                        text=ent.text,
                        start=ent.start_char,
                        end=ent.end_char,
                        entity_type=etype,
                        source=DetectionSource.SPACY,
                        confidence=0.85,
                    )
                )
        return out
