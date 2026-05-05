import pytest

from jude.store import Store
from jude.types import EntityType, Mode


def test_create_matter_persists(store: Store):
    m = store.create_matter("Acme v Acme", mode=Mode.STRICT)
    fetched = store.get_matter(m.id)
    assert fetched is not None
    assert fetched.name == "Acme v Acme"
    assert fetched.mode == Mode.STRICT
    assert fetched.zero_retention_attested is False


def test_create_entity_assigns_unique_pseudonym(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(matter_id, "Microsoft", EntityType.ORG)
    assert a.pseudonym == "Org1"
    assert b.pseudonym == "Org2"


def test_pseudonym_prefix_per_type(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    p = store.create_entity(matter_id, "John Doe", EntityType.PERSON)
    e = store.create_entity(matter_id, "x@y.com", EntityType.EMAIL)
    assert a.pseudonym == "Org1"
    assert p.pseudonym == "Person1"
    assert e.pseudonym == "Email1"


def test_find_by_surface_uses_normalized_match(store: Store, matter_id: str):
    store.create_entity(
        matter_id,
        "Amazon.com Inc.",
        EntityType.ORG,
        surface_forms={"Amazon.com Inc.", "Amazon"},
    )
    by_full = store.find_entity_by_surface(matter_id, "Amazon.com Inc.")
    by_short = store.find_entity_by_surface(matter_id, "amazon")
    by_with_corp = store.find_entity_by_surface(matter_id, "Amazon Corporation")
    assert by_full is not None
    assert by_short is not None and by_short.id == by_full.id
    assert by_with_corp is not None and by_with_corp.id == by_full.id


def test_set_llm_endpoint_persists(store: Store):
    m = store.create_matter("m", llm_endpoint="anthropic")
    store.set_llm_endpoint(m.id, "ollama", model="llama3.3:70b")
    refetched = store.get_matter(m.id)
    assert refetched.llm_endpoint == "ollama"
    assert refetched.llm_model == "llama3.3:70b"


def test_set_llm_endpoint_clears_model_when_omitted(store: Store):
    m = store.create_matter("m", llm_endpoint="ollama")
    store.set_llm_endpoint(m.id, "ollama", model="llama3.3:70b")
    store.set_llm_endpoint(m.id, "anthropic", model=None)
    assert store.get_matter(m.id).llm_model is None


def test_smart_mode_requires_zero_retention(store: Store):
    m = store.create_matter("m", mode=Mode.STRICT)
    with pytest.raises(ValueError):
        store.set_mode(m.id, Mode.SMART, zero_retention_attested=False)
    store.set_mode(m.id, Mode.SMART, zero_retention_attested=True)
    refetched = store.get_matter(m.id)
    assert refetched.mode == Mode.SMART
    assert refetched.zero_retention_attested is True


def test_add_surface_form_idempotent(store: Store, matter_id: str):
    e = store.create_entity(matter_id, "Acme", EntityType.ORG)
    store.add_surface_form(e.id, "Acme")
    store.add_surface_form(e.id, "Acme")
    forms = store.list_entities(matter_id)[0].surface_forms
    assert "Acme" in forms
    assert len(forms) == 1
