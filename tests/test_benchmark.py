"""TDD tests for the benchmark framework.

Specifies the API the implementation must provide:

  benchmark.schema.GoldSpan, GoldDocument
  benchmark.evaluate.score(pred_spans, gold_spans)  -> Score
  benchmark.evaluate.score_corpus(runner, corpus)   -> CorpusReport

Span-matching policy
--------------------

A predicted span counts as a true positive when it (a) overlaps a gold
span by at least one character AND (b) has the same `type`. This is
the "lenient overlap" policy commonly used in NER evaluation: it
forgives one-off boundary differences (e.g. predicting "Acme Solutions"
when gold is "Acme Solutions SA") while still penalising completely
unrelated predictions.

Each gold span matches at most one predicted span (greedy, longest-
overlap-first). A predicted span that doesn't match any gold is a
false positive; a gold span left unmatched is a false negative.
"""

from __future__ import annotations

import pytest


def _gs(start: int, end: int, type_: str = "ORG") -> "GoldSpan":  # noqa: F821
    from benchmark.schema import GoldSpan
    return GoldSpan(start=start, end=end, type=type_, text="x")


def _ps(start: int, end: int, type_: str = "ORG") -> "PredSpan":  # noqa: F821
    from benchmark.schema import PredSpan
    return PredSpan(start=start, end=end, type=type_, text="x")


# ---------- score() invariants ----------


def test_perfect_match_yields_f1_one():
    from benchmark.evaluate import score

    gold = [_gs(0, 5)]
    pred = [_ps(0, 5)]
    s = score(pred, gold)
    assert s.precision == 1.0
    assert s.recall == 1.0
    assert s.f1 == 1.0


def test_complete_miss_yields_f1_zero():
    from benchmark.evaluate import score

    gold = [_gs(0, 5)]
    pred: list = []
    s = score(pred, gold)
    assert s.precision == 0.0
    assert s.recall == 0.0
    assert s.f1 == 0.0


def test_only_false_positives_yields_zero_recall_zero_precision():
    from benchmark.evaluate import score

    gold: list = []
    pred = [_ps(0, 5)]
    s = score(pred, gold)
    # No gold → recall is undefined; convention here: 0.0 (we predicted
    # something we shouldn't have).
    assert s.precision == 0.0
    assert s.recall == 0.0
    assert s.f1 == 0.0


def test_partial_overlap_counts_as_match_under_lenient_policy():
    from benchmark.evaluate import score

    # gold says 'Acme Solutions SA' = chars 0-17; pred says 'Acme Solutions'
    # = chars 0-14. They overlap so this is a TP, not FP+FN.
    gold = [_gs(0, 17)]
    pred = [_ps(0, 14)]
    s = score(pred, gold)
    assert s.precision == 1.0
    assert s.recall == 1.0
    assert s.f1 == 1.0


def test_type_mismatch_does_not_count_as_match():
    from benchmark.evaluate import score

    gold = [_gs(0, 5, "ORG")]
    pred = [_ps(0, 5, "PERSON")]  # same span, wrong type
    s = score(pred, gold)
    assert s.precision == 0.0
    assert s.recall == 0.0
    assert s.f1 == 0.0


def test_one_gold_matches_at_most_one_pred():
    """If two predictions overlap the same gold span, only one is a TP;
    the other counts as a false positive."""

    from benchmark.evaluate import score

    gold = [_gs(0, 10)]
    pred = [_ps(0, 5), _ps(5, 10)]  # both overlap the single gold
    s = score(pred, gold)
    # 1 TP, 1 FP, 0 FN → P = 1/2, R = 1/1, F1 = 2/3
    assert s.precision == pytest.approx(0.5)
    assert s.recall == 1.0
    assert s.f1 == pytest.approx(2 / 3)


def test_per_type_breakdown():
    """The score also reports per-type precision/recall/F1 so we can see
    which entity types are the weakest."""

    from benchmark.evaluate import score

    gold = [_gs(0, 5, "ORG"), _gs(10, 15, "PERSON"), _gs(20, 25, "PERSON")]
    pred = [_ps(0, 5, "ORG"), _ps(10, 15, "PERSON")]  # ORG perfect; PERSON 1/2
    s = score(pred, gold)

    by = s.by_type
    assert by["ORG"].f1 == 1.0
    assert by["PERSON"].recall == pytest.approx(0.5)
    assert by["PERSON"].precision == 1.0


# ---------- corpus loader ----------


def test_load_gold_document_from_json(tmp_path):
    """Gold documents are JSON files with a fixed schema."""

    from benchmark.schema import GoldDocument

    p = tmp_path / "doc_001.json"
    p.write_text(
        '{"id":"doc_001","title":"t","language":"en","text":"Hello Acme.",'
        '"gold_spans":[{"start":6,"end":10,"type":"ORG","text":"Acme"}],'
        '"notes":"smoke"}',
        encoding="utf-8",
    )
    doc = GoldDocument.from_json(p)
    assert doc.id == "doc_001"
    assert doc.text == "Hello Acme."
    assert len(doc.gold_spans) == 1
    assert doc.gold_spans[0].start == 6
    assert doc.gold_spans[0].text == "Acme"


def test_runner_protocol_smoke():
    """Any runner is a callable taking text and returning a list of
    PredSpan. The base class exposes a `name` attribute used in reports."""

    from benchmark.runners import RunnerProtocol  # type: ignore[attr-defined]

    class FakeRunner:
        name = "fake"

        def predict(self, text: str):
            from benchmark.schema import PredSpan
            return [PredSpan(start=0, end=5, type="ORG", text="Hello")]

    r: RunnerProtocol = FakeRunner()  # type: ignore[assignment]
    out = r.predict("Hello there")
    assert out[0].text == "Hello"
