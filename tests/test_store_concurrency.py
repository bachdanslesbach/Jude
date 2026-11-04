"""Two processes on one jude.db must never issue the same pseudonym."""

from __future__ import annotations

import threading

import pytest

from jude.store import Store
from jude.types import EntityType


def test_pseudonym_allocation_atomic_across_connections(tmp_path):
    db = tmp_path / "jude.db"
    a = Store(db)
    b = Store(db)
    try:
        m = a.create_matter("shared")
        created: dict[str, list[str]] = {"a": [], "b": []}
        errors: list[BaseException] = []

        def work(store: Store, key: str) -> None:
            try:
                for i in range(100):
                    e = store.create_entity(m.id, f"{key}-{i}", EntityType.ORG)
                    created[key].append(e.pseudonym)
            except BaseException as exc:  # pragma: no cover — reported below
                errors.append(exc)

        ta = threading.Thread(target=work, args=(a, "a"))
        tb = threading.Thread(target=work, args=(b, "b"))
        ta.start()
        tb.start()
        ta.join(60)
        tb.join(60)
        assert errors == []
        all_pseudonyms = created["a"] + created["b"]
        assert len(all_pseudonyms) == 200
        assert len(set(all_pseudonyms)) == 200
        assert {e.pseudonym for e in a.list_entities(m.id)} == set(all_pseudonyms)
    finally:
        a.close()
        b.close()


def test_create_entity_single_transaction(store, matter_id):
    with pytest.raises(AttributeError):
        # A non-string surface form fails after the counter was advanced:
        # the whole transaction rolls back, counter included.
        store.create_entity(matter_id, "Broken", EntityType.ORG, surface_forms={42})  # type: ignore[arg-type]
    row = store._conn.execute(
        "SELECT next_n FROM pseudonym_counters WHERE matter_id = ? AND entity_type = 'ORG'",
        (matter_id,),
    ).fetchone()
    assert row is None
    assert store.list_entities(matter_id) == []
    e = store.create_entity(matter_id, "Fine", EntityType.ORG)
    assert e.pseudonym == "Org1"
    assert store._conn.in_transaction is False


def test_provisional_entity_writes_no_create_audit_line(store, matter_id):
    store.create_entity(matter_id, "Hidden Name", EntityType.PERSON, provisional_review_id="r-1")
    rows = store._conn.execute(
        "SELECT action, detail FROM audit_log WHERE matter_id = ?", (matter_id,)
    ).fetchall()
    assert all(r["action"] != "entity.create" for r in rows)
    assert all("Hidden Name" not in (r["detail"] or "") for r in rows)
    e = store.create_entity(matter_id, "Shown Name", EntityType.PERSON)
    rows = store._conn.execute(
        "SELECT action, detail FROM audit_log WHERE matter_id = ? AND action = 'entity.create'",
        (matter_id,),
    ).fetchall()
    assert len(rows) == 1 and e.pseudonym in rows[0]["detail"]


def test_add_and_remove_surface_form(store, matter_id):
    e = store.create_entity(matter_id, "Acme Holdings", EntityType.ORG)
    assert store.add_surface_form(e.id, "Acme") is True
    assert store.add_surface_form(e.id, "Acme") is False
    assert store.add_surface_form(e.id, "   ") is False
    assert "Acme" in store.list_entities(matter_id)[0].surface_forms
    store.remove_surface_form(e.id, "Acme")
    assert "Acme" not in store.list_entities(matter_id)[0].surface_forms
    assert "Acme Holdings" in store.list_entities(matter_id)[0].surface_forms
