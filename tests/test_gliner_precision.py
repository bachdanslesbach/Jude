"""Precision of the GLiNER layer once long documents are chunked.

Chunking exposed two gaps the old silent truncation had hidden: on a
short window GLiNER labels generic role phrases ("the Firm", "our
client", "Counsel for the Claimant") as organisations, and the GLiNER
detector — unlike the spaCy one — applied no shape filter at all. The
fixes: balanced windows (no tiny tail chunk), the same span normaliser
for GLiNER's PERSON / ORG / LOC output, a longer stop-list, and a few
public-knowledge entries (jurisdictions, courts, prosecutors).
"""

from __future__ import annotations

import math

from jude.types import EntityType


# ---------------------------------------------------------------------------
# Balanced chunks
# ---------------------------------------------------------------------------


class TestBalancedChunks:
    def test_no_tiny_tail_chunk(self):
        from jude.detect.chunking import chunk_text

        # 11 paragraphs × 25 words = 275 words. Greedy filling gives
        # [200, 75]; balanced filling gives two chunks of ~138.
        para = " ".join(f"w{i}" for i in range(25))
        text = "\n\n".join(para for _ in range(11))
        chunks = chunk_text(text, max_words=200)
        sizes = [len(c.split()) for _, c in chunks]
        assert len(sizes) == 2
        assert all(100 <= s <= 200 for s in sizes), sizes
        assert sum(sizes) == 275

    def test_balanced_over_many_chunks(self):
        from jude.detect.chunking import chunk_text

        para = " ".join(f"w{i}" for i in range(20))
        text = "\n\n".join(para for _ in range(50))  # 1000 words
        chunks = chunk_text(text, max_words=200)
        sizes = [len(c.split()) for _, c in chunks]
        assert len(sizes) == math.ceil(1000 / 200)
        assert max(sizes) <= 200
        assert min(sizes) >= 160, sizes
        for off, chunk in chunks:
            assert text[off:off + len(chunk)] == chunk

    def test_short_text_untouched(self):
        from jude.detect.chunking import chunk_text

        assert chunk_text("a b c", max_words=200) == [(0, "a b c")]


# ---------------------------------------------------------------------------
# Shape filter on GLiNER output
# ---------------------------------------------------------------------------


class _FakeGliner:
    """Returns whatever spans the test wants, with GLiNER's dict shape."""

    def __init__(self, spans: list[tuple[str, str]]):
        self._spans = spans  # (surface, label)

    def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
        out = []
        for surface, label in self._spans:
            i = text.find(surface)
            if i >= 0:
                out.append({"text": surface, "label": label, "start": i,
                            "end": i + len(surface), "score": 0.9})
        return out


def _detector(spans):  # noqa: ANN001
    from jude.detect.gliner_detector import GlinerDetector

    return GlinerDetector(model=_FakeGliner(spans))


class TestGlinerShapeFilter:
    def test_role_phrases_are_dropped_real_names_kept(self):
        text = ("The Firm will advise the Client. Counsel for the Claimant is "
                "Sophie Martin of Acme Solutions SA; our client is grateful. "
                "The undersigned confirms. General Counsel attended.")
        dets = _detector([
            ("The Firm", "company"), ("the Client", "client"),
            ("Counsel for the Claimant", "law firm"), ("Sophie Martin", "lawyer"),
            ("Acme Solutions SA", "company"), ("our client", "client"),
            ("The undersigned", "person"), ("General Counsel", "person"),
        ]).detect(text)
        assert sorted(d.text for d in dets) == ["Acme Solutions SA", "Sophie Martin"]
        for d in dets:
            assert text[d.start:d.end] == d.text

    def test_demonyms_and_generic_courts_are_dropped(self):
        text = "A Dutch company sued in the District Court; Escrow was released in Brussels."
        dets = _detector([
            ("Dutch", "country"), ("District Court", "court"),
            ("Escrow", "company"), ("Brussels", "city"),
        ]).detect(text)
        assert [d.text for d in dets] == ["Brussels"]

    def test_case_references_bypass_the_year_rule(self):
        # The spaCy normaliser rejects anything containing a year; that
        # rule must not eat GLiNER's case references.
        text = "Our ref. M-2026-PIO-001 concerns Acme SA."
        dets = _detector([("M-2026-PIO-001", "case reference"), ("Acme SA", "company")]).detect(text)
        assert {(d.entity_type, d.text) for d in dets} == {
            (EntityType.CASE_REF, "M-2026-PIO-001"), (EntityType.ORG, "Acme SA"),
        }

    def test_salutation_prefix_is_stripped_not_rejected(self):
        text = "Dear Sophie Martin, thank you."
        dets = _detector([("Dear Sophie Martin", "person")]).detect(text)
        assert [(d.text, text[d.start:d.end]) for d in dets] == [("Sophie Martin", "Sophie Martin")]


# ---------------------------------------------------------------------------
# Stop-list and public-knowledge additions
# ---------------------------------------------------------------------------


class TestStopListAdditions:
    def test_new_role_headers_rejected(self):
        from jude.detect.spacy_detector import _normalize_span

        for s in ("the Client", "our client", "Counsel for the Claimant", "Counsel for the Defendant",
                  "the undersigned", "Undersigned", "District Court", "the Court", "Escrow",
                  "the Claimant", "the Respondent", "Dutch", "French", "Belgian"):
            assert _normalize_span(s, 0, len(s), "en") is None, s

    def test_real_entities_still_pass(self):
        from jude.detect.spacy_detector import _normalize_span

        for s in ("Sophie Martin", "Acme Solutions SA", "Brussels", "Lumen Reality SARL",
                  "Commercial Court of London", "Dutch Bakery BV"):
            assert _normalize_span(s, 0, len(s), "en") is not None, s


class TestPublicKnowledgeAdditions:
    def test_jurisdictions_courts_prosecutors_are_public(self):
        from jude.public_knowledge import is_public_no_redact

        for s, t in (
            ("United States", EntityType.LOC), ("U.S.", EntityType.LOC), ("USA", EntityType.LOC),
            ("France", EntityType.LOC), ("Germany", EntityType.LOC), ("Italy", EntityType.LOC),
            ("Norway", EntityType.LOC), ("Spain", EntityType.LOC),
            ("Department of Justice", EntityType.ORG), ("DOJ", EntityType.ORG),
            ("Parquet National Financier", EntityType.ORG), ("PNF", EntityType.ORG),
            ("Commercial Court of London", EntityType.ORG),
            ("Eurostat", EntityType.ORG), ("Pillar Two", EntityType.ORG),
            ("United States District Court", EntityType.ORG),
            ("Data protection authority", EntityType.ORG), ("DPA", EntityType.ORG),
        ):
            assert is_public_no_redact(s, t), s

    def test_demonym_prefix_and_suffix_do_not_defeat_the_whitelist(self):
        from jude.public_knowledge import is_public_no_redact

        # Both were redacted by jude-full in the v0.7.8 benchmark run.
        assert is_public_no_redact("Autorité de la concurrence française", EntityType.ORG)
        assert is_public_no_redact("Belgian SPF Finances", EntityType.ORG)
        assert is_public_no_redact("the European Commission", EntityType.ORG)
        assert not is_public_no_redact("Belgian Brewers SA", EntityType.ORG)

    def test_bundle_still_parses_and_grew(self):
        from jude.context import _load_bundled

        recs = _load_bundled()
        assert len(recs) >= 197 + 10
        assert all("canonical" in r and "type" in r for r in recs)
