"""Baseline: the deterministic layers alone — zero parameters.

Regex identifiers (e-mail, phone, IBAN, case references), the
long-tail patterns (legal-form suffixes, honorific + name, vessels,
bare domains, addresses, acronyms defined in parentheses) and the
bundled known-entity list, with the public-knowledge whitelist
applied. No spaCy, no GLiNER. The bottom rung of the model-size
ladder: what a rules engine gets you before any neural model.
"""

from __future__ import annotations

from ..schema import PredSpan


class RulesOnlyRunner:
    name = "rules-only"

    def __init__(self):
        from jude.detect import KnownEntityDetector, PatternDetector, RegexDetector

        self.regex = RegexDetector()
        self.patterns = PatternDetector()
        self.known = KnownEntityDetector()

    def predict(self, text: str) -> list[PredSpan]:
        from jude.detect import resolve_overlaps
        from jude.public_knowledge import is_public_no_redact

        candidates = []
        candidates.extend(self.regex.detect(text))
        candidates.extend(self.patterns.detect(text))
        candidates.extend(self.known.detect(text))
        out = []
        for d in resolve_overlaps(candidates):
            if is_public_no_redact(d.text, d.entity_type):
                continue
            out.append(PredSpan(start=d.start, end=d.end, type=d.entity_type.value, text=d.text))
        return out

    def extra_meta(self) -> dict:
        return {"params_m": 0, "notes": ["Deterministic layers only: regex + patterns + known entities + whitelist."]}
