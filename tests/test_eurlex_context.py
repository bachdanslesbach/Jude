"""Tests for EurLexContextProvider.

Written test-first — at the time of this commit `jude.context_eurlex`
does not exist; these tests must fail (red). The next commit makes
them green.

Concept being specified
-----------------------

Smart-mode context for `CASE_REF` entities. EUR-Lex itself is bot-
protected and rate-limited, so v0 does not hit it over the network;
instead we **decode the ECLI / EU case-number structure** offline:

  * `ECLI:EU:C:2024:512` → Court of Justice of the European Union,
    2024, identifier 512.
  * `ECLI:EU:T:2024:200` → General Court of the European Union, 2024.
  * `Case T-203/24` → General Court, 2024, no. 203.
  * `Case C-403/19` → Court of Justice, 2019, no. 403.
  * `Case T-456/26 P` → General Court, 2026, no. 456, appeal (the
    P-suffix marks a pourvoi/appeal).
  * Member-state ECLI (e.g. ECLI:FR:CCASS:2024:...) returns at minimum
    the jurisdiction code so the LLM knows it's a national-court case
    and not an EU-court case.

This is enough context for the LLM to ground its reasoning in the
right court without learning the actual case content (which would
identify the parties to anyone with a search engine).
"""

from __future__ import annotations

from jude.context_eurlex import EurLexContextProvider
from jude.types import EntityType


def test_decodes_court_of_justice_ecli():
    p = EurLexContextProvider()
    ctx = p.lookup("ECLI:EU:C:2024:512", EntityType.CASE_REF)
    assert ctx is not None
    assert "Court of Justice" in ctx
    assert "2024" in ctx


def test_decodes_general_court_ecli():
    p = EurLexContextProvider()
    ctx = p.lookup("ECLI:EU:T:2024:200", EntityType.CASE_REF)
    assert ctx is not None
    assert "General Court" in ctx
    assert "2024" in ctx


def test_decodes_eu_case_number_general_court():
    p = EurLexContextProvider()
    ctx = p.lookup("Case T-203/24", EntityType.CASE_REF)
    assert ctx is not None
    assert "General Court" in ctx
    assert "2024" in ctx


def test_decodes_eu_case_number_court_of_justice():
    p = EurLexContextProvider()
    ctx = p.lookup("Case C-403/19", EntityType.CASE_REF)
    assert ctx is not None
    assert "Court of Justice" in ctx
    assert "2019" in ctx


def test_decodes_appeal_suffix():
    p = EurLexContextProvider()
    ctx = p.lookup("Case T-456/26 P", EntityType.CASE_REF)
    assert ctx is not None
    assert "appeal" in ctx.lower()


def test_decodes_member_state_ecli_carries_jurisdiction():
    p = EurLexContextProvider()
    ctx = p.lookup("ECLI:FR:CCASS:2024:111", EntityType.CASE_REF)
    assert ctx is not None
    # We don't require a friendly French court name — just that the
    # jurisdiction is exposed.
    assert "FR" in ctx or "French" in ctx or "France" in ctx


def test_returns_none_for_non_case_ref_type():
    """The provider must hard-refuse types other than CASE_REF — sending
    e.g. an organisation name to an EUR-Lex decoder yields nothing
    sensible."""

    p = EurLexContextProvider()
    assert p.lookup("Amazon", EntityType.ORG) is None
    assert p.lookup("Maître Dubois", EntityType.PERSON) is None


def test_returns_none_for_unparseable_string():
    p = EurLexContextProvider()
    assert p.lookup("just some random words", EntityType.CASE_REF) is None
    assert p.lookup("", EntityType.CASE_REF) is None


def test_handles_french_case_prefix():
    """'Affaire T-203/24' is the French rendering of 'Case T-203/24' and
    should decode the same way."""

    p = EurLexContextProvider()
    ctx = p.lookup("Affaire T-203/24", EntityType.CASE_REF)
    assert ctx is not None
    assert "General Court" in ctx
    assert "2024" in ctx


def test_handles_two_digit_year_below_50_as_21st_century():
    """'24' → 2024 (not 1924). EU case numbering uses 2-digit years; values
    < 50 are 21st century, ≥ 50 are 20th century. (The Court of Justice's
    case numbering started in 1953; numbers like /99, /87 etc. are 1900s.)
    """

    p = EurLexContextProvider()
    ctx_recent = p.lookup("Case T-1/24", EntityType.CASE_REF)
    assert ctx_recent is not None
    assert "2024" in ctx_recent

    ctx_old = p.lookup("Case T-1/87", EntityType.CASE_REF)
    assert ctx_old is not None
    assert "1987" in ctx_old
