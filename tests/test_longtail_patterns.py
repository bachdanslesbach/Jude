"""Deterministic long-tail rules (docs/towards-recall-one.md, lever 1).

Every remaining miss on the corpus belongs to a class a rule can close:
a company named with its legal form, a short name defined in
parentheses, a person introduced by an honorific, a vessel, a bare
domain, a street address, a family name before 'family', a bank known
by its acronym. Rules are precise by construction; the whitelist still
filters public bodies afterwards.
"""

from __future__ import annotations

import pytest

from jude.types import EntityType


def _detect(text: str):
    from jude.detect.patterns import PatternDetector

    dets = PatternDetector().detect(text)
    for d in dets:
        assert text[d.start:d.end] == d.text, (d.text, text[d.start:d.end])
    return dets


def _of(dets, etype):  # noqa: ANN001
    return [d.text for d in dets if d.entity_type == etype]


class TestLegalFormSuffix:
    def test_common_suffixes(self):
        text = ("Between Acme Solutions SA, Lumen Reality SARL, Halcyon Industries Holdings Ltd, "
                "Pemberton Cross LLP, Helios Photonics Inc., Meridian Media GmbH, "
                "Halcyon Treasury Holdings BV and Reinhart Voss & Klein NV.")
        orgs = _of(_detect(text), EntityType.ORG)
        for name in ("Acme Solutions SA", "Lumen Reality SARL", "Halcyon Industries Holdings Ltd",
                     "Pemberton Cross LLP", "Helios Photonics Inc.", "Meridian Media GmbH",
                     "Halcyon Treasury Holdings BV", "Reinhart Voss & Klein NV"):
            assert name in orgs, name

    def test_leading_article_and_connectors(self):
        text = "The Banque de Luxembourg SA and Société Générale de Belgique SA signed."
        orgs = _of(_detect(text), EntityType.ORG)
        assert "Banque de Luxembourg SA" in orgs
        assert "Société Générale de Belgique SA" in orgs
        assert not any(o.startswith("The ") for o in orgs)

    def test_legal_form_used_as_a_noun_is_not_a_company(self):
        # 'a Belgian SA', 'a Luxembourg SA', 'the SA' — the form, not a name.
        text = "Pioneer is a Luxembourg SA; the Buyer is a Belgian NV; each SA must file."
        assert _of(_detect(text), EntityType.ORG) == []

    def test_dotted_and_multiword_forms(self):
        text = "Aurelia Shipping S.p.A., Nordic Wind A/S, Baltic Grain Sp. z o.o. and Tyne Ltd."
        orgs = _of(_detect(text), EntityType.ORG)
        for name in ("Aurelia Shipping S.p.A.", "Nordic Wind A/S", "Baltic Grain Sp. z o.o.", "Tyne Ltd"):
            assert name in orgs, orgs


class TestDefinedAlias:
    def test_short_name_in_parentheses_after_a_company(self):
        text = 'Plaintiff Helios Photonics Inc. ("Helios"), a Delaware corporation, sued.'
        dets = _detect(text)
        orgs = _of(dets, EntityType.ORG)
        assert "Helios Photonics Inc." in orgs
        assert "Helios" in orgs

    def test_alias_with_or_the_firm(self):
        text = 'Counsel: Reinhart Voss & Klein, Avenue Louise 250, 1050 Brussels ("RVK" or "the Firm")'
        assert "RVK" in _of(_detect(text), EntityType.ORG)

    def test_curly_quotes_and_acronyms(self):
        text = "Lumen Optical Systems Corp. (“LOS”) and MeridianMedia Holdings GmbH (\"MeridianMedia\")."
        orgs = _of(_detect(text), EntityType.ORG)
        assert "LOS" in orgs
        assert "MeridianMedia" in orgs

    def test_defined_terms_that_are_roles_are_not_aliases(self):
        text = ('Acme SA (the "Buyer") and Zeta NV ("Seller") entered into this agreement '
                '(the "Agreement") on the closing date ("Closing").')
        orgs = _of(_detect(text), EntityType.ORG)
        assert "Acme SA" in orgs and "Zeta NV" in orgs
        for role in ("Buyer", "Seller", "Agreement", "Closing"):
            assert role not in orgs, role

    def test_public_bodies_in_parentheses_are_left_to_the_whitelist(self):
        # Emitted or not, 'EU' must never survive the public-knowledge
        # filter; here we only require that it is not typed as ORG by the
        # rule when the phrase before it is a statute.
        text = "Regulation (EU) 2022/1925 and the Digital Markets Act (\"DMA\") apply."
        orgs = _of(_detect(text), EntityType.ORG)
        assert "EU" not in orgs


class TestHonorific:
    def test_honorific_plus_name_yields_the_name(self):
        text = "Mr. Tan confirmed; Maître Jan Peeters and Dr. Krishnamurthy agreed; Mme Dubois signed."
        persons = _of(_detect(text), EntityType.PERSON)
        for name in ("Tan", "Jan Peeters", "Krishnamurthy", "Dubois"):
            assert name in persons, persons

    def test_possessive_is_not_part_of_the_name(self):
        text = "Mr. Tan's evidence was clear."
        assert _of(_detect(text), EntityType.PERSON) == ["Tan"]

    def test_role_after_honorific_is_not_a_person(self):
        text = "Mr. President and Mr. Chairman opened the session."
        assert _of(_detect(text), EntityType.PERSON) == []


