# Annotation-policy questions raised by the synthetic batch (doc_021–035)

Fifteen drafting agents, one document each, all passing the
programmatic bar. Each was asked to flag anything the annotation policy
does not settle. The same six questions came back from most of them.
They need a lawyer's ruling — the corpus, the whitelist and the
detector will follow it. Current defaults are marked ⟶.

## Rulings (Etienne Perrin, 2026-10-13) — applied to the corpus

| # | Question | Ruling | Applied |
|---|---|---|---|
| 1 | Deal codenames | **Not redacted** — but a per-matter option to redact them is wanted as a feature | Removed from gold in all 25 held-out specs (kept in a `codenames` field for that option) and from doc_007 (`Helios`) |
| 2 | Published vs live case references | **Published citations are public**; live / internal references are redacted | Already the batch convention; every CASE_REF in the original 19 documents is a live or internal reference — no change |
| 3 | Company registration numbers | **Redact** (not useful for the legal analysis) | As is — typed IBAN (identifier bucket) |
| 4 | Officials acting in a public capacity | **Redact** | As is — typed PERSON |
| 5 | Honorifics | **Keep** the convention (excluded before a full name, included with a bare surname) | As is |
| 6 | Cities | **Keep city names** — a bare city is never redacted; a party's street-address line still is | 47 bare-city LOC spans removed from the held-out specs, 37 from the original documents; address lines untouched |
| 7 | Invoice numbers; WhatsApp group names | **Redact invoice numbers**; group names are not identifiers | Four `F26-…` invoice numbers added to doc_043 (CASE_REF); `Belting Amigos BNL` removed from doc_040 |

The detector follows rulings 1 and 6 since v0.8.1: bare city and
country names are never predicted (a LOC span survives only with a
number, a street word or a venue word), codename phrases and words are
dropped unless the matter opts in (`Matter.redact_codenames`: UI
checkbox under *Change mode*, CLI `jude matter create
--redact-codenames`), in which case "Project X" and every bare "X" are
redacted deterministically. Ruling 2 (published-citation shapes left
alone) is not yet implemented in the detector: a `C-nnn/nn` citation
is still redacted — fail-closed, counted as a false positive.

## 1. Deal codenames — identifier or not?

`Project Ganymede`, `Projet Héron`, `Project Corvus`, `Project Lantern`,
`Project Sable`, `Projet Argus`, `Project Corvid`… and their bare forms.
The original corpus is inconsistent: `Helios` (doc_007) is gold, `Project
Aurora` (doc_001), `Project Lighthouse` (doc_014), `GINKGO` (doc_016)
are not. Jude's neural filter currently drops bare codename words
(`_CODENAME_WORDS` in `spacy_detector.py`).

Argument for redacting: a codename is chosen precisely so that the deal
cannot be identified from documents; leaking it links every document
that carries it, and inside the firm it maps one-to-one to the parties.
Argument against: on its own it identifies nobody, and it makes the
document more readable for the LLM.

⟶ **Batch default: redact, typed ORG** (all fifteen specs normalised to
ORG; three agents had chosen CASE_REF). If the ruling is "do not
redact", the entities are removed from the specs and the corpus rebuilt
in one command.

## 2. Published case references vs. live ones

`Case C-403/19` (doc_004) is gold CASE_REF; `C-746/21 P` (Altice,
doc_028), `C-311/18` (Schrems II, doc_030), `C-413/14 P` (doc_026) are
public. A *published* judgment identifies a decision, not the client; a
*pending* or *internal* reference (`A/26/02371`, `HV-2026-0417`,
`M.12384` before notification) identifies a matter.

⟶ **Batch default: published citation = public; live/internal reference
= CASE_REF.** doc_004 should be re-annotated to match when reviewed.

## 3. Company registration numbers

KBO/BCE `0712.445.303`, `HRB 71244`, Companies House `14886231`, KvK
`87214903`. They re-identify an anonymised company through a public
register, so they must be redacted; the schema has no registry type.

⟶ **Batch default: typed IBAN** (the "account / registry number" bucket,
as VAT, SIREN and the Belgian national-register number already are).
A future schema can add `REGISTRY_ID`; a dedicated model should have it.

## 4. Officials acting in a public capacity

The BMA *auditeur* (doc_026), a Commission case handler, a judge. The
institution is public; is the named official an identifier? Naming the
case team can identify the case to an insider; it identifies no client.

⟶ **Batch default: redact (PERSON)** — conservative. A dedicated model
should carry `official_in_public_capacity` as a separate label so the
policy can be flipped without re-annotating.

## 5. Honorifics

All fifteen followed the original corpus: honorific *excluded* from a
full name (`Laurent Vandenbroucke`, not `M. Laurent Vandenbroucke`),
*included* when only the surname follows (`Mme Deprez`, `Mr. Tan`).
Lenient matching makes either choice score the same; the convention
matters for the review protocol.

⟶ **Keep.** Written into the protocol page.

## 6. Cities: the firm's seat vs. the court's seat

`Brussels` is the seat of the law firm (identifier), of the Commission
(public) and of the court (`tribunal de l'entreprise francophone de
Bruxelles`). Agents handled it by annotating the firm's address as one
span (`Avenue des Arts 46, 1000 Brussels`) and never the bare city, or
by seating parties outside Brussels. A bare-city span would swallow
the court's name at gold-build time (gold wins over public on overlap).

