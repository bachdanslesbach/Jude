from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from .types import EntityType, normalize_surface


class ContextProvider(ABC):
    """Pluggable lookup of public-knowledge tags for an entity.

    Providers MUST only return facts that are publicly known about the
    entity — never anything from the user's own corpus. That invariant is
    the only reason smart mode is defensible at all.
    """

    name: str

    @abstractmethod
    def lookup(self, canonical: str, entity_type: EntityType) -> str | None: ...


class BundledContextProvider(ContextProvider):
    """Look up entities in the JSON dataset shipped with Jude.

    The dataset only contains well-known public entities (DMA gatekeepers,
    EU institutions, NCAs, top courts, etc.). Matches are case-insensitive
    on the normalized surface form.
    """

    name = "bundled"

    def __init__(self, data_path: Path | str | None = None):
        if data_path is None:
            self._records = _load_bundled()
        else:
            self._records = _load_json(Path(data_path))

    def lookup(self, canonical: str, entity_type: EntityType) -> str | None:
        norm = normalize_surface(canonical)
        if not norm:
            return None
        for rec in self._records:
            if rec["type"] != entity_type.value:
                continue
            if norm in rec["_normalized_aliases"]:
                return rec["context"]
        return None


class ContextRouter(ContextProvider):
    """Try providers in order, return first non-empty match."""

    name = "router"

    def __init__(self, providers: list[ContextProvider]):
        self.providers = providers

    def lookup(self, canonical: str, entity_type: EntityType) -> str | None:
        for p in self.providers:
            ctx = p.lookup(canonical, entity_type)
            if ctx:
                return ctx
        return None


@lru_cache(maxsize=1)
def _load_bundled() -> list[dict]:
    raw = files("jude.data").joinpath("known_entities.json").read_text(encoding="utf-8")
    return _parse(json.loads(raw))


def _load_json(path: Path) -> list[dict]:
    return _parse(json.loads(path.read_text(encoding="utf-8")))


def _parse(data: dict) -> list[dict]:
    out: list[dict] = []
    for rec in data.get("entities", []):
        names = [rec["canonical"], *rec.get("aliases", [])]
        rec["_normalized_aliases"] = {normalize_surface(n) for n in names if n}
        out.append(rec)
    return out


def default_provider() -> ContextProvider:
    return BundledContextProvider()


def make_provider(
    *,
    use_wikipedia: bool = False,
    wikipedia_provider: ContextProvider | None = None,
) -> ContextProvider:
    """Compose the ContextProvider chain used by smart-mode redaction.

    Always-on tier (no network, no opt-in):
      1. BundledContextProvider — 147 curated known entities.
      2. EurLexContextProvider — offline ECLI / EU case-number decoder.

    Opt-in tier:
      3. WikipediaContextProvider — best-effort online fallback for
         entities outside the curated set. Sends entity names to
         Wikipedia's REST API, so requires explicit opt-in per matter.

    `wikipedia_provider` is injectable for tests. In production it
    defaults to `WikipediaContextProvider(cache_path=...)`.
    """

    from .context_eurlex import EurLexContextProvider

    chain: list[ContextProvider] = [
        BundledContextProvider(),
        EurLexContextProvider(),
    ]
    if use_wikipedia:
        if wikipedia_provider is None:
            from .context_wikipedia import WikipediaContextProvider
            from .paths import jude_home

            wikipedia_provider = WikipediaContextProvider(
                cache_path=jude_home() / "wikipedia_cache.json",
            )
        chain.append(wikipedia_provider)
    return ContextRouter(chain)


def fill_missing_context(
    store, matter_id: str, provider: ContextProvider | None = None
) -> int:
    """Auto-fill `public_context` for entities in `matter_id` that lack one.

    Returns the number of entities updated. Useful when transitioning a matter
    from strict to smart mode, or as a one-off enrichment pass.
    """

    provider = provider or default_provider()
    n = 0
    for ent in store.list_entities(matter_id):
        if ent.public_context:
            continue
        ctx = provider.lookup(ent.canonical, ent.entity_type)
        if ctx:
            store.set_public_context(ent.id, ctx)
            n += 1
    return n