class TestVesselDomainFamily:
    def test_vessel(self):
        text = "the loss of the M/V Aurelia in the Bay of Biscay; the MV Northern Star was chartered."
        orgs = _of(_detect(text), EntityType.ORG)
        assert "M/V Aurelia" in orgs
        assert "MV Northern Star" in orgs

    def test_bare_domain(self):
        text = "online via your website pinegrove-coffee.example.com and www.acme-legal.be; see e.g. Art. 5."
        urls = _of(_detect(text), EntityType.URL)
        assert "pinegrove-coffee.example.com" in urls
        assert "www.acme-legal.be" in urls
        assert len(urls) == 2

    def test_domain_inside_an_email_is_not_a_separate_url(self):
        text = "Write to sophie.martin@example-law.eu today."
        assert _of(_detect(text), EntityType.URL) == []

    def test_family_name_before_family(self):
        text = "controlled by the Henkel-Vorwerk family trust and the Peeters family."
        persons = _of(_detect(text), EntityType.PERSON)
        assert "Henkel-Vorwerk" in persons
        assert "Peeters" in persons


class TestStreetAddress:
    def test_french_and_belgian_forms(self):
        text = "at 22 rue de Rivoli, 75001 Paris; Avenue Louise 250, 1050 Brussels; Boulevard du Régent 47, Bruxelles."
        locs = _of(_detect(text), EntityType.LOC)
        assert "22 rue de Rivoli" in locs
        assert "Avenue Louise 250" in locs
        assert "Boulevard du Régent 47" in locs

    def test_dutch_form(self):
        text = "registered office Strawinskylaan 3127, 1077 ZX Amsterdam; Keizersgracht 12A."
        locs = _of(_detect(text), EntityType.LOC)
        assert "Strawinskylaan 3127" in locs
        assert "Keizersgracht 12A" in locs

    def test_english_forms(self):
        text = "Pemberton Cross LLP, 10 Old Bailey, London EC4M 7NG; HQ at 14 Cornhill, London; 221B Baker Street."
        locs = _of(_detect(text), EntityType.LOC)
        for a in ("10 Old Bailey", "14 Cornhill", "221B Baker Street"):
            assert a in locs, locs

    def test_numbers_that_are_not_addresses(self):
        text = "within 5 Business Days, 3 Belgian companies, 2 Court hearings and 10 Old files."
        assert _of(_detect(text), EntityType.LOC) == []


class TestKnownEntities:
    def test_bundled_companies_and_banks_are_detected(self):
        from jude.detect.patterns import KnownEntityDetector

        text = "Initial capitalisation will route through BCEE; UBS and BNP Paribas will syndicate; Amazon objected."
        dets = KnownEntityDetector().detect(text)
        names = [d.text for d in dets]
        for n in ("BCEE", "UBS", "BNP Paribas", "Amazon"):
            assert n in names, names
        assert all(d.entity_type == EntityType.ORG for d in dets)

    def test_public_bodies_are_never_emitted(self):
        from jude.detect.patterns import KnownEntityDetector

        text = "The European Commission and the Bundeskartellamt reviewed the merger."
        assert KnownEntityDetector().detect(text) == []

    def test_short_acronyms_are_case_sensitive_and_word_bounded(self):
        from jude.detect.patterns import KnownEntityDetector

        text = "an apple a day; the ubs file; SUBSTANCE; Apple Inc. appealed."
        names = [d.text for d in KnownEntityDetector().detect(text)]
        assert "Apple" in names
        assert not any(n.lower() in ("apple a", "ubs") for n in names if n != "Apple")
        assert "SUBSTANCE" not in names


class TestPipelineIntegration:
    @pytest.fixture(scope="class")
    def pipeline(self):
        from jude.detect import DetectionPipeline
        from jude.store import Store
        from jude.types import Mode

        store = Store(":memory:")
        matter = store.create_matter("t", mode=Mode.STRICT)
        yield DetectionPipeline(store=store, matter_id=matter.id, use_gliner=False)
        store.close()

    def test_pattern_detections_reach_the_pipeline_and_win_overlaps(self, pipeline):  # noqa: ANN001
        text = ('Plaintiff Helios Photonics Inc. ("Helios") sued Lumen Optical Systems Corp. ("LOS"). '
                "Helios argues that LOS infringed. Capital routes through BCEE.")
        dets = pipeline.detect(text)
        by_text = {d.text: d for d in dets}
        for name in ("Helios Photonics Inc.", "Lumen Optical Systems Corp.", "LOS", "BCEE"):
            assert name in by_text, sorted(by_text)
        # The defined alias is found at its definition; the two-pass
        # dictionary propagates it to the bare mentions afterwards.
        assert sum(1 for d in dets if d.text == "Helios") >= 1
