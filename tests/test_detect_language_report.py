"""Languages seen in a document, including those Jude has no model for."""

from __future__ import annotations

from collections import Counter

import jude.detect.spacy_detector as sd
from jude.detect.language import detect_language_any


def test_detect_language_any_without_filter():
    assert detect_language_any("The board approved the merger with the supplier last week.") == "en"
    assert detect_language_any("Der Vorstand hat die Fusion mit dem Lieferanten genehmigt.") == "de"
    assert detect_language_any("Hi") is None


def test_unmodelled_language_reported(monkeypatch):
    german = "Der Vorstand hat die Fusion mit dem Lieferanten letzte Woche genehmigt."
    english = "The board approved the merger with the supplier last week."
    text = f"{german}\n\n{english}\n\nxx"

    class FakeDoc:
        ents: tuple = ()

    monkeypatch.setattr(
        sd, "detect_language_any",
        lambda chunk, **kw: "de" if chunk == german else ("en" if chunk == english else None),
    )
    monkeypatch.setattr(
        sd, "detect_language",
        lambda chunk, supported=("en",), **kw: "en" if chunk == english else None,
    )
    monkeypatch.setattr(sd, "_resolve_model_for_language", lambda lang, overrides: "fake_model")
    monkeypatch.setattr(sd, "_load_model", lambda name: (lambda chunk: FakeDoc()))
    det = sd.SpacyDetector(languages=("en", "fr", "nl"))
    assert det.detect(text) == []
    assert det.last_unmodelled == ["de"]
    assert det.last_languages == Counter({"de": 1, "en": 1, "und": 1})
    det.detect(english)
    assert det.last_unmodelled == [] and det.last_languages == Counter({"en": 1})
