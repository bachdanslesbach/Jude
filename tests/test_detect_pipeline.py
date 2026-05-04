from jude.detect import resolve_overlaps
from jude.detect.regex_rules import RegexDetector
from jude.types import Detection, DetectionSource, EntityType


def test_regex_detects_emails_and_ibans():
    text = "Contact me at john.doe@acme.eu or wire to BE68 5390 0754 7034."
    detections = RegexDetector().detect(text)
    by_type = {d.entity_type for d in detections}
    assert EntityType.EMAIL in by_type
    assert EntityType.IBAN in by_type


def test_regex_detects_eu_case_refs():
    text = "See Case C-403/19 and ECLI:EU:C:2020:512."
    detections = RegexDetector().detect(text)
    types = [d.entity_type for d in detections]
    assert types.count(EntityType.CASE_REF) == 2


def test_resolve_overlaps_prefers_higher_priority_source():
    spacy_det = Detection(
        text="John Doe", start=0, end=8, entity_type=EntityType.PERSON,
        source=DetectionSource.SPACY,
    )
    user_det = Detection(
        text="John Doe", start=0, end=8, entity_type=EntityType.PERSON,
        source=DetectionSource.USER,
    )
    kept = resolve_overlaps([spacy_det, user_det])
    assert len(kept) == 1
    assert kept[0].source == DetectionSource.USER


def test_resolve_overlaps_prefers_longer_span_within_same_source():
    short = Detection(
        text="Acme", start=0, end=4, entity_type=EntityType.ORG,
        source=DetectionSource.SPACY,
    )
    long = Detection(
        text="Acme Industries", start=0, end=15, entity_type=EntityType.ORG,
        source=DetectionSource.SPACY,
    )
    kept = resolve_overlaps([short, long])
    assert len(kept) == 1
    assert kept[0].end == 15


def test_resolve_overlaps_keeps_disjoint_spans():
    a = Detection(
        text="Acme", start=0, end=4, entity_type=EntityType.ORG,
        source=DetectionSource.SPACY,
    )
    b = Detection(
        text="Beta", start=10, end=14, entity_type=EntityType.ORG,
        source=DetectionSource.SPACY,
    )
    kept = resolve_overlaps([a, b])
    assert len(kept) == 2