⟶ **Batch default: a party's city is gold only as part of its address
line; bare city names are left to the reviewer.** Worth a ruling:
"city of a party = LOC everywhere" (as doc_001 `Brussels`) would be
simpler for the detector but conflicts with public seats.

## 7. Invoice numbers, WhatsApp group names, initials (batch 2)

`F26-1183` in a mise en demeure (doc_043) is left public by its
drafter; it identifies a precise commercial relationship once combined
with the parties. A WhatsApp group name (`Belting Amigos BNL`,
doc_040) is typed ORG like a codename; a contact-label initial (`KH`)
is typed PERSON.

⟶ **Batch default: invoice numbers not redacted; group names ORG;
initials PERSON.** Worth a ruling on invoice and order numbers: in an
insolvency or a payment dispute they are the identifiers.

## Questions raised by the public split (doc_101–114, 15 October 2026)

Fourteen excerpts of real judgments and decisions, each annotated blind
by two agents and adjudicated by a third (`benchmark/public/README.md`).
The two annotators agreed on what is gold in almost every document; the
questions below are the points where the written policy is silent and
the adjudicator applied a default. Each needs a one-line ruling; the
default applied in the corpus is marked ⟶.

| # | Question | Where | Default applied ⟶ |
|---|---|---|---|
| 8 | **Non-party private companies named in the facts** — a contractor, customer, distributor, parent or counterparty that is not a party (TSK, Farlin, Accredo/CVS, AEI Ventures, Live Ventures). The policy enumerates "the parties" only. | doc_101, 104, 105, 106, 107 | Gold ORG — a named private company in a confidential file identifies the matter; flips 8 of 46 spans in doc_101 alone |
| 9 | **Earlier decisions in the client's own proceedings** — the judgment below (`[2025] EWHC 1569 (Ch)`), the earlier appeal (`2024 WL 1364345`): published, so public under ruling 2, yet one lookup re-identifies the parties. | doc_105, 108 | Gold CASE_REF — a carve-out to ruling 2 for the same matter's prior decisions |
| 10 | **The document's own published citation** — its ECLI or neutral citation (`ECLI:BE:CASS:2023:ARR.20230223.1F.3`, `[2026] EWHC 2587 (Comm)`). Public once published, but it *is* the matter's reference. | all | Gold CASE_REF, "as if live" |
| 11 | **A party's brands, products and titles** (`Remodulin`, `CADD-MS 3`, `La Libre`, `LN24`, `FUN Radio` …) — one-to-one with the party. Ruling wanted on identifier-or-not and on the type (ORG today; a `PRODUCT` label in a dedicated schema?). A licensed third-party mark operated by a party (`FUN Radio`) needs the same ruling. | doc_106, 112 | Gold ORG (word-mark precedent `MERIDIAAN`, doc_031) |
| 12 | **Counsel's address line** (`Bruxelles, rue de la Régence, 4`, `avenue Louise, 250`, `Rue Joseph Stevens 7`) — ruling 6 speaks of a *party's* street-address line. | doc_109, 110, 112 | Gold LOC, like a party's |
| 13 | **Public-law parties** — the State acting through its tax administration (`État belge`) vs a small municipality (`Ville de Virton`). | doc_110, 111 | State public, municipality gold — the test is whether the name identifies the matter |
| 14 | **IP registration numbers** — a patent number and its short form (`6,000,608`, `’608`): redacted under ruling 3 by analogy, but in a patent case the number may be needed for the analysis. | doc_108 | Gold, IBAN bucket (registry numbers) |
| 15 | **Commercial order numbers** (`work order no. 535958`) — ruling 7 covers invoice numbers only. | doc_102 | Gold CASE_REF, like invoice numbers |
| 16 | **The authority's own contact identifiers** — the Autorité belge de la concurrence's switchboard, BCE number, e-mail and website in its letterhead. The policy exempts "the court or authority itself and its address"; PHONE / IBAN / EMAIL / URL are otherwise unconditional buckets. | doc_114 (precedent doc_026) | Public — institutional coordinates identify no client |
| 17 | **Smaller shapes** — (a) a comma-appositive legal form glued to the name (`INTERNATIONAL TOOLS SERVICE, société anonyme`): inside the ORG span or a public generic term? left unannotated; (b) a third-party landmark locating a party's premises (`Immingham oil terminal`, venue → gold) next to bare places that identify it just as well (`North Killingholme`, public under ruling 6); (c) beneficial-owner family names that are neither parties nor officials (`Hurbain`, `le Hodey`) → gold PERSON; (d) the contested act's own numbering (`décision n° 8`) → public; (e) a real platform named as a business descriptor (`a YouTube channel`) → public. | doc_109, 103, 112, 113, 104 | As stated |

## Smaller points

* Span counts run 42–71 per document, above the 15–30 aim, because the
  policy is *every occurrence* and pleadings repeat party names. Fine
  for scoring (micro-average); the distinct-surface count is 30–46.
* Postcodes alone are not identifiers (all agents). Data-room index
  numbers are not identifiers.
* Real banks kept as gold (KBC, BCEE — whitelist `redact: true`), real
  public bodies kept public (SOGEPA, SPI, National Bank of Belgium).
* The trademark word mark `MERIDIAAN` (doc_031) typed ORG.
