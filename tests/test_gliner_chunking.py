"""GLiNER's `predict_entities` tokenises with `truncation=True` at the
model's `max_len` (384 word-tokens for `gliner_large-v2.1`) and says
nothing about it. A two-page document loses its tail. Jude's detector
must chunk on paragraph boundaries and map offsets back.
"""

from __future__ import annotations

import pytest

from jude.types import EntityType


class TestChunkText:
    def test_short_text_is_one_chunk(self):
        from jude.detect.chunking import chunk_text

        assert chunk_text("Hello world", max_words=200) == [(0, "Hello world")]

    def test_splits_on_paragraph_boundary_when_budget_exceeded(self):
        from jude.detect.chunking import chunk_text

        assert chunk_text("a b c\n\nd e f", max_words=3) == [(0, "a b c"), (7, "d e f")]

    def test_oversized_paragraph_is_windowed(self):
        from jude.detect.chunking import chunk_text

        assert chunk_text("w1 w2 w3 w4 w5", max_words=2) == [(0, "w1 w2"), (6, "w3 w4"), (12, "w5")]

    def test_offsets_round_trip_and_no_word_is_lost(self):
        from jude.detect.chunking import chunk_text

        text = "Dear Ms Martin,\n\n" + " ".join(f"word{i}" for i in range(500)) + "\n\nRegards,\nAcme SA"
        chunks = chunk_text(text, max_words=120)
        assert len(chunks) >= 5
        for off, chunk in chunks:
            assert text[off:off + len(chunk)] == chunk
        assert sum(len(c.split()) for _, c in chunks) == len(text.split())


@pytest.fixture(scope="module")
def gliner_detector():
    pytest.importorskip("gliner")
    from jude.detect.gliner_detector import GlinerDetector

    return GlinerDetector()


_FILLER = (
    "The parties discussed the commercial terms of the proposed transaction at "
    "length, including the purchase price adjustment mechanism, the scope of the "
    "warranties, the conditions precedent to completion and the allocation of "
    "regulatory risk between signing and closing.\n\n"
)


def test_entity_past_the_384_word_limit_is_detected(gliner_detector):
    # ~40 words × 15 paragraphs = ~600 words of filler before the only entity.
    text = _FILLER * 15 + "Counsel for the buyer is Sophie Martin of Acme Solutions SA, Brussels."
    assert len(text.split()) > 384

    dets = gliner_detector.detect(text)
    persons = [d for d in dets if d.entity_type == EntityType.PERSON]
    assert any(d.text == "Sophie Martin" for d in persons), [d.text for d in dets]
    for d in dets:
        assert text[d.start:d.end] == d.text


def test_entity_before_the_limit_is_still_detected_once(gliner_detector):
    text = "Counsel for the buyer is Sophie Martin of Acme Solutions SA.\n\n" + _FILLER * 15
    dets = gliner_detector.detect(text)
    hits = [d for d in dets if d.text == "Sophie Martin" and d.entity_type == EntityType.PERSON]
    assert len(hits) == 1
    assert text[hits[0].start:hits[0].end] == "Sophie Martin"
