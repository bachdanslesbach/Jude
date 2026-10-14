## The generalisation gap

The first version of this benchmark scored twenty documents on which
Jude's whitelist and stop-lists had been tuned. The `heldout` split —
twenty-five documents drafted later against a programmatic bar and a
judge, never consulted while tuning — is the number to quote:

Numbers below follow the annotation rulings of 13 October 2026
(`benchmark/synth/POLICY_QUESTIONS.md`): deal codenames and bare city
names are no longer identifiers, invoice numbers are. Jude's detector
follows rulings 1 and 6 since v0.8.1 (bare cities are never predicted,
codenames only when a matter opts in); every document was reviewed in
Word by a lawyer on the same day.

| System | dev F1 (P / R) | heldout F1 (P / R) | gap |
|---|---|---|---|
| `jude-full` | 0.952 (0.92 / 0.99) | **0.745** (0.64 / 0.89) | −0.21 |
| `jude-full-gliner-small` | 0.941 (0.90 / 0.98) | 0.732 (0.64 / 0.86) | −0.21 |
| `rules-only` | 0.836 (0.99 / 0.72) | 0.714 (0.95 / 0.57) | −0.12 |
| `nvidia-gliner-pii-native` | 0.662 (0.68 / 0.65) | 0.628 (0.64 / 0.62) | −0.03 |
| `gliner-large-v2.1-jude-labels` | 0.624 | 0.600 | −0.02 |
| `pplx-pii-masking` | 0.570 (0.89 / 0.42) | 0.632 (0.92 / 0.48) | +0.06 |
| `ollama-qwen3-4b` (generative, 4 B) | 0.694 (0.59 / 0.85) | 0.544 (0.50 / 0.60) | −0.15 |
| `roblox-pii-classifier` (sentence F1) | 0.764 | 0.751 | −0.01 |

Jude loses 21 points between the two splits; the generic models lose
three or gain some. That is the honest measure of how much of the dev
score was tuning. On the held-out set Jude's recall holds (0.89) while
its precision drops (0.92 → 0.64). The rules alone sit at precision
0.95 and recall 0.57 — three points of F1 behind. F1 is not the
lawyer's objective; recall is, and 0.89 against 0.57 is the whole case
for the neural layers. But the gap says what they cost: 32 points of
recall for 31 points of precision — the public sphere in French
practice, roles and bare short forms they do not yet know to leave
alone, as the taxonomy below shows. Every fix suggested by a held-out
failure is listed here and *not applied*; policy rulings are applied
immediately, to the corpus and to the detector, because a ruling is
not tuning.

## Failure taxonomy

Read off `python -m benchmark.analyze benchmark/results/*.json`; counts
are exact for this corpus.

### 1. Generic PII taxonomies have no word for half of what a legal document must hide

ORG and CASE_REF are 47 % of the gold spans. `pplx-pii-masking` has no
organisation label: ORG recall is **0.000** by construction, on both
splits; its overall recall is 0.44 and its precision 0.92 — it is a
careful model for the wrong task. NVIDIA's `company_name` reaches
ORG recall 0.47 with precision 0.85 — it misses short names, acronyms
and every codename. Neither has a case-reference label.

### 2. What Jude misses on the held-out split (recall 0.89)

142 misses in 1,627 gold spans, in five classes, each a handful of
lines to fix and each *left unfixed* for the next round:

* **Registry numbers** (28): KBO/BCE `0712.445.303`, `HRB 71244`,
  Companies House eight-digit numbers, an Italian VAT. IBAN precision
  is 1.00 and recall 0.43 on the held-out split — the regex layer
  simply has no pattern for them.
* **Reference formats it has not seen** (29): Belgian *numéro de rôle*
  `A/26/02371`, firm references of the shape `LH/2026/0583-TRV`, a
  pre-notification `M.12384`. CASE_REF recall 0.56 — the same lesson
  as v0.7.7, on new shapes.
* **Short forms** (25 ORG): `Valdoire`, `Ambreval`, `Tremonval`,
  `Zilverberg` — the full form was caught but not propagated to its
  bare short form. (Codenames are no longer gold under ruling 1.)
* **Surname-only repeats** (36 PERSON): `Herbiet` ×3, `Roelandts`,
  `Thonnard`, `Brankovic`, `Pasqualotto`, `Rombouts` — the reference a
  practitioner uses after first mention. The dictionary propagates
  full names; it must propagate surnames.
* **Postcode-and-city lines and venues** (24 LOC): `1040 Brussels`,
  `2000 Antwerp`, `London EC4A 1NL` on their own letterhead line
  (16 of the 24 — the address pattern wants a street; the normaliser
  keeps any LOC with a number, but nothing detects the line), and
  `Hotel Löwenkranz`, `Kastanjehof conference centre` (a venue named
  on its own).

### 3. What Jude over-redacts on the held-out split (precision 0.64)

With the detector following the rulings, LOC is nearly clean (8
spurious spans, precision 0.93). The 634 spurious spans that remain
are ORG (461) and PERSON (153) — the *negative* classes:

* **The public sphere in Belgian and French practice** — 30 % of the
  496 whitelisted mentions redacted: *Auditorat*, *Chambre
  contentieuse*, *Cour des marchés*, *ONSS*, *SPF Emploi*, *Conseil
  national du Travail*, *SETCa*, *loi du 3 juillet 1978*, *Cass.*,
  *Pas.* — a whitelist built on English competition practice meeting
  employment, data-protection and civil-procedure French. A list can
  be extended forever; a model with a `public_body` label learns the
  category.
