import pytest

from jude.redact import redact
from jude.rehydrate import rehydrate
from jude.store import Store
from jude.types import Detection, DetectionSource, EntityType, Mode


def _det(text: str, start: int, etype: EntityType = EntityType.ORG) -> Detection:
    return Detection(
        text=text,
        start=start,
        end=start + len(text),
        entity_type=etype,
        source=DetectionSource.USER,
    )


def test_redact_strict_replaces_with_pseudonym(store: Store, matter_id: str):
    text = "Amazon and Microsoft are competitors. Amazon is bigger."
    detections = [
        _det("Amazon", 0),
        _det("Microsoft", 11),
        _det("Amazon", 38),
    ]
    result = redact(text, detections, store, matter_id, Mode.STRICT)
    assert "Amazon" not in result.redacted_text
    assert "Microsoft" not in result.redacted_text
    assert "Org_001" in result.redacted_text
    assert "Org_002" in result.redacted_text
    assert result.redacted_text.count("Org_001") == 2


def test_redact_smart_appends_context_only_on_first_mention(
    store: Store, smart_matter_id: str
):
    e = store.create_entity(
        smart_matter_id,
        "Amazon",
        EntityType.ORG,
        public_context="DMA gatekeeper, marketplace + cloud",
    )
    text = "Amazon competes. Amazon's revenue grew."
    detections = [_det("Amazon", 0), _det("Amazon", 17)]
    result = redact(text, detections, store, smart_matter_id, Mode.SMART)
    first_idx = result.redacted_text.find(e.pseudonym)
    second_idx = result.redacted_text.find(e.pseudonym, first_idx + 1)
    assert "(DMA gatekeeper" in result.redacted_text[first_idx : first_idx + 80]
    assert "(DMA gatekeeper" not in result.redacted_text[second_idx:]


def test_redact_smart_refuses_without_zero_retention(store: Store):
    m = store.create_matter("strict matter", mode=Mode.STRICT)
    with pytest.raises(ValueError):
        redact("Amazon", [_det("Amazon", 0)], store, m.id, Mode.SMART)


def test_rehydrate_reverses_pseudonyms(store: Store, matter_id: str):
    text = "Amazon and Microsoft."
    redacted = redact(
        text, [_det("Amazon", 0), _det("Microsoft", 11)], store, matter_id, Mode.STRICT
    )
    llm_response = (
        f"In my view, {redacted.entities_used[0].pseudonym} has the stronger position "
        f"against {redacted.entities_used[1].pseudonym}."
    )
    rehydrated = rehydrate(llm_response, store, matter_id)
    assert "Amazon" in rehydrated
    assert "Microsoft" in rehydrated
    assert "Org_001" not in rehydrated


def test_rehydrate_does_not_match_partial_pseudonyms(store: Store, matter_id: str):
    store.create_entity(matter_id, "Acme", EntityType.ORG)
    llm_response = "See Org_001 as well as Org_0011_extra (this is not a pseudonym)."
    rehydrated = rehydrate(llm_response, store, matter_id)
    assert "Acme" in rehydrated
    assert "Org_0011_extra" in rehydrated


def test_redact_consistent_pseudonym_across_runs(store: Store, matter_id: str):
    redact("Amazon.", [_det("Amazon", 0)], store, matter_id, Mode.STRICT)
    second = redact(
        "Amazon and Acme.",
        [_det("Amazon", 0), _det("Acme", 11)],
        store,
        matter_id,
        Mode.STRICT,
    )
    pseudonyms = {e.canonical: e.pseudonym for e in second.entities_used}
    assert pseudonyms["Amazon"] == "Org_001"
    assert pseudonyms["Acme"] == "Org_002"
