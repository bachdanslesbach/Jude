"""Word-highlight annotation protocol for the benchmark corpus.

A reviewer annotates a .docx in Word by highlighting spans with one
colour per entity type (legend in `benchmark.docx_gold.HIGHLIGHT_TO_TYPE`).
`ingest_docx` turns that into a gold document whose `text` is exactly
what Jude's DOCX adapter extracts, so offsets line up with what the
pipeline sees. `prefill_docx` does the reverse — writes Jude's own
detections into a copy as highlights — so the reviewer corrects rather
than annotates from scratch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document
from docx.enum.text import WD_COLOR_INDEX

from benchmark.schema import GoldDocument, GoldSpan, PredSpan
from jude.adapters.docx import DocxAdapter


def _doc_with_runs(path: Path, paragraphs: list[list[tuple[str, str | None]]]) -> Path:
    doc = Document()
    for runs in paragraphs:
        p = doc.add_paragraph()
        for text, colour in runs:
            r = p.add_run(text)
            if colour:
                r.font.highlight_color = WD_COLOR_INDEX[colour]
    doc.save(str(path))
    return path


def _span(text: str, needle: str, typ: str, cls=GoldSpan):  # noqa: ANN001
    i = text.index(needle)
    return cls(start=i, end=i + len(needle), type=typ, text=needle)


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------


class TestLegend:
    def test_every_jude_type_has_a_colour_and_the_map_is_a_bijection(self):
        from benchmark.docx_gold import HIGHLIGHT_TO_TYPE, TYPE_TO_HIGHLIGHT

        for typ in ("PERSON", "ORG", "LOC", "CASE_REF", "EMAIL", "PHONE", "IBAN", "URL", "SECRET"):
            assert typ in TYPE_TO_HIGHLIGHT
        assert HIGHLIGHT_TO_TYPE["YELLOW"] == "PERSON"
        assert HIGHLIGHT_TO_TYPE["BRIGHT_GREEN"] == "ORG"
        assert HIGHLIGHT_TO_TYPE["GRAY_25"] == "PUBLIC"
        assert {TYPE_TO_HIGHLIGHT[t] for t in TYPE_TO_HIGHLIGHT} == set(HIGHLIGHT_TO_TYPE)
        for colour, typ in HIGHLIGHT_TO_TYPE.items():
            assert TYPE_TO_HIGHLIGHT[typ] == colour
            assert colour in WD_COLOR_INDEX.__members__


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TestIngest:
    def test_text_is_exactly_what_the_adapter_extracts(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = tmp_path / "in.docx"
        doc = Document()
        doc.add_paragraph("Term sheet")
        doc.add_paragraph("")  # empty paragraphs are dropped by the adapter
        doc.add_paragraph("Between Acme SA and Zeta NV.")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Buyer"
        table.cell(0, 1).text = "Acme SA"
        doc.save(str(path))

        result = ingest_docx(path, language="en")
        assert result.text == DocxAdapter.read(path).text

    def test_highlighted_runs_become_typed_spans_with_document_offsets(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Term sheet", None)],
            [("Dear ", None), ("Sophie Martin", "YELLOW"), (" of ", None),
             ("Acme SA", "BRIGHT_GREEN"), (".", None)],
        ])
        result = ingest_docx(path, language="en")
        assert result.text == "Term sheet\n\nDear Sophie Martin of Acme SA."
        assert [(s.type, s.text) for s in result.gold_spans] == [
            ("PERSON", "Sophie Martin"), ("ORG", "Acme SA"),
        ]
        person = result.gold_spans[0]
        assert (person.start, person.end) == (17, 30)
        for s in result.gold_spans:
            assert result.text[s.start:s.end] == s.text

    def test_adjacent_runs_of_the_same_colour_merge(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        # Word splits runs on spell-check and edit boundaries; a reviewer
        # who highlights word by word leaves the space unhighlighted.
        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Sophie", "YELLOW"), (" ", "YELLOW"), ("Martin", "YELLOW"), (" and ", None),
             ("James", "YELLOW"), (" ", None), ("Chen", "YELLOW"), (".", None)],
        ])
        result = ingest_docx(path, language="en")
        assert [s.text for s in result.gold_spans] == ["Sophie Martin", "James Chen"]

    def test_different_colours_do_not_merge(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Sophie Martin", "YELLOW"), (" ", None), ("Acme SA", "BRIGHT_GREEN")],
        ])
        result = ingest_docx(path, language="en")
        assert [(s.type, s.text) for s in result.gold_spans] == [
            ("PERSON", "Sophie Martin"), ("ORG", "Acme SA"),
        ]

    def test_span_edges_are_trimmed_of_whitespace_and_punctuation_is_kept(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Counsel: ", None), (" Acme SA ", "BRIGHT_GREEN"), ("(the Buyer)", None)],
        ])
        result = ingest_docx(path, language="en")
        assert [s.text for s in result.gold_spans] == ["Acme SA"]
        s = result.gold_spans[0]
        assert result.text[s.start:s.end] == "Acme SA"

    def test_spans_never_cross_paragraphs(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Acme", "BRIGHT_GREEN")],
            [("SA", "BRIGHT_GREEN")],
        ])
        result = ingest_docx(path, language="en")
        assert [s.text for s in result.gold_spans] == ["Acme", "SA"]

    def test_gray_marks_public_mentions_not_gold(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("The ", None), ("European Commission", "GRAY_25"), (" fined ", None),
             ("Acme SA", "BRIGHT_GREEN"), (".", None)],
        ])
        result = ingest_docx(path, language="en")
        assert [s.text for s in result.gold_spans] == ["Acme SA"]
        assert [(s.type, s.text) for s in result.public_spans] == [("PUBLIC", "European Commission")]

    def test_unknown_colour_is_reported_not_silently_dropped(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Acme SA", "GREEN"), (" and ", None), ("Zeta NV", "BRIGHT_GREEN")],
        ])
        result = ingest_docx(path, language="en")
        assert [s.text for s in result.gold_spans] == ["Zeta NV"]
        assert any("GREEN" in w and "Acme SA" in w for w in result.warnings)

    def test_language_is_autodetected_when_not_given(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("Nous avons l'honneur de vous informer que la société ", None),
             ("Acme SA", "BRIGHT_GREEN"),
             (" a introduit un recours devant le tribunal de l'entreprise de Bruxelles.", None)],
        ])
        result = ingest_docx(path)
        assert result.language == "fr"

    def test_highlights_inside_hyperlinks_and_tables_are_seen(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx

        path = tmp_path / "in.docx"
        doc = Document()
        doc.add_paragraph("Body.")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Counsel"
        cell_p = table.cell(0, 1).paragraphs[0]
        r = cell_p.add_run("Sophie Martin")
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        doc.save(str(path))

        result = ingest_docx(path, language="en")
        assert [(s.type, s.text) for s in result.gold_spans] == [("PERSON", "Sophie Martin")]
        s = result.gold_spans[0]
        assert result.text[s.start:s.end] == "Sophie Martin"


# ---------------------------------------------------------------------------
# Corpus JSON
# ---------------------------------------------------------------------------


class TestCorpusJson:
    def test_to_corpus_dict_round_trips_into_gold_document(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx, to_corpus_dict

        path = _doc_with_runs(tmp_path / "in.docx", [
            [("The ", None), ("European Commission", "GRAY_25"), (" fined ", None),
             ("Acme SA", "BRIGHT_GREEN"), (" in ", None), ("Brussels", "TURQUOISE"), (".", None)],
        ])
        result = ingest_docx(path, language="en")
        d = to_corpus_dict(result, doc_id="doc_021_fine_en", title="Fine", notes="test")
        out = tmp_path / "doc_021_fine_en.json"
        out.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        gold = GoldDocument.from_json(out)
        assert gold.id == "doc_021_fine_en"
        assert gold.language == "en"
        assert gold.text == result.text
        assert [(s.type, s.text) for s in gold.gold_spans] == [("ORG", "Acme SA"), ("LOC", "Brussels")]
        assert [(s.type, s.text) for s in gold.public_spans] == [("PUBLIC", "European Commission")]
        assert d["source"] == "docx-highlight"

    def test_existing_corpus_files_still_load_without_public_spans(self):
        from benchmark.run import CORPUS_DIR

        doc = GoldDocument.from_json(next(CORPUS_DIR.glob("doc_001_*.json")))
        assert doc.public_spans == ()


# ---------------------------------------------------------------------------
# Prefill (Jude → highlights) and round trip
# ---------------------------------------------------------------------------


class TestPrefill:
    def test_prefill_preserves_text_and_paragraphs(self, tmp_path: Path):
        from benchmark.docx_gold import prefill_docx

        src = tmp_path / "in.docx"
        dst = tmp_path / "out.docx"
        doc = Document()
        doc.add_paragraph("Term sheet")
        doc.add_paragraph("Between Acme SA and Sophie Martin, Brussels.")
        doc.save(str(src))
        text = DocxAdapter.read(src).text

        prefill_docx(src, dst, [
            _span(text, "Acme SA", "ORG", PredSpan),
            _span(text, "Sophie Martin", "PERSON", PredSpan),
        ])
        assert DocxAdapter.read(dst).text == text

    def test_prefill_then_ingest_round_trips_spans(self, tmp_path: Path):
        from benchmark.docx_gold import ingest_docx, prefill_docx

        src = tmp_path / "in.docx"
        dst = tmp_path / "out.docx"
        doc = Document()
        doc.add_paragraph("Term sheet")
        doc.add_paragraph("The European Commission fined Acme SA; counsel Sophie Martin, Brussels.")
        doc.add_paragraph("Ref: Case T-203/24. IBAN BE68 5390 0754 7034.")
        doc.save(str(src))
        text = DocxAdapter.read(src).text

        spans = [
            _span(text, "Acme SA", "ORG", PredSpan),
            _span(text, "Sophie Martin", "PERSON", PredSpan),
            _span(text, "Brussels", "LOC", PredSpan),
            _span(text, "Case T-203/24", "CASE_REF", PredSpan),
            _span(text, "BE68 5390 0754 7034", "IBAN", PredSpan),
        ]
        public = [_span(text, "European Commission", "PUBLIC", PredSpan)]
        prefill_docx(src, dst, spans, public=public)

        result = ingest_docx(dst, language="en")
        assert result.text == text
        assert [(s.type, s.text, s.start, s.end) for s in result.gold_spans] == [
            (s.type, s.text, s.start, s.end) for s in spans
        ]
        assert [(s.type, s.text) for s in result.public_spans] == [("PUBLIC", "European Commission")]

    def test_prefill_rejects_spans_that_straddle_paragraphs(self, tmp_path: Path):
        from benchmark.docx_gold import prefill_docx

        src = tmp_path / "in.docx"
        doc = Document()
        doc.add_paragraph("Acme")
        doc.add_paragraph("SA")
        doc.save(str(src))
        text = DocxAdapter.read(src).text  # "Acme\n\nSA"
        with pytest.raises(ValueError, match="paragraph"):
            prefill_docx(src, tmp_path / "out.docx", [PredSpan(0, len(text), "ORG", text)])


# ---------------------------------------------------------------------------
# Negative-class metric honours explicit public spans
# ---------------------------------------------------------------------------


class TestExplicitPublicSpans:
    def test_public_mentions_include_reviewer_marked_spans(self):
        from benchmark.negative import public_mentions

        # "Tribunal de l'entreprise" is not in the bundled whitelist; the
        # reviewer marked it grey, so it must count as a public mention.
        text = "Acme SA sued before the Tribunal de l'entreprise francophone de Bruxelles."
        gold = [_span(text, "Acme SA", "ORG")]
        explicit = [_span(text, "Tribunal de l'entreprise francophone de Bruxelles", "PUBLIC")]
        mentions = public_mentions(text, gold, explicit=explicit)
        assert [m.text for m in mentions] == ["Tribunal de l'entreprise francophone de Bruxelles"]