* **Published citations typed as live case references** (13):
  `C-746/21 P`, `C-311/18`, `T-274/01`, *Hoffmann-La Roche 85/76*.
  The corpus policy (POLICY_QUESTIONS §2) says published = public; the
  regex says every `C-nnn/nn` is a case reference. A model needs the
  distinction as two labels.
* **Roles, defined terms and legal forms** (a large share of 427 ORG
  false positives): *l'Auditeur*, *auditeur général*, *siège des
  Parties*, *Naamloze vennootschap*, *Audit & Risk Committee*,
  *Creditors' Committee*, *Swiss parent*. The stop-list has sixty
  entries; the held-out documents used sixty others.
* **Type confusion on bare short forms** (ORG → PERSON 26, PERSON →
  ORG 20): a bare `Valdoire` or `Steinhauer` is a company in one
  document and a person in the next; without context the neural layer
  guesses. Lenient any-type F1 (0.78 vs 0.74) measures the cost.
* **Countries and regions as LOC** (part of 185 LOC false positives):
  *Pays-Bas*, *England and Wales*, *Afrique du Nord*, the Commission's
  own address. Jurisdictions are public; the whitelist knows twenty.

### 4. Address ≠ location; e-mails as names; the honorific-only reference

Unchanged from the first run and confirmed on the new documents:
`pplx`'s `private_address` catches full postal addresses and no bare
city (LOC recall 0.27); NVIDIA labels the local part of e-mail
addresses as first and last names (EMAIL recall 0.40, dozens of
spurious PERSON spans); `pplx` misses *Mr. Tan*-style references,
NVIDIA catches them.

### 5. A message classifier on legal prose

`roblox-pii-classifier` at sentence level: precision 0.97, recall 0.63
on the held-out split — it almost never flags a clean sentence and
misses a third of the sentences carrying an identifier.

### 6. A generative model as the extractor

`qwen3:4b` through Ollama, prompted to list every identifier as JSON
and told not to list institutions: F1 0.596 overall, 0.555 held out
(recall 0.58); **46 % of public-body mentions redacted** — the
instruction does not survive contact with a Belgian filing; 115 s per
page on the laptop; two documents returned invalid JSON and one timed
out twice. A hundred times the compute of the encoders for a result
below the rules alone. The generative route is a second reader at
most (see `efficiency-frontier.html`).

### 7. The review report as the last line

Of Jude's 142 held-out misses, the unverified-term report puts 50 in
front of the reviewer, at 22 items per document. The remaining 110 are
mostly numbers (registry and reference formats) and lower-case or
all-caps short forms the capitalisation heuristic does not see —
which is why the report's next version lists digit-bearing tokens
too.

## What Jude takes from this — for the next version, measured on the next batch

* Registry-number and *numéro de rôle* patterns; surname propagation
  in the dictionary; digit-bearing tokens in the review report.
* French public-sphere entries and the *published citation* rule in
  the whitelist — knowing that every such list is a stopgap the model
  should make redundant.
* A pattern for postcode-and-city lines (`1040 Brussels`, `London
  EC4A 1NL`) and for venues named on their own — 24 of the 142 misses.
* (Done in v0.8.1: rulings 1 and 6 in the detector, with the
  per-matter option to redact codenames.)
* GLiNER small as the laptop default is defensible: −3 recall points
  for 2.7× the speed inside the pipeline (see `efficiency-frontier.html`).

## What a legal-anonymisation model would need

For anyone minded to train one — the plan is in `training-data.html`:

1. **Labels that encode the legal distinction, not the PII one.**
   `party_organisation` *versus* `public_body`; `private_person`
   *versus* `official_in_public_capacity`; `case_reference_live`
   *versus* `case_reference_published`; `registry_number`;
   `party_address` *versus* `public_address`; `role` as an explicit
   negative. Every one of these is a class of held-out error above.
2. **Legal synthetic data, EN / FR first (then DE / NL), EU formats**,
   generated the way this corpus was — briefs, a programmatic bar, a
   judge, uniqueness across documents — at a scale of thousands.
3. **Long context or built-in chunking** with consistent decisions
   across chunks.
4. **Alias consistency**: *Herbiet* / *Thomas Herbiet* / *le
   directeur commercial* map to one pseudonym; a model that emits
   coreference makes the propagation cheap.
5. **Evaluation on the held-out split, never on the tuning split**,
   and a fresh batch for every round of fixes.

## Limitations of this benchmark

* Forty-four synthetic documents, one annotation policy whose seven
  open questions were ruled on 13 October 2026, every document
  reviewed in Word by a lawyer on the same day (no change required;
  see `annotation-protocol.html`). The numbers are indicative; the ranking and
  the size of the generalisation gap are robust.
* Where a mapping choice was ambiguous it was made in the external
  model's favour: dates and demographic labels are dropped rather than
  counted as false positives; adjacent name fragments are merged.
* Thresholds are the model cards' defaults; lowering NVIDIA's to 0.3
  changes little.
* Roblox's own card reports 45.5 % F1 on the Kaggle PII essay dataset;
  that number is not comparable to anything here and is not used.
