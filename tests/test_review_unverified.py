"""The unverified-term report (docs/towards-recall-one.md, lever 3).

After redaction, everything capitalised or identifier-shaped that was
neither redacted nor whitelisted is listed, in context, for one
confirmation pass. The detectors find what they can; this report shows
the lawyer exactly what they did not decide. It is fail-closed by
design: noise is acceptable, a silent miss is not.
"""

from __future__ import annotations

from benchmark.schema import PredSpan


def _span(text: str, needle: str, typ: str = "ORG") -> PredSpan:
    i = text.index(needle)
    return PredSpan(start=i, end=i + len(needle), type=typ, text=needle)


def _terms(text: str, dets=()):  # noqa: ANN001
    from jude.review import unverified_terms

    out = unverified_terms(text, dets)
    for t in out:
        for s, e in t.occurrences:
            assert text[s:e].lower() == t.text.lower() or text[s:e].rstrip("'’s") == t.text
    return out


class TestUnverifiedTerms:
    def test_undetected_capitalised_name_is_listed_with_context_and_count(self):
        import re

        text = ("Acme Solutions SA engaged Northbridge to advise. The report by Northbridge "
                "was delivered to Acme Solutions SA.")
        dets = [PredSpan(m.start(), m.end(), "ORG", m.group())
                for m in re.finditer("Acme Solutions SA", text)]
        terms = _terms(text, dets)
        names = {t.text: t for t in terms}
        assert "Northbridge" in names
        assert names["Northbridge"].count == 2
        assert "Northbridge" in names["Northbridge"].context
        assert "Acme Solutions SA" not in names

    def test_detected_spans_are_excluded_including_partial_overlap(self):
        text = "Counsel Sophie Martin of Lumen Reality SARL attended."
        dets = [_span(text, "Sophie Martin", "PERSON"), _span(text, "Lumen Reality", "ORG")]
        # 'SARL' hangs off the detected span; still part of a redacted name.
        assert [t.text for t in _terms(text, dets)] == []

    def test_sentence_initial_common_words_are_skipped(self):
        text = ("The parties agree. Pursuant to Article 5, the Buyer shall pay. "
                "Notwithstanding the above, Completion occurs on the Closing Date.")
        assert _terms(text) == []

    def test_sentence_initial_name_that_recurs_mid_sentence_is_listed(self):
        text = "Helios argues infringement. The court asked Helios to reply."
        terms = _terms(text)
        assert [(t.text, t.count) for t in terms] == [("Helios", 2)]

    def test_public_bodies_and_statutes_are_skipped(self):
        text = ("The European Commission, the Bundeskartellamt and the Digital Markets Act "
                "are cited; Article 102 TFEU applies in Belgium.")
        assert _terms(text) == []

    def test_identifier_shaped_tokens_are_listed(self):
        text = "Our ref. HIP-NOTUSE-2026-0098; see also IPR2025-00712 and docket B6-127/26."
        names = [t.text for t in _terms(text)]
        for ident in ("HIP-NOTUSE-2026-0098", "IPR2025-00712", "B6-127/26"):
            assert ident in names, names

    def test_multi_token_phrases_with_connectors(self):
        text = "Financing from Banque de Luxembourg and Reinhart Voss & Klein was arranged."
        names = [t.text for t in _terms(text)]
        assert "Banque de Luxembourg" in names
        assert "Reinhart Voss & Klein" in names

    def test_possessive_and_trailing_punctuation_are_stripped(self):
        text = "We reviewed Northbridge's accounts (Northbridge)."
        terms = _terms(text)
        assert [(t.text, t.count) for t in terms] == [("Northbridge", 2)]

    def test_months_currencies_and_section_words_are_noise(self):
        text = "On 12 March 2026 the fee of EUR 40,000 under Clause 7 and Annex B was paid in Q2."
        assert _terms(text) == []

    def test_bare_domains_are_listed_even_though_lowercase(self):
        text = "Orders are placed online via pinegrove-coffee.example.com. Nothing else."
        assert [t.text for t in _terms(text)] == ["pinegrove-coffee.example.com"]

    def test_accepts_detection_objects(self):
        from jude.types import Detection, DetectionSource, EntityType

        text = "Meridian Media GmbH and Zeta NV met."
        d = Detection(text="Meridian Media GmbH", start=0, end=19, entity_type=EntityType.ORG,
                      source=DetectionSource.PATTERN, confidence=0.95)
        assert [t.text for t in _terms(text, [d])] == ["Zeta NV"]


class TestBenchmarkReviewMetric:
    def test_rescore_reports_misses_surfaced_by_the_review(self):
        from benchmark.evaluate import score_corpus
        from benchmark.run import rescore
        from benchmark.schema import GoldDocument, GoldSpan

        text = "Acme SA engaged Northbridge; Northbridge advised the Commission."

        class Runner:
            name = "stub"

            def predict(self, t):
                return [_span(t, "Acme SA")]

        gold = GoldDocument(
            id="d1", title="t", language="en", text=text,
            gold_spans=(
                GoldSpan(*_span(text, "Acme SA").__dict__.values()),
                GoldSpan(*_span(text, "Northbridge").__dict__.values()),
            ),
        )
        report = score_corpus(Runner(), [gold])
        report.meta["span_level"] = True
        rescored = rescore(report, [gold])
        rv = rescored.meta["review"]
        assert rv["misses"] == 1
        assert rv["misses_surfaced"] == 1
        assert rv["items"] >= 1
