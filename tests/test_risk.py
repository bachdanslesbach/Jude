"""Tests for the re-identification risk assessor.

Written test-first — at the time of this commit `jude.risk` does not
exist; these tests must fail (red). The next commit makes them green.

Concept being specified
-----------------------

Pseudonymisation alone is not anonymisation: an entity can remain
identifiable from context. "The largest gaming acquisition in history at
$68.7bn" pseudonymises Microsoft–Activision but a reader recovers it
trivially. The risk assessor scores how vulnerable each entity in a
redacted turn is to this kind of re-identification.

The scoring is heuristic — *not* a formal k-anonymity proof. It surfaces
the obvious structural signals so the user (always the last filter) can
notice them before sending the prompt.

Signals scored (each contributes 1–3 points):

  * Public-knowledge `context` tag attached in smart mode
    (each tag narrows the population of candidate entities).
  * The entity's own canonical name appearing inside its public context
    (e.g. Amazon's bundled tag mentions "Amazon Marketplace") — this is
    a direct leak.
  * A specific currency figure within ~80 characters of any of the
    entity's pseudonym mentions (e.g. "Org1 paid €450,000,000").
  * A specific calendar date within ~80 characters.
  * A specific EU case reference (T-/C-/ECLI:) within ~80 characters.

Score → level mapping:

  * 0–1  → LOW
  * 2–3  → MEDIUM
  * 4+   → HIGH

Each reason is exposed as a short human-readable string so the UI can
explain its assessment.
"""

from __future__ import annotations

from datetime import datetime, timezone

from jude.risk import RiskLevel, assess_risks
from jude.types import Entity, EntityType, Mode


def _entity(
    entity_id: int,
    pseudonym: str,
    canonical: str,
    *,
    public_context: str | None = None,
    entity_type: EntityType = EntityType.ORG,
) -> Entity:
    return Entity(
        id=entity_id,
        matter_id="m",
        canonical=canonical,
        entity_type=entity_type,
        pseudonym=pseudonym,
        public_context=public_context,
        surface_forms={canonical},
        created_at=datetime.now(timezone.utc),
    )


# ---------- baseline behaviour ----------


def test_empty_inputs_return_empty_assessment():
    assert assess_risks("", [], Mode.STRICT) == []


def test_entity_with_no_context_and_no_specific_markers_is_low():
    text = "Org1 is a counterparty."
    e = _entity(1, "Org1", "Acme")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert risk.entity_id == 1
    assert risk.pseudonym == "Org1"
    assert risk.level == RiskLevel.LOW
    assert risk.score == 0
    assert risk.reasons == []


# ---------- public-knowledge context contributions ----------


def test_smart_mode_context_tag_alone_is_at_least_medium():
    """Even without specific figures, a public-knowledge tag narrows the
    pool of candidate entities and counts as a re-identification signal."""

    text = "Org1 entered the market in 2018."
    e = _entity(
        1, "Org1", "Amazon",
        public_context="DMA-designated gatekeeper for marketplace and ads",
    )
    [risk] = assess_risks(text, [e], Mode.SMART)
    assert risk.score >= 1
    assert any("public-knowledge tag" in r.lower() for r in risk.reasons)


def test_canonical_name_inside_own_context_is_high_risk():
    """If the bundled context for Amazon includes the word 'Amazon', the
    entity name leaks via the tag — this is the worst case and should
    score the maximum signal weight."""

    text = "Org1 holds a dominant position."
    e = _entity(
        1, "Org1", "Amazon",
        public_context=(
            "DMA-designated gatekeeper for the Amazon Marketplace and "
            "Amazon Ads core platform services"
        ),
    )
    [risk] = assess_risks(text, [e], Mode.SMART)
    assert any("canonical name appears inside" in r.lower() for r in risk.reasons)
    assert risk.level == RiskLevel.HIGH


# ---------- co-occurrence signals ----------


def test_specific_dollar_amount_near_pseudonym_adds_score():
    text = "Org1 acquired the target for $68,700,000,000 in cash."
    e = _entity(1, "Org1", "Microsoft")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert risk.score >= 1
    assert any("currency figure" in r.lower() for r in risk.reasons)


def test_currency_figure_far_from_pseudonym_does_not_count():
    """A figure in a separate paragraph, more than ~80 chars from any of
    the entity's pseudonym mentions, is not attributed to it."""

    text = (
        "Org1 is a counterparty.\n\n"
        + "Filler. " * 30
        + "\n\nIn another transaction, $68,700,000,000 changed hands."
    )
    e = _entity(1, "Org1", "Acme")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert not any("currency figure" in r.lower() for r in risk.reasons)


def test_specific_date_near_pseudonym_adds_score():
    text = "Org1 announced the deal on October 13, 2023."
    e = _entity(1, "Org1", "Activision")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert any("date" in r.lower() for r in risk.reasons)


def test_eu_case_ref_near_pseudonym_adds_score():
    text = "Org1 was a party in Case T-203/24 before the General Court."
    e = _entity(1, "Org1", "Meta")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert any("case reference" in r.lower() for r in risk.reasons)


# ---------- compound scenarios ----------


def test_compound_signals_escalate_to_high():
    text = (
        "Org1 announced on October 13, 2023 the closing of the "
        "$68,700,000,000 acquisition. See Case T-640/24."
    )
    e = _entity(
        1, "Org1", "Microsoft",
        public_context="DMA-designated gatekeeper for Windows and LinkedIn",
    )
    [risk] = assess_risks(text, [e], Mode.SMART)
    assert risk.level == RiskLevel.HIGH
    assert risk.score >= 4


def test_multiple_entities_scored_independently():
    text = (
        "Org1 has revenues of €450,000,000.\n\n"
        "Org2 is just mentioned in passing."
    )
    e1 = _entity(1, "Org1", "Big")
    e2 = _entity(2, "Org2", "Small")
    risks = assess_risks(text, [e1, e2], Mode.STRICT)
    by_id = {r.entity_id: r for r in risks}
    assert by_id[1].score > by_id[2].score


def test_reasons_are_human_readable_strings():
    text = "Org1 paid €450,000,000 on March 15, 2026."
    e = _entity(1, "Org1", "Anything")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    assert all(isinstance(r, str) and len(r) > 5 for r in risk.reasons)


def test_pseudonym_match_uses_word_boundaries():
    """Org1 must not match inside Org11 — otherwise an entity with a
    short numeric suffix would erroneously inherit signals from a
    longer-pseudonym entity nearby."""

    text = "Org11 is a separate party that paid $1,000,000,000."
    e = _entity(1, "Org1", "Confusable")
    [risk] = assess_risks(text, [e], Mode.STRICT)
    # No pseudonym mention of Org1 in this text → score is 0 regardless of
    # the financial figure floating around Org11.
    assert risk.score == 0


# ---------- result ordering ----------


def test_results_are_returned_in_descending_risk_order():
    """The UI surfaces risks for review; the highest-risk entity should
    appear first so the user notices it without scrolling."""

    text = (
        "Org1 paid €450,000,000 on March 15, 2026 in Case T-1/26.\n\n"
        "Org2 is mentioned briefly.\n\n"
        "Org3 also exists."
    )
    es = [
        _entity(1, "Org1", "Risky"),
        _entity(2, "Org2", "Mid"),
        _entity(3, "Org3", "Boring"),
    ]
    risks = assess_risks(text, es, Mode.STRICT)
    scores = [r.score for r in risks]
    assert scores == sorted(scores, reverse=True)
