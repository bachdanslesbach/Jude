"""Tests for the optional openai/privacy-filter detector.

Most tests are gated on `transformers` being installed AND the model being
downloadable. The cheap structural tests (overlap priority, label mapping,
detection-pipeline integration with a fake stub) always run.
"""

from __future__ import annotations

import pytest

from jude.detect import DetectionPipeline, resolve_overlaps
from jude.detect.privacy_filter_detector import _LABEL_MAP
from jude.store import Store
from jude.types import Detection, DetectionSource, EntityType


def test_label_map_drops_dates():
    assert _LABEL_MAP["private_date"] is None


def test_label_map_routes_secret_to_secret():
    assert _LABEL_MAP["secret"] == EntityType.SECRET


def test_label_map_routes_address_to_loc():
    # Addresses are pseudonymised through the LOC bucket; we don't need a
    # separate prefix for v0.
    assert _LABEL_MAP["private_address"] == EntityType.LOC


def test_overlap_priority_privacy_filter_wins_over_spacy():
    spacy_det = Detection(
        text="Alice Smith",
        start=0,
        end=11,
        entity_type=EntityType.PERSON,
        source=DetectionSource.SPACY,
    )
    pf_det = Detection(
        text="Alice Smith",
        start=0,
        end=11,
        entity_type=EntityType.PERSON,
        source=DetectionSource.PRIVACY_FILTER,
    )
    kept = resolve_overlaps([spacy_det, pf_det])
    assert len(kept) == 1
    assert kept[0].source == DetectionSource.PRIVACY_FILTER


def test_overlap_priority_dictionary_wins_over_privacy_filter():
    dict_det = Detection(
        text="Acme",
        start=0,
        end=4,
        entity_type=EntityType.ORG,
        source=DetectionSource.DICTIONARY,
    )
    pf_det = Detection(
        text="Acme",
        start=0,
        end=4,
        entity_type=EntityType.ORG,
        source=DetectionSource.PRIVACY_FILTER,
    )
    kept = resolve_overlaps([dict_det, pf_det])
    assert len(kept) == 1
    assert kept[0].source == DetectionSource.DICTIONARY


def test_pipeline_does_not_load_filter_when_disabled(
    store: Store, matter_id: str
):
    pipeline = DetectionPipeline(
        store=store, matter_id=matter_id, use_privacy_filter=False
    )
    assert pipeline.privacy_filter is None


@pytest.mark.skipif(
    True,
    reason="full integration test requires 1.5 GB model download; "
    "run manually with `pytest -k 'privacy_filter and integration'`",
)
def test_privacy_filter_detects_email_and_address():
    """End-to-end: instantiate the detector, run it, expect at least one
    private_email and one private_address span. Skipped by default."""

    from jude.detect.privacy_filter_detector import PrivacyFilterDetector

    det = PrivacyFilterDetector()
    text = (
        "Send the draft to alice.smith@example.com. The registered office "
        "is 22 rue de Rivoli, 75001 Paris, France."
    )
    found = det.detect(text)
    types = {d.entity_type for d in found}
    assert EntityType.EMAIL in types
    assert EntityType.LOC in types
