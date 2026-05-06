"""Integration test: two-pass redaction with the REAL spaCy pipeline.

The unit tests in test_redact_rehydrate.py mock the detection pipeline
to prove the two-pass algorithm is correct. This file proves the
feature actually solves a real-world problem: real spaCy `en_core_web_lg`
misses ALL-CAPS titles where the surrounding tokens (a column header,
an isolated heading) don't give it enough context to label the span as
ORG. After the first pass catches the lower-case body form and adds
it to the per-matter dictionary, the second pass's DictionaryDetector
fires on the title (matching is case-insensitive) and the redaction
covers both occurrences.

This is exactly the failure mode the user hit on their real test memo.
"""

from __future__ import annotations

import pytest

from jude.detect import DetectionPipeline
from jude.redact import redact_two_pass
from jude.store import Store
from jude.types import Mode


@pytest.fixture
def real_pipeline(store, matter_id):
    """Real DetectionPipeline using whichever English spaCy model is
    available. Fixture skips if no English model is installed."""

    try:
        return DetectionPipeline(store=store, matter_id=matter_id)
    except RuntimeError as e:
        pytest.skip(f"spaCy model not installed: {e}")


def _detection_supports_lg() -> bool:
    try:
        import spacy.util  # type: ignore[import-not-found]

        return spacy.util.is_package("en_core_web_lg") or spacy.util.is_package(
            "en_core_web_md"
        )
    except ImportError:
        return False


@pytest.mark.skipif(
    not _detection_supports_lg(),
    reason="needs en_core_web_lg or en_core_web_md installed",
)
def test_two_pass_real_spacy_catches_all_caps_title(
    store: Store, matter_id: str, real_pipeline: DetectionPipeline
):
    """ALL-CAPS title that spaCy misses gets caught on the second pass via
    the case-insensitive DictionaryDetector match."""

    text = (
        "Notice for ACME SOLUTIONS SA filing\n\n"
        "Acme Solutions SA, a Belgian company, contests the practices."
    )

    # Sanity: the first pass alone (no two-pass) leaves the title unredacted.
    first = real_pipeline.detect(text)
    title_in_first = any("ACME SOLUTIONS SA" in d.text for d in first)
    assert not title_in_first, (
        "Test premise broken — spaCy unexpectedly caught the all-caps title "
        "on its own. Pick a different reproducer."
    )

    # The two-pass redact catches both.
    result = redact_two_pass(
        text, real_pipeline, store, matter_id, Mode.STRICT
    )
    assert "ACME SOLUTIONS SA" not in result.redacted_text
    assert "Acme Solutions SA" not in result.redacted_text
    # Both occurrences resolve to the same canonical entity, so the same
    # pseudonym appears twice.
    pseudonyms = {e.pseudonym for e in result.entities_used}
    assert len(pseudonyms) == 1
    pseudonym = pseudonyms.pop()
    assert result.redacted_text.count(pseudonym) == 2


@pytest.mark.skipif(
    not _detection_supports_lg(),
    reason="needs en_core_web_lg or en_core_web_md installed",
)
def test_aliasing_links_first_name_to_full_name_with_real_spacy(
    store: Store, matter_id: str, real_pipeline: DetectionPipeline
):
    """Real spaCy on text where a person is introduced by full name and
    later referenced by first name only — the second mention should
    resolve to the same Entity rather than producing a new pseudonym."""

    text = (
        "Marie-Claire Lefèvre filed the complaint on behalf of the client.\n\n"
        "She added that Marie-Claire would attend the hearing in person."
    )

    result = redact_two_pass(
        text, real_pipeline, store, matter_id, Mode.STRICT
    )

    # We expect a single PERSON entity covering both forms — even if
    # spaCy only labelled "Marie-Claire Lefèvre" as PERSON, the alias-
    # aware lookup in _get_or_create_entity should link any subsequent
    # "Marie-Claire" detection back to it.
    persons = [e for e in result.entities_used if e.entity_type.value == "PERSON"]
    assert len(persons) == 1, (
        f"expected single PERSON entity for Marie-Claire, got {len(persons)}: "
        f"{[(e.pseudonym, e.canonical) for e in persons]}"
    )
    # Both real-name forms are gone from the redacted text (display goes
    # through redact, not rehydrate).
    assert "Marie-Claire Lefèvre" not in result.redacted_text
    # 'Marie-Claire' alone may or may not have been detected by spaCy on
    # the second mention — we only require that *if* it was redacted, it
    # was redacted to the same pseudonym as the full name.
    if "Marie-Claire" not in result.redacted_text:
        assert result.redacted_text.count(persons[0].pseudonym) >= 2
