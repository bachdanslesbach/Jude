"""The review launcher must act only on files a person saved in Word.

File dates cannot tell an export from a save (the corpus record is
often rebuilt after the export). `export` therefore writes a manifest
of the exported files' modification times next to them; a review copy
is "saved since export" iff its current mtime differs from the
manifest's."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _corpus(path: Path) -> None:
    path.write_text(json.dumps({
        "id": "doc_099_test_en", "title": "t", "language": "en",
        "text": "Kestrel Foods NV sued Zeta Holdings Ltd.",
        "gold_spans": [{"start": 0, "end": 16, "type": "ORG", "text": "Kestrel Foods NV"}],
        "public_spans": [], "split": "heldout",
    }), encoding="utf-8")


def test_export_writes_manifest_and_saved_since_export_detects_a_resave(tmp_path: Path):
    from benchmark.docx_gold import export_docx, saved_since_export, write_manifest

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _corpus(corpus / "doc_099_test_en.json")
    out = tmp_path / "review"
    out.mkdir()
    docx = out / "doc_099_test_en.docx"
    export_docx(corpus / "doc_099_test_en.json", docx)
    write_manifest(out, [docx])

    manifest = json.loads((out / ".export-manifest.json").read_text(encoding="utf-8"))
    assert "doc_099_test_en.docx" in manifest
    assert saved_since_export(out) == []

    # A person opens the copy in Word and saves it (mtime moves).
    os.utime(docx, (docx.stat().st_atime, docx.stat().st_mtime + 60))
    assert [p.name for p in saved_since_export(out)] == ["doc_099_test_en.docx"]


def test_files_without_manifest_entry_are_reported_not_ingested(tmp_path: Path):
    from benchmark.docx_gold import saved_since_export

    out = tmp_path / "review"
    out.mkdir()
    (out / "doc_098_orphan_en.docx").write_bytes(b"x")
    (out / ".export-manifest.json").write_text("{}", encoding="utf-8")
    assert saved_since_export(out) == []
    assert [p.name for p in saved_since_export(out, include_unknown=True)] == ["doc_098_orphan_en.docx"]
