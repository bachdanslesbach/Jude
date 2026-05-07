"""Baseline: spaCy NER alone, with our shape filter, no public-knowledge
whitelist, no regex, no dictionary. Tests the contribution of the spaCy
layer in isolation.
"""

from __future__ import annotations

from ..schema import PredSpan


class SpacyOnlyRunner:
    name = "spacy-only"

    def __init__(self, languages=("en", "fr")):
        from jude.detect.spacy_detector import SpacyDetector

        self.spacy = SpacyDetector(languages=languages)

    def predict(self, text: str) -> list[PredSpan]:
        out = self.spacy.detect(text)
        return [
            PredSpan(
                start=d.start, end=d.end,
                type=d.entity_type.value, text=d.text,
            )
            for d in out
        ]
