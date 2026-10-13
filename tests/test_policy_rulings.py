"""The detector follows the annotation rulings of 13 October 2026.

Ruling 6 — a bare city or country name is never an identifier; a
party's street-address line is. Ruling 1 — deal codenames are not
redacted by default; a matter may opt in (`redact_codenames`), in
which case "Project X" is caught deterministically and its bare short
form follows through the dictionary.
"""

from __future__ import annotations

from jude.types import EntityType, Mode


def _norm(s: str, etype: EntityType, **kw):  # noqa: ANN003
    from jude.detect.spacy_detector import _normalize_span

    return _normalize_span(s, 0, len(s), "en", etype=etype, **kw)


class TestBareCities:
    def test_bare_city_and_country_names_are_dropped_for_loc(self):
        for s in ("Brussels", "Antwerp", "Paris", "Düsseldorf", "Luxembourg",
                  "Woluwe-Saint-Pierre", "Sint-Niklaas", "United States", "Bruxelles"):
            assert _norm(s, EntityType.LOC) is None, s

    def test_street_addresses_and_venues_are_kept(self):
        for s in ("Avenue Louise 250, 1050 Brussels", "22 rue de Rivoli", "Uitbreidingstraat 84",
                  "10 Old Bailey", "Hotel Löwenkranz", "Kastanjehof conference centre",
                  "Strawinskylaan 3127", "Place Madou 1"):
            assert _norm(s, EntityType.LOC) is not None, s

    def test_the_rule_is_loc_only(self):
        # A company called after a city, a person called Paris — not LOC, not touched.
        assert _norm("Brussels Airlines", EntityType.ORG) is not None
        assert _norm("Paris", EntityType.PERSON) is not None

    def test_gliner_no_longer_asks_for_cities_or_countries(self):
        from jude.detect.gliner_detector import GlinerDetector

        class _Fake:
            def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
                return []

        labels = GlinerDetector(model=_Fake()).labels
        assert "city" not in labels and "country" not in labels
        assert "address" in labels


class TestCodenames:
    def test_project_phrase_dropped_by_default_kept_when_opted_in(self):
        for s in ("Project Ganymede", "Projet Héron", "PROJECT CORVUS", "projet Sarment"):
            assert _norm(s, EntityType.ORG) is None, s
            assert _norm(s, EntityType.ORG, redact_codenames=True) is not None, s

    def test_gliner_codename_label_is_opt_in(self):
        from jude.detect.gliner_detector import GlinerDetector

        class _Fake:
            def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
                return []

        assert "deal codename" not in GlinerDetector(model=_Fake()).labels
        assert "deal codename" in GlinerDetector(model=_Fake(), redact_codenames=True).labels

    def test_pattern_detector_catches_project_phrase_only_when_opted_in(self):
        from jude.detect.patterns import PatternDetector

        text = "Project Ganymede closes in Q4; Ganymede is on track."
        default = [d for d in PatternDetector().detect(text) if "Ganymede" in d.text]
        assert default == []
        opted = PatternDetector(redact_codenames=True).detect(text)
        phrases = [(d.text, d.entity_type) for d in opted if "Ganymede" in d.text]
        assert ("Project Ganymede", EntityType.ORG) in phrases


class TestMatterOption:
    def test_store_persists_redact_codenames(self):
        from jude.store import Store

        store = Store(":memory:")
        try:
            m = store.create_matter("t", mode=Mode.STRICT)
            assert store.get_matter(m.id).redact_codenames is False
            store.set_redact_codenames(m.id, True)
            assert store.get_matter(m.id).redact_codenames is True
            m2 = store.create_matter("u", mode=Mode.STRICT, redact_codenames=True)
            assert store.get_matter(m2.id).redact_codenames is True
            assert [x.redact_codenames for x in store.list_matters()] == [False, True] or \
                   sorted(x.redact_codenames for x in store.list_matters()) == [False, True]
        finally:
            store.close()

    def test_pipeline_reads_the_option_from_the_matter(self, monkeypatch):
        import jude.detect.gliner_detector as gd
        from jude.detect import DetectionPipeline
        from jude.store import Store

        class _Fake:
            def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
                return []

        monkeypatch.setattr(gd, "_load", lambda name: _Fake())
        store = Store(":memory:")
        try:
            off = store.create_matter("off", mode=Mode.STRICT)
            on = store.create_matter("on", mode=Mode.STRICT, redact_codenames=True)
            p_off = DetectionPipeline(store=store, matter_id=off.id, use_gliner=True)
            p_on = DetectionPipeline(store=store, matter_id=on.id, use_gliner=True)
            assert p_off.redact_codenames is False and p_on.redact_codenames is True
            assert "deal codename" not in p_off.gliner.labels
            assert "deal codename" in p_on.gliner.labels
            text = "Project Ganymede closes in Q4."
            assert not [d for d in p_off.patterns.detect(text) if d.text == "Project Ganymede"]
            assert [d for d in p_on.patterns.detect(text) if d.text == "Project Ganymede"]
        finally:
            store.close()

    def test_bare_short_form_follows_the_phrase_when_opted_in(self, monkeypatch):
        """Once 'Project Ganymede' is an entity, a later bare 'Ganymede'
        must get the same pseudonym (dictionary alias)."""

        import jude.detect.gliner_detector as gd
        from jude.detect import DetectionPipeline
        from jude.redact import redact_two_pass
        from jude.store import Store

        class _Fake:
            def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
                return []

        monkeypatch.setattr(gd, "_load", lambda name: _Fake())
        store = Store(":memory:")
        try:
            m = store.create_matter("on", mode=Mode.STRICT, redact_codenames=True)
            pipeline = DetectionPipeline(store=store, matter_id=m.id, use_gliner=True)
            text = "Project Ganymede closes in Q4. Ganymede is on track."
            result = redact_two_pass(text, pipeline, store, m.id, Mode.STRICT)
            assert "Ganymede" not in result.redacted_text
            assert result.redacted_text.count("Org1") == 2
        finally:
            store.close()
