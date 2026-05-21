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
        # IBAN: 2-letter country + 2 check digits + BBAN of 11–30
        # alphanumerics, optionally space-grouped. The previous regex
        # required 4-char groups, which clipped French IBANs (27 chars,
        # trailing 3-char group). The new pattern matches the spec
        # directly: the BBAN portion is "any number of optional
        # spaces interleaved with [A-Z0-9]" up to the per-country max.
        "iban",
        re.compile(
            r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b"
        ),
        EntityType.IBAN,
    ),
    _Rule(
        # EU VAT numbers: country prefix + 8-12 digits (varies by member
        # state). Requires the prefix so we don't grab every order number.
        "eu_vat",
        re.compile(
            r"\b(?:BE0?\d{9,10}|FR[A-Z0-9]{2}\d{9}|DE\d{9}|IT\d{11}|"
            r"ES[A-Z0-9]\d{7}[A-Z0-9]|NL\d{9}B\d{2}|LU\d{8}|"
            r"AT[Uu]\d{8}|PT\d{9}|IE\d[A-Z0-9]\d{5}[A-Z]|"
            r"PL\d{10}|SE\d{12}|DK\d{8}|FI\d{8})\b"
        ),
        EntityType.IBAN,  # VAT shares the IBAN bucket for v0
    ),
    _Rule(
        # French SIRET (14 digits) — must come before SIREN to win the
        # priority race when a SIRET fully contains a SIREN as prefix.
        "french_siret",
        re.compile(
            r"(?<!\d)(?:SIRET\s*[:\s]?\s*)?\d{14}(?!\d)",
            re.IGNORECASE,
        ),
        EntityType.IBAN,
    ),
    _Rule(
        # French SIREN (9 digits, often after the word SIREN).
        "french_siren",
        re.compile(
            r"(?<!\d)(?:SIREN\s*[:\s]?\s*)?\d{9}(?!\d)",
            re.IGNORECASE,
        ),
        EntityType.IBAN,
    ),
    _Rule(
        # Belgian National Register number (RRN). Format: YY.MM.DD-NNN.CC
        # where CC is a control number. Less commonly: YYMMDD-NNNCC.
        "belgian_rrn",
        re.compile(
            r"\b\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}\b"
            r"|\b\d{6}-\d{3}\.?\d{2}\b"
        ),
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
    _Rule(
        # US federal court docket: 1:26-cv-00489-RGA, 2:24-cr-00012-JES.
        # district_no:year-type-seq-judge_initials.
        "us_district_docket",
        re.compile(
            r"\b\d+:\d{2}-(?:cv|cr|md|mj|mc|mh|bk|ap)-\d{4,6}"
            r"(?:-[A-Z]{2,4})?\b",
            re.IGNORECASE,
        ),
        EntityType.CASE_REF,
    ),
    _Rule(
        # USPTO PTAB inter-partes review: IPR2025-00712.
        "uspto_ptab",
        re.compile(r"\b(?:IPR|PGR|CBM)\d{4}-\d{5}\b"),
        EntityType.CASE_REF,
    ),
    _Rule(
        # Bundeskartellamt case numbers: B6-127/26, VK-12/24, etc.
        "bundeskartellamt_case",
        re.compile(r"\b(?:B\d+|VK|KVR|KZR)-\d+/\d{2}\b"),
        EntityType.CASE_REF,
    ),
    _Rule(
        # Internal matter / docket ID containing a 4-digit year somewhere.
        # Catches M-2026-PIO-001, FE-COMP-2026-088, RVK-2026-BPC-014,
        # HRT-2026-GINKGO-01, WP-CREST-TLW-2026, etc. The leading lookahead
        # rejects "LONG-TERM"-style phrases (no digits) and "ORTIZ-VALDEZ"
        # (looks docket-shaped but is two surnames).
        "internal_matter_id_with_year",
        re.compile(
            r"\b(?=[A-Z0-9-]*(?:19|20)\d{2})"
            r"[A-Z]{1,8}(?:-[A-Z0-9]+){1,5}\b"
        ),
        EntityType.CASE_REF,
    ),
    _Rule(
        # Numeric-trailer matter IDs: two+ alphabetic segments then a
        # 3-5-digit number (CT-WB-026, FE-COMP-088). Won't match
        # "PIO-001" alone (single alpha segment) and won't match
        # "LONG-TERM" (no digits).
        "internal_matter_id_numeric_trailer",
        re.compile(r"\b[A-Z]{2,8}-[A-Z]{2,8}-\d{3,5}\b"),
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
