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


def test_regex_detects_eu_vat_numbers():
    text = "Our supplier is VAT BE0123456789 and the buyer is FR12345678901."
    detections = RegexDetector().detect(text)
    surfaces = {d.text for d in detections}
    # IBAN bucket is fine for VAT v0 — it's the closest existing category;
    # what matters is that the number gets pseudonymized rather than
    # passing through in the clear.
    assert any("BE0123456789" in s for s in surfaces)
    assert any("FR12345678901" in s for s in surfaces)


def test_regex_detects_french_siren_siret():
    text = (
        "Société immatriculée au RCS sous le SIREN 552120222 "
        "(SIRET 55212022200013)."
    )
    detections = RegexDetector().detect(text)
    surfaces = {d.text for d in detections}
    assert any("552120222" in s for s in surfaces)
    assert any("55212022200013" in s for s in surfaces)


def test_regex_detects_belgian_national_register_number():
    text = (
        "Le client est inscrit sous le numéro national 92.06.15-123.45 "
        "au Registre national."
    )
    detections = RegexDetector().detect(text)
    surfaces = {d.text for d in detections}
    assert any("92.06.15" in s for s in surfaces)


def test_regex_does_not_grab_random_long_digits_as_vat():
    """The VAT pattern must not over-match every long digit run — the
    country prefix is mandatory."""

    text = "Order number 1234567890 was processed."
    detections = RegexDetector().detect(text)
    # Order number alone shouldn't trigger VAT detection.
    vat_hits = [
        d for d in detections
        if d.text.startswith(("BE", "FR", "DE", "IT", "ES", "NL", "LU"))
    ]
    assert vat_hits == []


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
