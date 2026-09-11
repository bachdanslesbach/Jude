"""Cross-corpus uniqueness for synthetic documents.

The judge's first finding on the first batch: agents reuse names
("Lambrechts" in six documents, one "Corv-" family in seven) and
reference numbers ("0417" in ten). A known-entity detector or a model
trained on such data learns the fingerprint instead of the task, and a
held-out split that shares names with the tuning split is not held out.
The validator therefore checks every new spec against the existing
corpus and refuses collisions.
"""

from __future__ import annotations

import json
from pathlib import Path


def _corpus_doc(path: Path, doc_id: str, text: str, spans: list[tuple[str, str]]) -> None:
    gold = []
    for surface, typ in spans:
        i = text.index(surface)
        gold.append({"start": i, "end": i + len(surface), "type": typ, "text": surface})
    path.write_text(json.dumps({
        "id": doc_id, "title": "t", "language": "en", "text": text,
        "gold_spans": gold, "public_spans": [], "split": "dev",
    }), encoding="utf-8")


def _spec(entities: list[tuple[str, str]], text: str) -> dict:
    return {
        "id": "doc_099_test_en", "title": "t", "language": "en", "text": text,
        "entities": [{"surface": s, "type": t} for s, t in entities],
        "public": [], "traps": [], "notes": "",
    }


class TestCollisions:
    def test_reused_party_name_is_reported(self, tmp_path: Path):
        from benchmark.synth import collisions

        _corpus_doc(tmp_path / "doc_001_a_en.json", "doc_001_a_en",
                    "Kestrel Foods NV sued Zeta Holdings Ltd.",
                    [("Kestrel Foods NV", "ORG"), ("Zeta Holdings Ltd", "ORG")])
        spec = _spec([("Kestrel Foods NV", "ORG"), ("Orvane Capital SA", "ORG")],
                     "Kestrel Foods NV and Orvane Capital SA signed.")
        errs = collisions(spec, tmp_path)
        assert any("Kestrel Foods NV" in e and "doc_001_a_en" in e for e in errs), errs
        assert not any("Orvane" in e for e in errs)

    def test_reused_surname_inside_a_longer_name_is_reported(self, tmp_path: Path):
        from benchmark.synth import collisions

        _corpus_doc(tmp_path / "doc_001_a_en.json", "doc_001_a_en",
                    "Counsel Olivier Lambrechts attended.", [("Olivier Lambrechts", "PERSON")])
        spec = _spec([("Julie Lambrechts", "PERSON")], "Julie Lambrechts signed.")
        errs = collisions(spec, tmp_path)
        assert any("Lambrechts" in e for e in errs), errs

    def test_reused_reference_number_and_address_are_reported(self, tmp_path: Path):
        from benchmark.synth import collisions

        _corpus_doc(tmp_path / "doc_001_a_en.json", "doc_001_a_en",
                    "Ref HV/2026/0417-KVN at Louizalaan 331, 1050 Brussels.",
                    [("HV/2026/0417-KVN", "CASE_REF"), ("Louizalaan 331, 1050 Brussels", "LOC")])
        spec = _spec([("VD/2026/0417-SAB", "CASE_REF"), ("Louizalaan 331", "LOC")],
                     "Ref VD/2026/0417-SAB at Louizalaan 331.")
        errs = collisions(spec, tmp_path)
        assert any("0417" in e for e in errs), errs
        assert any("Louizalaan 331" in e for e in errs), errs

    def test_banks_by_acronym_and_public_bodies_are_allowed(self, tmp_path: Path):
        from benchmark.synth import collisions

        _corpus_doc(tmp_path / "doc_001_a_en.json", "doc_001_a_en",
                    "KBC financed it; the European Commission cleared it.", [("KBC", "ORG")])
        spec = _spec([("KBC", "ORG")], "KBC financed it; the European Commission cleared it.")
        spec["public"] = ["European Commission"]
        assert collisions(spec, tmp_path) == []

    def test_own_document_is_not_a_collision(self, tmp_path: Path):
        from benchmark.synth import collisions

        _corpus_doc(tmp_path / "doc_099_test_en.json", "doc_099_test_en",
                    "Orvane Capital SA signed.", [("Orvane Capital SA", "ORG")])
        spec = _spec([("Orvane Capital SA", "ORG")], "Orvane Capital SA signed.")
        assert collisions(spec, tmp_path) == []


class TestValidateWithCorpus:
    def test_validate_takes_a_corpus_dir_and_reports_collisions(self, tmp_path: Path):
        from benchmark.synth import validate

        _corpus_doc(tmp_path / "doc_001_a_en.json", "doc_001_a_en",
                    "Kestrel Foods NV sued.", [("Kestrel Foods NV", "ORG")])
        from tests.test_synth import _spec as good_spec  # a spec that passes the bar

        spec = good_spec()
        assert validate(spec) == []
        errs = validate(spec, corpus_dir=tmp_path)
        assert any("Kestrel Foods NV" in e for e in errs), errs
