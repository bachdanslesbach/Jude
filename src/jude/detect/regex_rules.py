from __future__ import annotations

import re
from dataclasses import dataclass

from ..types import Detection, DetectionSource, EntityType


@dataclass(frozen=True)
class _Rule:
    name: str
    pattern: re.Pattern[str]
    entity_type: EntityType


_RULES: tuple[_Rule, ...] = (
    _Rule(
        "email",
        re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
        EntityType.EMAIL,
    ),
    _Rule(
        "iban",
        re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}\b"),
        EntityType.IBAN,
    ),
    _Rule(
        "phone_intl",
        re.compile(
            r"(?<!\w)\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,5}(?!\w)"
        ),
        EntityType.PHONE,
    ),
    _Rule(
        "url",
        re.compile(
            r"\bhttps?://[^\s<>\"')]+",
            re.IGNORECASE,
        ),
        EntityType.URL,
    ),
    _Rule(
        # EU case references: C-123/22, T-456/21 P, joined cases.
        "eu_case_ref",
        re.compile(
            r"\b(?:Case|Affaire|Aff\.?)\s*[CT]-\d+/\d{2}(?:\s*P)?\b",
            re.IGNORECASE,
        ),
        EntityType.CASE_REF,
    ),
    _Rule(
        "ecli",
        re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[A-Z0-9.]+\b"),
        EntityType.CASE_REF,
    ),
)


class RegexDetector:
    """Deterministic detection for emails, phones, IBANs, URLs, case refs."""

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for rule in _RULES:
            for m in rule.pattern.finditer(text):
                out.append(
                    Detection(
                        text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        entity_type=rule.entity_type,
                        source=DetectionSource.REGEX,
                        confidence=1.0,
                    )
                )
        return out
