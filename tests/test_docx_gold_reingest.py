"""Re-ingesting a reviewed .docx must not lose what the corpus knows
about the document: its split (dev / heldout), genre, traps. A held-out
document that silently fell back to `dev` on review would corrupt the
one number the benchmark stands on."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.schema import GoldDocument


def _corpus_json(path: Path) -> None:
    text = "Kestrel Foods NV sued Zeta Holdings Ltd before the European Commission."
    doc = {
        "id": "doc_099_test_en", "title": "Test title", "language": "en", "text": text,
        "gold_spans": [
            {"start": 0, "end": 16, "type": "ORG", "text": "Kestrel Foods NV"},
            {"start": 22, "end": 39, "type": "ORG", "text": "Zeta Holdings Ltd"},
        ],
        "public_spans": [{"start": 51, "end": 70, "type": "PUBLIC", "text": "European Commission"}],
        "notes": "SHOULD redact: parties.", "source": "agent-synthetic",
        "split": "heldout", "genre": "test genre", "traps": ["codename", "address"],
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_reingest_keeps_split_genre_traps_title_notes(tmp_path: Path):
    from benchmark.docx_gold import export_docx, main

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    src = corpus / "doc_099_test_en.json"
    _corpus_json(src)
    docx = tmp_path / "doc_099_test_en.docx"
    export_docx(src, docx)

    main(["ingest", str(docx), "--id", "doc_099_test_en", "--out", str(corpus), "--force"])

    after = json.loads(src.read_text(encoding="utf-8"))
    assert after["split"] == "heldout"
    assert after["genre"] == "test genre"
    assert after["traps"] == ["codename", "address"]
    assert after["title"] == "Test title"
    assert after["notes"] == "SHOULD redact: parties."
    assert after["source"] == "docx-highlight"
    assert after.get("reviewed") is True
    gold = GoldDocument.from_json(src)
    assert gold.split == "heldout"
    assert [g.text for g in gold.gold_spans] == ["Kestrel Foods NV", "Zeta Holdings Ltd"]
    assert [p.text for p in gold.public_spans] == ["European Commission"]


def test_fresh_ingest_defaults_to_heldout_and_reviewed(tmp_path: Path):
    """A document that did not exist in the corpus and arrives through
    a reviewed .docx was never tuned on: it belongs to the held-out
    split."""

    from benchmark.docx_gold import export_docx, main

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    seed = tmp_path / "seed.json"
    _corpus_json(seed)
    docx = tmp_path / "doc_099_test_en.docx"
    export_docx(seed, docx)

    main(["ingest", str(docx), "--id", "doc_099_test_en", "--out", str(corpus)])

    after = json.loads((corpus / "doc_099_test_en.json").read_text(encoding="utf-8"))
    assert after["split"] == "heldout"
    assert after.get("reviewed") is True
