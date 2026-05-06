import pytest

from jude.store import Store
from jude.types import EntityType, MessageRole, Mode


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


def test_export_matter_round_trips_via_json(store: Store):
    """A matter export captures everything needed to back the matter up
    and (eventually) re-import on another machine: matter row, entities
    + their surface forms, conversations + messages."""

    import json as _json

    m = store.create_matter("export-test", mode=Mode.STRICT)
    store.create_entity(
        m.id, "Acme Solutions SA", EntityType.ORG,
        surface_forms={"Acme Solutions SA", "Acme"},
        public_context="Belgian SA, fictional",
    )
    conv = store.create_conversation(m.id, title="export-conv")
    store.add_message(
        conv.id, MessageRole.USER,
        redacted_text="Org1 is the client.",
        display_text="Acme Solutions SA is the client.",
    )

    data = store.export_matter_json(m.id)
    # Round-trips through json without loss
    parsed = _json.loads(_json.dumps(data))

    assert parsed["matter"]["id"] == m.id
    assert parsed["matter"]["name"] == "export-test"
    assert any(
        ent["canonical"] == "Acme Solutions SA" for ent in parsed["entities"]
    )
    assert any("Acme" in ent["surface_forms"] for ent in parsed["entities"])
    assert len(parsed["conversations"]) == 1
    assert len(parsed["conversations"][0]["messages"]) == 1
    assert (
        parsed["conversations"][0]["messages"][0]["display_text"]
        == "Acme Solutions SA is the client."
    )


def test_export_matter_unknown_id_raises(store: Store):
    import pytest

    with pytest.raises(ValueError):
        store.export_matter_json("does-not-exist")


def test_matter_notes_persist_across_lookups(store: Store):
    """Lawyers want a free-text working-notes field per matter — not
    sent to the LLM, just for their own reference. Persists across
    process restarts via the matters table."""

    m = store.create_matter("with-notes")
    assert (store.get_matter(m.id).notes or "") == ""
    store.set_matter_notes(m.id, "Client called Tuesday — confirmed scope.")
    refetched = store.get_matter(m.id)
    assert refetched.notes == "Client called Tuesday — confirmed scope."


def test_matter_notes_can_be_cleared(store: Store):
    m = store.create_matter("clearable")
    store.set_matter_notes(m.id, "something")
    store.set_matter_notes(m.id, None)
    assert store.get_matter(m.id).notes is None


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


def test_find_alias_matches_first_name_substring(store: Store, matter_id: str):
    """When 'Marie-Claire Lefèvre' is already an entity, encountering just
    'Marie-Claire' should resolve to the same entity — eliminating the
    duplicate-pseudonym issue we hit on the test memo."""

    e = store.create_entity(
        matter_id, "Marie-Claire Lefèvre", EntityType.PERSON
    )
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Marie-Claire", EntityType.PERSON
    )
    assert found is not None
    assert found.id == e.id


def test_find_alias_matches_last_name_substring(store: Store, matter_id: str):
    e = store.create_entity(
        matter_id, "Marie-Claire Lefèvre", EntityType.PERSON
    )
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Lefèvre", EntityType.PERSON
    )
    assert found is not None
    assert found.id == e.id


def test_find_alias_refuses_when_ambiguous(store: Store, matter_id: str):
    """Two persons named 'Marie-Claire X' and 'Marie-Claire Y' — auto-aliasing
    a bare 'Marie-Claire' would be wrong; refuse and let the user decide."""

    store.create_entity(matter_id, "Marie-Claire Lefèvre", EntityType.PERSON)
    store.create_entity(matter_id, "Marie-Claire Dubois", EntityType.PERSON)
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Marie-Claire", EntityType.PERSON
    )
    assert found is None


def test_find_alias_for_org_prefix(store: Store, matter_id: str):
    e = store.create_entity(
        matter_id, "Pioneer Industries SA", EntityType.ORG
    )
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Pioneer Industries", EntityType.ORG
    )
    assert found is not None
    assert found.id == e.id


def test_find_alias_does_not_cross_entity_types(store: Store, matter_id: str):
    """A PERSON named 'Pioneer' and an ORG named 'Pioneer Industries' must
    not be linked even though one is a prefix of the other — the type
    boundary is harder evidence of separateness than the lexical hint."""

    store.create_entity(matter_id, "Pioneer Industries SA", EntityType.ORG)
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Pioneer", EntityType.PERSON
    )
    assert found is None


def test_find_alias_prefers_exact_match(store: Store, matter_id: str):
    """If an exact-form entity exists alongside an alias-matchable one, the
    exact match wins."""

    exact = store.create_entity(matter_id, "Pioneer", EntityType.ORG)
    store.create_entity(matter_id, "Pioneer Industries SA", EntityType.ORG)
    found = store.find_entity_by_surface_or_alias(
        matter_id, "Pioneer", EntityType.ORG
    )
    assert found is not None
    assert found.id == exact.id


def test_find_alias_returns_none_for_unhandled_types(store: Store, matter_id: str):
    """Aliasing only fires for PERSON and ORG — for EMAIL / PHONE / IBAN /
    URL / CASE_REF, the literal surface form is the identity (substring
    matching would create false positives)."""

    store.create_entity(matter_id, "alice@example.com", EntityType.EMAIL)
    found = store.find_entity_by_surface_or_alias(
        matter_id, "alice", EntityType.EMAIL
    )
    assert found is None


def test_add_surface_form_idempotent(store: Store, matter_id: str):
    e = store.create_entity(matter_id, "Acme", EntityType.ORG)
    store.add_surface_form(e.id, "Acme")
    store.add_surface_form(e.id, "Acme")
    forms = store.list_entities(matter_id)[0].surface_forms
    assert "Acme" in forms
    assert len(forms) == 1
