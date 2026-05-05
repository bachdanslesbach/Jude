"""Tests for the Wikipedia-backed ContextProvider.

Written test-first — at the time of this commit the implementation does
not exist and these tests must fail (red). The next commit implements the
provider until they pass (green).

Design intent surfaced by these tests:

  * The provider implements the same `ContextProvider.lookup(canonical,
    entity_type) -> str | None` interface as `BundledContextProvider`,
    so it composes cleanly through `ContextRouter`.
  * HTTP is injected via a small client protocol. Production uses urllib
    (stdlib, no new dependencies); tests use a Fake.
  * Lookups are cached in-memory; the same query never hits the network
    twice in one process lifetime.
  * Network errors and missing pages return None, never raise — context
    enrichment is best-effort and should never break a redaction run.
  * Returned context strings are short (<= 280 chars) and stripped, so
    they're a good fit for the parenthetical in smart-mode redactions.
  * The provider DOES NOT auto-disambiguate disambiguation pages; it
    returns the first hit, leaving the user to verify in the UI.
"""

from __future__ import annotations

import pytest

from jude.context_wikipedia import (
    HttpClientProtocol,
    WikipediaContextProvider,
)
from jude.types import EntityType


class FakeWikipediaClient:
    """In-memory test double for the urllib-backed default client."""

    def __init__(self, responses: dict[tuple[str, str], dict | None]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def get_summary(self, title: str, lang: str = "en") -> dict | None:
        self.calls.append((title, lang))
        return self.responses.get((title, lang))


def test_returns_short_context_for_known_entity():
    fake = FakeWikipediaClient(
        {
            ("Amazon (company)", "en"): {
                "title": "Amazon (company)",
                "extract": (
                    "Amazon.com, Inc. is an American multinational technology "
                    "company focusing on e-commerce, cloud computing, online "
                    "advertising, digital streaming, and artificial intelligence."
                ),
                "type": "standard",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    ctx = p.lookup("Amazon", EntityType.ORG)
    assert ctx is not None
    assert "American" in ctx
    assert len(ctx) <= 280


def test_returns_none_for_unknown_entity():
    fake = FakeWikipediaClient(responses={})
    p = WikipediaContextProvider(http_client=fake)
    assert p.lookup("Acme Privately Held Client SARL", EntityType.ORG) is None


def test_returns_none_on_network_error():
    class Failing:
        def get_summary(self, title: str, lang: str = "en") -> dict | None:
            raise ConnectionError("simulated network failure")

    p = WikipediaContextProvider(http_client=Failing())
    assert p.lookup("Amazon", EntityType.ORG) is None


def test_returns_none_for_disambiguation_pages():
    """Wikipedia disambiguation pages have type='disambiguation' and aren't
    useful as context — they return a list of meanings, not a definition."""

    fake = FakeWikipediaClient(
        {
            ("Apple", "en"): {
                "title": "Apple",
                "type": "disambiguation",
                "extract": "Apple may refer to: Apple Inc., Apple (fruit), …",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    assert p.lookup("Apple", EntityType.ORG) is None


def test_caches_repeat_lookups():
    fake = FakeWikipediaClient(
        {
            ("Amazon (company)", "en"): {
                "title": "Amazon (company)",
                "extract": "Amazon is a US tech company.",
                "type": "standard",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    p.lookup("Amazon", EntityType.ORG)
    p.lookup("Amazon", EntityType.ORG)
    p.lookup("Amazon", EntityType.ORG)
    assert len(fake.calls) == 1


def test_caches_negative_results_too():
    """A lookup that returned None must not retry the network on a second call.

    The first call may issue several requests internally (the provider tries
    a few disambiguated titles for ORGs — e.g. `Apple (company)` to avoid
    returning the fruit's article). What we care about is that a *second*
    `lookup()` for the same key issues zero further requests.
    """

    fake = FakeWikipediaClient(responses={})
    p = WikipediaContextProvider(http_client=fake)
    p.lookup("AcmeUnknownXYZ", EntityType.ORG)
    after_first = len(fake.calls)
    assert after_first >= 1, "first call should hit the network at least once"
    p.lookup("AcmeUnknownXYZ", EntityType.ORG)
    assert len(fake.calls) == after_first  # no new calls


def test_truncates_very_long_extracts():
    long_text = "Sentence one. " + ("More text. " * 200)
    fake = FakeWikipediaClient(
        {
            ("BigArticle", "en"): {
                "title": "BigArticle",
                "extract": long_text,
                "type": "standard",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    ctx = p.lookup("BigArticle", EntityType.ORG)
    assert ctx is not None
    assert len(ctx) <= 280


def test_strips_whitespace_and_trailing_dots():
    fake = FakeWikipediaClient(
        {
            ("Cleanme", "en"): {
                "title": "Cleanme",
                "extract": "  Cleanme is a thing.   \n\n",
                "type": "standard",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    ctx = p.lookup("Cleanme", EntityType.ORG)
    assert ctx == "Cleanme is a thing."


def test_only_consults_wikipedia_for_org_and_loc_types():
    """Privacy guardrail: we don't query Wikipedia for PERSON/EMAIL/PHONE/etc.
    Querying Wikipedia for a person's name leaks the name to Wikipedia's
    server logs. ORG and LOC names are typically already public knowledge,
    but we still expect the user to opt in for sensitive matters."""

    fake = FakeWikipediaClient(
        {
            ("John Doe", "en"): {
                "title": "John Doe",
                "extract": "Some person",
                "type": "standard",
            }
        }
    )
    p = WikipediaContextProvider(http_client=fake)
    assert p.lookup("John Doe", EntityType.PERSON) is None
    assert p.lookup("john@example.com", EntityType.EMAIL) is None
    assert fake.calls == []  # no network call attempted


def test_default_client_is_a_real_http_client_not_required_in_tests():
    """We can construct the provider without explicitly passing a client.
    Tests that need to assert behaviour always inject a Fake; this just
    verifies the constructor signature allows the production path."""

    p = WikipediaContextProvider()
    # Don't actually call lookup() here — that would hit Wikipedia in CI.
    assert isinstance(p.http, HttpClientProtocol) or hasattr(p.http, "get_summary")
