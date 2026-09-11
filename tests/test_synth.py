"""Spec → gold builder and the programmatic quality bar for synthetic
corpus documents (benchmark/synth.py)."""

from __future__ import annotations

import pytest


def _spec(**overrides):  # noqa: ANN003
    words = ("The board of Kestrel Foods NV (\"KFN\") met at Avenue Louise 250, 1050 Brussels. "
             "Mr. Van Acker chaired; Pieter Van Acker signed. Counsel: Sophie Martin, "
             "s.martin@example-law.eu, +32 2 555 0100. Ref M-2026-GAN-004. IBAN BE68 5390 0754 7034. "
             "The European Commission and the Belgian Competition Authority must clear Project Ganymede; "
             "Ganymede closes in Q4. KFN's bank is BCEE. See kestrelfoods.example.com. ")
    text = words * 8  # ~470 words
    base = {
        "id": "doc_099_test_en",
        "title": "Test",
        "language": "en",
        "genre": "test",
        "split": "heldout",
        "text": text,
        "entities": [
            {"surface": "Kestrel Foods NV", "type": "ORG"},
            {"surface": "KFN", "type": "ORG"},
            {"surface": "Avenue Louise 250", "type": "LOC"},
            {"surface": "Brussels", "type": "LOC"},
            {"surface": "Mr. Van Acker", "type": "PERSON"},
            {"surface": "Pieter Van Acker", "type": "PERSON"},
            {"surface": "Van Acker", "type": "PERSON"},
            {"surface": "Sophie Martin", "type": "PERSON"},
            {"surface": "s.martin@example-law.eu", "type": "EMAIL"},
            {"surface": "+32 2 555 0100", "type": "PHONE"},
            {"surface": "M-2026-GAN-004", "type": "CASE_REF"},
            {"surface": "BE68 5390 0754 7034", "type": "IBAN"},
            {"surface": "Project Ganymede", "type": "ORG"},
            {"surface": "Ganymede", "type": "ORG"},
            {"surface": "BCEE", "type": "ORG"},
            {"surface": "kestrelfoods.example.com", "type": "URL"},
        ],
        "public": ["European Commission", "Belgian Competition Authority"],
        "traps": ["codename", "acronym-defined", "bank-acronym", "bare-domain"],
        "notes": "SHOULD redact: parties. SHOULD NOT redact: Commission, BCA.",
    }
    base.update(overrides)
    return base


class TestBuild:
    def test_every_occurrence_is_annotated_longest_first(self):
        from benchmark.synth import build

        doc = build(_spec())
        texts = [g["text"] for g in doc["gold_spans"]]
        assert texts.count("Kestrel Foods NV") == 8
        assert texts.count("Pieter Van Acker") == 8
        # "Van Acker" inside "Pieter Van Acker" / "Mr. Van Acker" is not a
        # separate span; every span is one of the listed surfaces.
        assert "Van Acker" not in texts
        for g in doc["gold_spans"]:
            assert doc["text"][g["start"]:g["end"]] == g["text"]

    def test_word_boundaries(self):
        from benchmark.synth import build

        spec = _spec(text="KFN and KFNX and xKFN and KFN.", entities=[{"surface": "KFN", "type": "ORG"}], public=[])
        doc = build(spec)
        assert [(g["start"], g["end"]) for g in doc["gold_spans"]] == [(0, 3), (26, 29)]

    def test_public_mentions_never_overlap_gold(self):
        from benchmark.synth import build

        doc = build(_spec())
        assert {p["text"] for p in doc["public_spans"]} == {"European Commission", "Belgian Competition Authority"}
        for p in doc["public_spans"]:
            assert p["type"] == "PUBLIC"
            assert not any(not (p["end"] <= g["start"] or g["end"] <= p["start"]) for g in doc["gold_spans"])

    def test_output_fields(self):
        from benchmark.synth import build

        doc = build(_spec())
        assert doc["source"] == "agent-synthetic"
        assert doc["split"] == "heldout"
        assert doc["id"] == "doc_099_test_en"


class TestValidate:
    def test_good_spec_passes(self):
        from benchmark.synth import validate

        assert validate(_spec()) == []

    @pytest.mark.parametrize("override, fragment", [
        ({"text": "Too short."}, "words"),
        ({"id": "doc21_x_en"}, "must look like"),
        ({"language": "fr"}, "suffix must equal language"),
        ({"entities": [{"surface": "Nowhere Ltd", "type": "ORG"}]}, "does not occur"),
        ({"entities": [{"surface": "KFN", "type": "COMPANY"}]}, "not in"),
        ({"public": ["Nonexistent Authority"]}, "does not occur"),
        ({"traps": ["codename"]}, "traps declared"),
        ({"traps": ["codename", "unicorn", "vessel"]}, "unknown traps"),
    ])
    def test_bad_specs_are_rejected_with_a_reason(self, override, fragment):
        from benchmark.synth import validate

        errs = validate(_spec(**override))
        assert any(fragment in e for e in errs), errs

    def test_whitelisted_surface_as_entity_is_a_policy_conflict(self):
        from benchmark.synth import validate

        spec = _spec()
        spec["entities"].append({"surface": "European Commission", "type": "ORG"})
        errs = validate(spec)
        assert any("whitelist" in e for e in errs), errs

    def test_language_mismatch_is_detected(self):
        from benchmark.synth import validate

        spec = _spec(id="doc_099_test_fr", language="fr")  # English text
        errs = validate(spec)
        assert any("detected as 'en'" in e for e in errs), errs
