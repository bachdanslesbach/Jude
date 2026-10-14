"""A third corpus split, `public`: excerpts of real published documents
(judgments, Commission decisions) annotated as if they were a client's
confidential file. Provenance must travel with the record, and the
uniqueness check must not treat two real documents that share a real
counsel or judge as a synthetic fingerprint."""

from __future__ import annotations

import json
from pathlib import Path


def _spec(doc_id: str, text: str, entities, split="public", **extra):  # noqa: ANN001
    s = {
        "id": doc_id, "title": "t", "language": "en", "text": text, "split": split,
        "entities": [{"surface": a, "type": b} for a, b in entities],
        "public": [], "traps": [], "notes": "",
    }
    s.update(extra)
    return s


def test_build_carries_source_and_provenance():
    from benchmark.synth import build

    prov = {"source": "courtlistener", "url": "https://www.courtlistener.com/opinion/1/x/",
            "licence": "public domain (US federal opinion)", "court": "ca2", "date": "2024-03-01"}
    doc = build(_spec("doc_101_us_opinion_en", "Acme Corp. appealed.", [("Acme Corp.", "ORG")],
                      source="public-courtlistener", provenance=prov))
    assert doc["split"] == "public"
    assert doc["source"] == "public-courtlistener"
    assert doc["provenance"] == prov


def test_two_public_documents_may_share_real_counsel(tmp_path: Path):
    from benchmark.synth import collisions

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc_101_a_en.json").write_text(json.dumps({
        "id": "doc_101_a_en", "title": "t", "language": "en", "split": "public",
        "text": "represented by Daniel Beard KC",
        "gold_spans": [{"start": 15, "end": 30, "type": "PERSON", "text": "Daniel Beard KC"}],
        "public_spans": [],
    }), encoding="utf-8")
    mine = _spec("doc_102_b_en", "Daniel Beard KC appeared.", [("Daniel Beard KC", "PERSON")])
    assert collisions(mine, corpus) == []
    # …but a synthetic document must still not reuse a name from any split.
    synthetic = _spec("doc_099_c_en", "Daniel Beard KC appeared.", [("Daniel Beard KC", "PERSON")],
                      split="heldout")
    assert collisions(synthetic, corpus) != []
