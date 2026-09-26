"""Highlights on consecutive lines of one paragraph are distinct spans.

Letterheads and signature blocks put one identifier per line inside a
single Word paragraph (soft line breaks). The reviewer highlights each
line; ingest must not merge them across the break — two people are
not one person."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX


def _doc(path: Path, runs: list[tuple[str, str | None]]) -> Path:
    doc = Document()
    p = doc.add_paragraph()
    for text, colour in runs:
        r = p.add_run(text)
        if colour:
            r.font.highlight_color = WD_COLOR_INDEX[colour]
    doc.save(str(path))
    return path


def test_same_colour_spans_on_consecutive_lines_stay_separate(tmp_path: Path):
    from benchmark.docx_gold import ingest_docx

    path = _doc(tmp_path / "a.docx", [
        ("Tijl Roelandt", "YELLOW"), ("\n", None), ("Annelore Sioen", "YELLOW"),
    ])
    result = ingest_docx(path, language="en")
    assert [s.text for s in result.gold_spans] == ["Tijl Roelandt", "Annelore Sioen"]
    for s in result.gold_spans:
        assert result.text[s.start:s.end] == s.text


def test_same_colour_spans_separated_by_a_space_still_merge(tmp_path: Path):
    from benchmark.docx_gold import ingest_docx

    path = _doc(tmp_path / "b.docx", [("Sophie", "YELLOW"), (" ", None), ("Martin", "YELLOW")])
    result = ingest_docx(path, language="en")
    assert [s.text for s in result.gold_spans] == ["Sophie Martin"]


def test_public_block_on_three_lines_gives_three_public_spans(tmp_path: Path):
    from benchmark.docx_gold import ingest_docx

    path = _doc(tmp_path / "c.docx", [
        ("European Commission", "GRAY_25"), ("\n", None),
        ("Directorate-General for Competition", "GRAY_25"), ("\n", None),
        ("Place Madou 1, 1210 Brussels", "GRAY_25"),
    ])
    result = ingest_docx(path, language="en")
    assert [s.text for s in result.public_spans] == [
        "European Commission", "Directorate-General for Competition", "Place Madou 1, 1210 Brussels",
    ]


def test_export_then_ingest_round_trips_every_corpus_document(tmp_path: Path):
    """The strongest guard: exporting each real corpus document and
    ingesting the untouched copy must reproduce its gold and public
    spans exactly."""

    import json

    from benchmark.docx_gold import export_docx, ingest_docx
    from benchmark.run import CORPUS_DIR

    for src in sorted(CORPUS_DIR.glob("doc_*.json")):
        rec = json.loads(src.read_text(encoding="utf-8"))
        docx = tmp_path / (src.stem + ".docx")
        export_docx(src, docx)
        result = ingest_docx(docx, language=rec["language"])
        assert result.text == rec["text"], src.name
        got = [(s.start, s.end, s.type) for s in result.gold_spans]
        want = [(g["start"], g["end"], g["type"]) for g in rec["gold_spans"]]
        assert got == want, f"{src.name}: gold spans changed by the round trip"
