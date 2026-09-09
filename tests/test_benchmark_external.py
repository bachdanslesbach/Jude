"""Tests for the model-comparison additions to the benchmark harness.

Everything here is pure logic — no model is loaded. The external
runners are exercised through their label-mapping / span-conversion
helpers so the mapping policy (what counts, what is dropped as
out-of-schema) is pinned down in code rather than in prose.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from benchmark.schema import GoldSpan, PredSpan

# ---------------------------------------------------------------------------
# Negative-class metric: public bodies that must NOT be redacted
# ---------------------------------------------------------------------------


def _gold(text: str, needle: str, typ: str) -> GoldSpan:
    i = text.index(needle)
    return GoldSpan(start=i, end=i + len(needle), type=typ, text=needle)


def _pred(text: str, needle: str, typ: str) -> PredSpan:
    i = text.index(needle)
    return PredSpan(start=i, end=i + len(needle), type=typ, text=needle)


class TestPublicMentions:
    def test_finds_whitelisted_institution_not_in_gold(self):
        from benchmark.negative import public_mentions

        text = "The European Commission opened proceedings against Acme SA."
        gold = [_gold(text, "Acme SA", "ORG")]
        mentions = public_mentions(text, gold)
        assert [m.text for m in mentions] == ["European Commission"]

    def test_longest_alias_wins_no_nested_duplicates(self):
        from benchmark.negative import public_mentions

        # "Commission" alone is also a whitelist alias; it must not be
        # reported a second time inside "European Commission".
        text = "European Commission decision."
        mentions = public_mentions(text, [])
        assert len(mentions) == 1
        assert mentions[0].text == "European Commission"

    def test_mention_overlapping_gold_is_excluded(self):
        from benchmark.negative import public_mentions

        # Annotation policy in the corpus treats Luxembourg (as a place
        # of business) as redactable; the whitelist treats it as a
        # jurisdiction. Gold wins: not a negative-class mention.
        text = "Registered office in Luxembourg."
        gold = [_gold(text, "Luxembourg", "LOC")]
        assert public_mentions(text, gold) == []

    def test_demonyms_and_legal_form_suffixes_are_ignored(self):
        from benchmark.negative import public_mentions

        text = "Acme NV is a Belgian company; Zeta SE is Swiss."
        assert public_mentions(text, []) == []

    def test_short_acronyms_are_case_sensitive(self):
        from benchmark.negative import public_mentions

        # "dma" inside "Padma" or lowercase prose must not fire.
        text = "The dma team met Padma; the DMA applies."
        mentions = public_mentions(text, [])
        assert [m.text for m in mentions] == ["DMA"]


class TestOverRedaction:
    def test_counts_mentions_covered_by_predictions(self):
        from benchmark.negative import over_redaction, public_mentions

        text = "The European Commission fined Acme SA; the Bundeskartellamt agreed."
        gold = [_gold(text, "Acme SA", "ORG")]
        mentions = public_mentions(text, gold)
        assert len(mentions) == 2
        preds = [
            _pred(text, "European Commission", "ORG"),
            _pred(text, "Acme SA", "ORG"),
        ]
        hits, total = over_redaction(preds, mentions)
        assert (hits, total) == (1, 2)

    def test_partial_overlap_counts_as_hit(self):
        from benchmark.negative import over_redaction, public_mentions

        text = "Referred to DG Competition yesterday."
        mentions = public_mentions(text, [])
        assert [m.text for m in mentions] == ["DG Competition"]
        preds = [_pred(text, "Competition yesterday", "ORG")]
        assert over_redaction(preds, mentions) == (1, 1)


# ---------------------------------------------------------------------------
# pplx-pii-masking: label mapping and out-of-schema accounting
# ---------------------------------------------------------------------------


@dataclass
class _FakeSpan:
    start: int
    end: int
    label: str
    score: float = 0.9


class TestPplxMapping:
    def test_in_schema_labels_map_to_jude_types(self):
        from benchmark.runners.pplx_pii import PPLX_LABEL_MAP, convert_spans

        text = "Daniel Whitfield <daniels@meridiancap.com> +1 415 555 0123"
        spans = [
            _FakeSpan(0, 16, "private_person"),
            _FakeSpan(18, 41, "private_email"),
            _FakeSpan(43, 58, "private_phone"),
        ]
        preds, dropped = convert_spans(spans, text)
        assert [p.type for p in preds] == ["PERSON", "EMAIL", "PHONE"]
        assert preds[0].text == "Daniel Whitfield"
        assert dropped == {}
        assert PPLX_LABEL_MAP["account_number"] == "IBAN"
        assert PPLX_LABEL_MAP["private_url"] == "URL"
        assert PPLX_LABEL_MAP["private_address"] == "LOC"

    def test_out_of_schema_labels_are_dropped_and_counted(self):
        from benchmark.runners.pplx_pii import convert_spans

        text = "Signed 12 March 2026 by Daniel Whitfield"
        spans = [
            _FakeSpan(7, 20, "private_date"),
            _FakeSpan(24, 40, "private_person"),
            _FakeSpan(0, 6, "other_pii"),
        ]
        preds, dropped = convert_spans(spans, text)
        assert [p.type for p in preds] == ["PERSON"]
        assert dropped == {"private_date": 1, "other_pii": 1}


# ---------------------------------------------------------------------------
# nvidia/gliner-PII: native-label mapping
# ---------------------------------------------------------------------------


class TestNvidiaMapping:
    def test_native_labels_cover_all_jude_types_except_case_ref(self):
        from benchmark.runners.nvidia_gliner_pii import NATIVE_LABEL_MAP

        covered = set(NATIVE_LABEL_MAP.values())
        assert {"PERSON", "ORG", "LOC", "EMAIL", "PHONE", "IBAN", "URL"} <= covered
        assert "CASE_REF" not in covered  # no such label in Nemotron-PII

    def test_first_and_last_name_both_map_to_person(self):
        from benchmark.runners.nvidia_gliner_pii import NATIVE_LABEL_MAP

        assert NATIVE_LABEL_MAP["first_name"] == "PERSON"
        assert NATIVE_LABEL_MAP["last_name"] == "PERSON"
        assert NATIVE_LABEL_MAP["company_name"] == "ORG"

    def test_adjacent_same_type_spans_are_merged(self):
        from benchmark.runners.nvidia_gliner_pii import merge_adjacent

        # first_name + last_name come back as two spans separated by a
        # space; a fair comparison against a PERSON gold span merges them.
        text = "Daniel Whitfield signed."
        preds = [
            PredSpan(0, 6, "PERSON", "Daniel"),
            PredSpan(7, 16, "PERSON", "Whitfield"),
        ]
        merged = merge_adjacent(preds, text)
        assert len(merged) == 1
        assert (merged[0].start, merged[0].end, merged[0].text) == (0, 16, "Daniel Whitfield")

    def test_merge_does_not_cross_types_or_punctuation(self):
        from benchmark.runners.nvidia_gliner_pii import merge_adjacent

        text = "Acme SA, Brussels"
        preds = [
            PredSpan(0, 7, "ORG", "Acme SA"),
            PredSpan(9, 17, "LOC", "Brussels"),
        ]
        assert merge_adjacent(preds, text) == preds


class TestChunkText:
    def test_short_text_is_one_chunk(self):
        from benchmark.runners.nvidia_gliner_pii import chunk_text

        assert chunk_text("Hello world", max_words=200) == [(0, "Hello world")]

    def test_splits_on_paragraph_boundary_when_budget_exceeded(self):
        from benchmark.runners.nvidia_gliner_pii import chunk_text

        text = "a b c\n\nd e f"
        assert chunk_text(text, max_words=3) == [(0, "a b c"), (7, "d e f")]

    def test_oversized_paragraph_is_windowed(self):
        from benchmark.runners.nvidia_gliner_pii import chunk_text

        text = "w1 w2 w3 w4 w5"
        assert chunk_text(text, max_words=2) == [(0, "w1 w2"), (6, "w3 w4"), (12, "w5")]

    def test_offsets_round_trip(self):
        from benchmark.runners.nvidia_gliner_pii import chunk_text

        text = "Dear Ms Martin,\n\n" + " ".join(f"word{i}" for i in range(500)) + "\n\nRegards,\nAcme SA"
        chunks = chunk_text(text, max_words=120)
        assert len(chunks) >= 5
        for off, chunk in chunks:
            assert text[off:off + len(chunk)] == chunk
        # Every word of the text lands in exactly one chunk.
        assert sum(len(c.split()) for _, c in chunks) == len(text.split())


# ---------------------------------------------------------------------------
# Sentence-level evaluation (for message-level classifiers like Roblox)
# ---------------------------------------------------------------------------


class TestSentenceEval:
    def test_split_sentences_returns_offsets_covering_text(self):
        from benchmark.sentence_eval import split_sentences

        text = "Dear Ms Martin,\n\nWe act for Acme SA. Please call +32 2 555 0123.\nRegards"
        sents = split_sentences(text)
        assert all(text[s:e].strip() for s, e in sents)
        assert sents[0] == (0, 15)
        assert len(sents) >= 3

    def test_sentence_gold_labels_true_iff_overlaps_a_gold_span(self):
        from benchmark.sentence_eval import sentence_gold_labels

        text = "Acme SA appealed. The court adjourned. Call +32 2 555 0123."
        sents = [(0, 17), (18, 38), (39, 58)]
        gold = [_gold(text, "Acme SA", "ORG"), _gold(text, "+32 2 555 0123", "PHONE")]
        assert sentence_gold_labels(sents, gold) == [True, False, True]

    def test_score_sentences_precision_recall(self):
        from benchmark.sentence_eval import score_sentences

        s = score_sentences(pred=[True, False, False], gold=[True, False, True])
        assert (s.tp, s.fp, s.fn) == (1, 0, 1)
        assert s.precision == pytest.approx(1.0)
        assert s.recall == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Report serialisation (so runners can execute in separate processes)
# ---------------------------------------------------------------------------


class TestReportRoundTrip:
    def test_corpus_report_survives_json(self):
        from benchmark.evaluate import score_corpus
        from benchmark.schema import GoldDocument
        from benchmark.serialize import report_from_dict, report_to_dict

        class Runner:
            name = "stub"

            def predict(self, text):
                return [_pred(text, "Acme SA", "ORG")]

        text = "Acme SA sued Zeta NV."
        doc = GoldDocument(
            id="d1", title="t", language="en", text=text,
            gold_spans=(_gold(text, "Acme SA", "ORG"), _gold(text, "Zeta NV", "ORG")),
        )
        report = score_corpus(Runner(), [doc])
        report.meta = {"seconds": 1.5, "peak_rss_mb": 12.0}
        clone = report_from_dict(report_to_dict(report))
        assert clone.runner_name == "stub"
        assert clone.aggregate.f1 == pytest.approx(report.aggregate.f1)
        assert clone.aggregate.by_type["ORG"].fn == 1
        assert clone.per_doc[0].pred_spans == report.per_doc[0].pred_spans
        assert clone.meta == {"seconds": 1.5, "peak_rss_mb": 12.0}
