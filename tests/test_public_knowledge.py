"""Tests for the public-knowledge whitelist.

Some institutions in the bundled known-entities dataset should NEVER be
redacted — their mention in a legal document does not identify a client.
The European Commission, CNIL, the Bundeskartellamt, the CJEU etc. are
public bodies; redacting them ranges from useless to actively harmful
(it forces the LLM to reason without grounding).

Public *companies* (Amazon, Microsoft, Meta) stay redactable — they
could be the user's client or counterparty.

Specified contract:
  * The bundled JSON gains an optional `"redact"` field (default true).
  * Institutions, regulators, NCAs, DPAs, courts, financial bodies have
    `"redact": false`.
  * Companies (the 7 DMA gatekeepers) keep the default redactable.
  * The redact pipeline drops detections whose normalized canonical
    matches any `redact: false` bundled record of the same entity_type.
"""

from __future__ import annotations

from jude.context import BundledContextProvider
from jude.public_knowledge import is_public_no_redact
from jude.redact import redact
from jude.store import Store
from jude.types import Detection, DetectionSource, EntityType, Mode


def _det(text: str, start: int, etype: EntityType = EntityType.ORG) -> Detection:
    return Detection(
        text=text,
        start=start,
        end=start + len(text),
        entity_type=etype,
        source=DetectionSource.SPACY,
    )


# ---------- the predicate ----------


def test_european_commission_is_no_redact():
    assert is_public_no_redact("European Commission", EntityType.ORG)
    assert is_public_no_redact("Commission", EntityType.ORG)  # via alias
    assert is_public_no_redact("CNIL", EntityType.ORG)


def test_companies_in_bundled_are_still_redactable():
    """Amazon, Microsoft, Meta etc. STAY redactable — they could be the
    user's client or a counterparty whose identity is confidential in
    this matter, even though their corporate identity is public."""

    assert not is_public_no_redact("Amazon", EntityType.ORG)
    assert not is_public_no_redact("Microsoft", EntityType.ORG)
    assert not is_public_no_redact("Meta", EntityType.ORG)


def test_eu_regulations_are_no_redact():
    """The Digital Markets Act, GDPR, EUMR and similar are public
    regulations — must never be pseudonymised."""

    assert is_public_no_redact("Digital Markets Act", EntityType.ORG)
    assert is_public_no_redact("DMA", EntityType.ORG)
    assert is_public_no_redact("GDPR", EntityType.ORG)
    assert is_public_no_redact("Regulation (EC) 139/2004", EntityType.ORG)
    assert is_public_no_redact("TFEU", EntityType.ORG)


def test_unknown_entities_default_to_redactable():
    assert not is_public_no_redact("Acme Solutions SA", EntityType.ORG)
    assert not is_public_no_redact("Marie-Claire Lefèvre", EntityType.PERSON)


def test_aliases_match_case_insensitively():
    assert is_public_no_redact("CJEU", EntityType.ORG)
    assert is_public_no_redact("cjeu", EntityType.ORG)
    assert is_public_no_redact("Court of Justice", EntityType.ORG)


# ---------- end-to-end ----------


def test_redact_skips_public_institutions(store: Store, matter_id: str):
    """The European Commission is mentioned in the input; it must NOT be
    pseudonymized in the output. The user's client name 'Acme SA' SHOULD
    still be."""

    text = (
        "Acme Solutions SA filed a complaint with the European Commission. "
        "The Commission opened an investigation."
    )
    dets = [
        _det("Acme Solutions SA", 0),
        _det("European Commission", 51, EntityType.ORG),
        _det("Commission", 88, EntityType.ORG),
    ]
    result = redact(text, dets, store, matter_id, Mode.STRICT)
    assert "Acme Solutions SA" not in result.redacted_text
    assert "European Commission" in result.redacted_text
    assert "Commission" in result.redacted_text  # the second mention also kept
    # And the dictionary should NOT have created an Org_n entity for the
    # Commission — only Acme.
    canonicals = {e.canonical for e in result.entities_used}
    assert "Acme Solutions SA" in canonicals
    assert "European Commission" not in canonicals


def test_redact_still_handles_public_companies_normally(
    store: Store, matter_id: str
):
    """Amazon is in the bundled set but still redactable. The same
    pipeline applies."""

    text = "Amazon acquired Acme Solutions SA."
    dets = [_det("Amazon", 0), _det("Acme Solutions SA", 16)]
    result = redact(text, dets, store, matter_id, Mode.STRICT)
    assert "Amazon" not in result.redacted_text
    assert "Acme Solutions SA" not in result.redacted_text
