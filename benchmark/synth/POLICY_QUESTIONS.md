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

The detector follows rulings 1 and 6 in the next version (bare city
names and codenames are no longer predicted); the whitelist of
published-citation shapes follows ruling 2.

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

## Smaller points

* Span counts run 42–71 per document, above the 15–30 aim, because the
  policy is *every occurrence* and pleadings repeat party names. Fine
  for scoring (micro-average); the distinct-surface count is 30–46.
* Postcodes alone are not identifiers (all agents). Data-room index
  numbers are not identifiers.
* Real banks kept as gold (KBC, BCEE — whitelist `redact: true`), real
  public bodies kept public (SOGEPA, SPI, National Bank of Belgium).
* The trademark word mark `MERIDIAAN` (doc_031) typed ORG.
