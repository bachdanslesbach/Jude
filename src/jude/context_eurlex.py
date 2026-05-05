"""Offline ECLI / EU case-number decoder for smart-mode context.

EUR-Lex's public website is bot-protected and rate-limited, so this
provider does not hit the network. Instead it decodes the structure
of an ECLI reference or an EU case number into a short human-readable
context string ("Court of Justice of the European Union, 2024, no.
512"). That gives the LLM enough information to ground its reasoning
in the right court without disclosing the actual case content.

Online enrichment (fetching the actual case title, parties, subject
matter from EUR-Lex) can be added later as an opt-in second-tier
provider once we have a stable, rate-limit-friendly endpoint.

ECLI structure (https://e-justice.europa.eu/175/EN/european_case_law_identifier_ecli):

    ECLI : <country> : <court> : <year> : <ordinal>

EU court codes:
  C  Court of Justice
  T  General Court (Tribunal)
  F  Civil Service Tribunal (defunct since 2016)

EU case-number structure:

  Case <prefix>-<number>/<year> [P]

  prefix: T (General Court), C (Court of Justice)
  year:   2 digits, < 50 = 21st century, >= 50 = 20th century
  P:      pourvoi / appeal (optional suffix)
"""

from __future__ import annotations

import re

from .context import ContextProvider
from .types import EntityType

_EU_COURTS = {
    "C": "Court of Justice of the European Union",
    "T": "General Court of the European Union",
    "F": "Civil Service Tribunal of the European Union (defunct since 2016)",
}

_ECLI_RE = re.compile(
    r"^\s*ECLI\s*:\s*([A-Z]{2})\s*:\s*([A-Z0-9]+)\s*:\s*(\d{4})\s*:\s*([A-Z0-9.]+)\s*$",
    re.IGNORECASE,
)
_CASE_RE = re.compile(
    r"^\s*(?:Case|Affaire|Aff\.?)\s+([CT])-(\d+)/(\d{2})(\s*P)?\s*$",
    re.IGNORECASE,
)


class EurLexContextProvider(ContextProvider):
    name = "eur-lex"

    def lookup(self, canonical: str, entity_type: EntityType) -> str | None:
        if entity_type != EntityType.CASE_REF:
            return None
        if not canonical or not canonical.strip():
            return None

        text = canonical.strip()

        m = _ECLI_RE.match(text)
        if m:
            country, court_code, year, ordinal = m.groups()
            return _format_ecli(country, court_code.upper(), year, ordinal)

        m = _CASE_RE.match(text)
        if m:
            prefix, number, year2, appeal = m.groups()
            return _format_eu_case(prefix.upper(), number, year2, bool(appeal))

        return None


def _format_ecli(country: str, court: str, year: str, ordinal: str) -> str:
    country_u = country.upper()
    if country_u == "EU":
        court_name = _EU_COURTS.get(court, f"EU body (code {court})")
        return f"{court_name} judgment, {year} (no. {ordinal})"
    # Member-state ECLI — surface the jurisdiction code so the LLM at
    # least knows it's a national-court case and not an EU-court case.
    return (
        f"National-court judgment, jurisdiction {country_u}, "
        f"court {court}, {year} (no. {ordinal})"
    )


def _format_eu_case(prefix: str, number: str, year2: str, appeal: bool) -> str:
    year_int = int(year2)
    full_year = 2000 + year_int if year_int < 50 else 1900 + year_int
    court_name = _EU_COURTS.get(prefix, f"EU court (code {prefix})")
    base = f"{court_name} case, {full_year} (no. {number})"
    if appeal:
        base += " — appeal"
    return base
