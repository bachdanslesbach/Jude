from jude.context import (
    BundledContextProvider,
    ContextRouter,
    fill_missing_context,
)
from jude.store import Store
from jude.types import EntityType


def test_bundled_provider_finds_dma_gatekeepers():
    p = BundledContextProvider()
    ctx = p.lookup("Amazon", EntityType.ORG)
    assert ctx is not None
    assert "gatekeeper" in ctx.lower()


def test_bundled_provider_matches_aliases_case_insensitively():
    p = BundledContextProvider()
    assert p.lookup("amazon.com inc.", EntityType.ORG) is not None
    assert p.lookup("AMZN", EntityType.ORG) is not None
    assert p.lookup("Google", EntityType.ORG) is not None
    assert p.lookup("GOOGL", EntityType.ORG) is not None


def test_bundled_provider_rejects_wrong_type():
    p = BundledContextProvider()
    assert p.lookup("Amazon", EntityType.PERSON) is None


def test_bundled_provider_returns_none_for_unknown():
    p = BundledContextProvider()
    assert p.lookup("Acme Specific Client SARL", EntityType.ORG) is None


def test_bundled_provider_finds_eu_institutions():
    p = BundledContextProvider()
    assert p.lookup("European Commission", EntityType.ORG) is not None
    assert p.lookup("CJEU", EntityType.ORG) is not None
    assert p.lookup("Bundeskartellamt", EntityType.ORG) is not None


def test_router_returns_first_match():
    class Always(BundledContextProvider):
        def __init__(self, val):
            self._val = val

        def lookup(self, c, t):
            return self._val

    r = ContextRouter([Always(None), Always("hit"), Always("never")])
    assert r.lookup("anything", EntityType.ORG) == "hit"


def test_fill_missing_context_only_fills_empty(store: Store, matter_id: str):
    a = store.create_entity(matter_id, "Amazon", EntityType.ORG)
    b = store.create_entity(
        matter_id, "Microsoft", EntityType.ORG, public_context="user override"
    )
    private = store.create_entity(matter_id, "Acme Private SARL", EntityType.ORG)
    n = fill_missing_context(store, matter_id)
    assert n == 1
    refreshed = {e.id: e for e in store.list_entities(matter_id)}
    assert refreshed[a.id].public_context is not None
    assert refreshed[b.id].public_context == "user override"
    assert refreshed[private.id].public_context is None
