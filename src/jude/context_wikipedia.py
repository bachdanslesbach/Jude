"""Wikipedia-backed `ContextProvider`.

Best-effort online enrichment for entities that aren't in the bundled
known-entities dataset. Used as a fallback by `ContextRouter` after
`BundledContextProvider`.

Privacy posture:
  * We only consult Wikipedia for ORG and LOC entity types. Querying for
    a person's name would leak the name to Wikipedia's server logs.
  * Lookups should be opt-in per matter — the UI surfaces a clear
    "this sends entity names to Wikipedia" toggle. The provider itself
    is purely mechanical.
  * Caching is in-memory per process; no on-disk persistence (which
    would be a privacy leak of its own kind).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol, runtime_checkable

from .context import ContextProvider
from .types import EntityType

_USER_AGENT = "Jude/0.4 (https://github.com/bachdanslesbach/Jude; legal-tech)"
_API_TEMPLATE = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
_MAX_CONTEXT_CHARS = 280
_DISAMBIGUATION_TYPES = {"disambiguation"}
_ALLOWED_TYPES: frozenset[EntityType] = frozenset(
    {EntityType.ORG, EntityType.LOC}
)
_DISAMBIGUATION_SUFFIXES_FOR_ORG = ("(company)", "(corporation)")


@runtime_checkable
class HttpClientProtocol(Protocol):
    """Minimal client interface — fetch a Wikipedia summary as parsed JSON.

    Returns the parsed JSON dict for the page summary, or None if the page
    does not exist (HTTP 404). Other transport errors should raise; the
    provider catches them and returns None.
    """

    def get_summary(self, title: str, lang: str = "en") -> dict | None: ...


class _UrllibClient:
    """Default HTTP client using urllib (stdlib, no extra dependencies)."""

    def get_summary(self, title: str, lang: str = "en") -> dict | None:
        url = _API_TEMPLATE.format(
            lang=lang, title=urllib.parse.quote(title, safe="")
        )
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        # Any other URLError, ConnectionError, JSONDecodeError, timeout, etc.
        # propagates and is caught by the provider.


class WikipediaContextProvider(ContextProvider):
    """Look up entities on Wikipedia for smart-mode context enrichment."""

    name = "wikipedia"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        lang: str = "en",
    ):
        self.http: HttpClientProtocol = http_client or _UrllibClient()
        self.lang = lang
        # Maps (canonical, entity_type) -> str | None (None caches negatives).
        self._cache: dict[tuple[str, EntityType], str | None] = {}

    def lookup(self, canonical: str, entity_type: EntityType) -> str | None:
        if entity_type not in _ALLOWED_TYPES:
            return None

        key = (canonical, entity_type)
        if key in self._cache:
            return self._cache[key]

        result = self._fetch(canonical, entity_type)
        self._cache[key] = result
        return result

    def _fetch(self, canonical: str, entity_type: EntityType) -> str | None:
        # For ORGs, prefer the disambiguated "(company)" page when it exists,
        # which avoids returning a fruit's article for "Apple". We try the
        # disambiguated title first; if it 404s, fall back to the bare name.
        candidates = [canonical]
        if entity_type == EntityType.ORG:
            candidates = [
                f"{canonical} {suffix}"
                for suffix in _DISAMBIGUATION_SUFFIXES_FOR_ORG
            ] + [canonical]

        for title in candidates:
            try:
                data = self.http.get_summary(title, self.lang)
            except Exception:
                # Any transport-level failure is non-fatal.
                return None
            if not data:
                continue
            if data.get("type") in _DISAMBIGUATION_TYPES:
                continue
            extract = data.get("extract")
            if not extract:
                continue
            return _shape_context(extract)
        return None


def _shape_context(extract: str) -> str:
    """Normalize a Wikipedia extract into a short, paren-friendly context.

    Strategy: take the first sentence (or first 280 chars, whichever ends
    sooner). Strip whitespace and a single trailing dot.
    """

    text = extract.strip()
    if not text:
        return text
    # Find the end of the first sentence-ish block.
    match = re.search(r"\.\s+(?=[A-ZÀ-Ÿ])", text)
    if match:
        text = text[: match.start() + 1]
    if len(text) > _MAX_CONTEXT_CHARS:
        text = text[:_MAX_CONTEXT_CHARS].rstrip()
        if text.endswith(","):
            text = text[:-1]
    text = text.rstrip(" \t\n.")
    return text + "." if text and not text.endswith(".") else text
