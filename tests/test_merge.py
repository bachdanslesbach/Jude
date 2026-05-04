import pytest

from jude.rehydrate import rehydrate
from jude.store import Store
from jude.types import EntityType


def test_merge_consolidates_surface_forms(store: Store, matter_id: str):
    a = store.create_entity(
        matter_id, "Amazon", EntityType.ORG, surface_forms={"Amazon"}
    )
    b = store.create_entity(
        matter_id, "Amazon.com Inc.", EntityType.ORG, surface_forms={"Amazon.com Inc."}
    )
    merged = store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)
    assert merged.id == a.id
    assert merged.pseudonym == a.pseudonym
    assert "Amazon" in merged.surface_forms
    assert "Amazon.com Inc." in merged.surface_forms
    assert store.find_entity_by_pseudonym(matter_id, b.pseudonym) is None


def test_merge_inherits_secondary_context_when_primary_empty(
    store: Store, matter_id: str
):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(
        matter_id,
        "Amazon.com Inc.",
        EntityType.ORG,
        public_context="DMA gatekeeper",
    )
    merged = store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)
    assert merged.public_context == "DMA gatekeeper"


def test_merge_keeps_primary_context_over_secondary(store: Store, matter_id: str):
    a = store.create_entity(
        matter_id, "Amazon", EntityType.ORG, public_context="primary tag"
    )
    b = store.create_entity(
        matter_id, "Amazon.com Inc.", EntityType.ORG, public_context="secondary tag"
    )
    merged = store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)
    assert merged.public_context == "primary tag"


def test_merge_rejects_different_types(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(matter_id, "Jeff Bezos", EntityType.PERSON)
    with pytest.raises(ValueError):
        store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)


def test_merge_rejects_same_entity(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    with pytest.raises(ValueError):
        store.merge_entities(matter_id, primary_id=a.id, secondary_id=a.id)


def test_merge_does_not_recycle_pseudonym(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(matter_id, "Microsoft", EntityType.ORG)
    store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)
    c = store.create_entity(matter_id, "Apple", EntityType.ORG)
    assert c.pseudonym not in {a.pseudonym, b.pseudonym}
    assert c.pseudonym == "Org_003"


def test_rehydrate_after_merge_uses_primary_canonical(
    store: Store, matter_id: str
):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(matter_id, "Amazon.com Inc.", EntityType.ORG)
    pa, pb = a.pseudonym, b.pseudonym
    store.merge_entities(matter_id, primary_id=a.id, secondary_id=b.id)
    text = f"{pa} acquired something. {pb} also did."
    out = rehydrate(text, store, matter_id)
    assert "Amazon" in out
    assert pb in out
