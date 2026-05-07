"""Baseline: regex rules alone. Tests how much of the redaction surface
can be covered by deterministic patterns (emails, IBANs, phones, case
refs, ECLI) without any NER.
"""

from __future__ import annotations

from ..schema import PredSpan


class RegexOnlyRunner:
    name = "regex-only"

    def __init__(self):
        from jude.detect.regex_rules import RegexDetector

        self.regex = RegexDetector()

    def predict(self, text: str) -> list[PredSpan]:
        out = self.regex.detect(text)
        return [
            PredSpan(
                start=d.start, end=d.end,
                type=d.entity_type.value, text=d.text,
            )
            for d in out
        ]
