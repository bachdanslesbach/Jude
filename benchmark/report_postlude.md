## Failure taxonomy

Everything below is read off `python -m benchmark.analyze
benchmark/results/*.json`; the counts are exact for this corpus.

### 1. Generic PII taxonomies have no word for half of what a legal document must hide

ORG (172 spans) and CASE_REF (18) together are 190 of the 400 gold
spans — 48 %. `pplx-pii-masking` has no organisation label: ORG recall
is **0.000** by construction. NVIDIA's `company_name` fires on 54 % of
ORG spans — with perfect precision when it does — and misses the rest:
short names (`UBS`, `BIL`, `BNP Paribas`), trading names
(`TotalEnergies` without its `SE`), codenames (`Helios`, `Northbridge`),
a bank named only by acronym (`BCEE`). Neither system has a notion of a
case reference; `pplx` files 7 of the 18 under `account_number`.

Seven of the twenty documents score below 0.5 for `pplx`; the
antitrust complaint, the regulatory submission and the expert-economist
report — the documents densest in company names — are the worst
(0.474, 0.323, 0.261).

### 2. Address ≠ location

`private_address` catches full postal addresses and nothing else
(precision 1.000, LOC recall **0.268**). *Brussels*, *Paris*, *Munich*,
*Hamburg* are not PII to `pplx`. For a lawyer, the city of a party's
registered office is often the strongest quasi-identifier in the file —
the seat of the only listed brewer in a small country is the brewer.

### 3. E-mail addresses read as names

NVIDIA's model labels the local part of an e-mail address as
`first_name` / `last_name` — *sophie*, *martin*, *chen*, *hartmann* — so
22 of 30 e-mails are lost (EMAIL recall 0.267) and 38 spurious PERSON
spans appear. Its type-agnostic F1 (0.812 against 0.724 strict) shows
that a third of its gap is label confusion, not blindness. `pplx` has
the mirror problem: five phone numbers were fused into the preceding
e-mail span (`sophie.martin@example-law.eu, +33 1 44 55 66 77` as one
`private_email`).

### 4. Over-redaction of the public sphere

Share of the 117 public-body mentions redacted: base GLiNER **55 %**,
NVIDIA with Jude's labels 41 %, NVIDIA native 22 %, Jude without its
whitelist 81 %, Jude 3 %, `pplx` 3 %. NVIDIA's native run classifies
*Bundeskartellamt* as an identification number three times and redacts
*UK*, *Cayman*, *Ireland*, *Luxembourg* as countries. `pplx`'s 3 % is
the flip side of §1–2: it barely redacts places or organisations at
all, public or private. Jude's three residual hits are whitelisted
words swallowed by a longer span (*Delaware* inside `THE DISTRICT OF
DELAWARE`, *OECD* inside a guideline title) and one US state.

### 5. The honorific-only reference

*Mr. Tan* — the way a witness is referred to after first mention —
appears five times in the witness statement; `pplx` misses all five.
NVIDIA catches every one (PERSON recall 0.989, its best number).

### 6. A message classifier on legal prose

`roblox-pii-classifier` at sentence level: precision 0.968, recall
0.631. It almost never flags a clean sentence and misses 37 % of the
sentences that carry an identifier — "Pioneer Industries SA (the
Borrower) has drawn EUR 40 m" is not *giving PII* in the chat sense it
was trained on. Relatedly, `pplx`'s document-sensitivity head averages
0.11 across documents every one of which is confidential.

### 7. PII fine-tuning transfers — and shows where the ceiling is

Same checkpoint family, same labels, same threshold, same windows:
NVIDIA's fine-tune against the base GLiNER on Jude's legal labels moves
PERSON 0.810 → 0.874, CASE_REF 0.560 → 0.759, ORG 0.687 → 0.703, and
public-body over-redaction 55 % → 41 %. Synthetic-PII training helps on
legal text it never saw. It also says what is missing: not architecture, but
*legal* training data and a label set with parties and public bodies
as first-class, opposite categories.

### 8. Cost

All three external models run at 2.3–2.9 k chars/s on an M2 laptop
(MPS): a twenty-page brief in about twenty seconds. `pplx` is the
lightest to deploy (749 MB resident, bf16, MIT). Jude's shipped stack
is six times slower (426 chars/s: transformer spaCy and GLiNER on CPU,
two passes, windowed) and nothing in it has been optimised yet. None of this is
the bottleneck — a lawyer's review of the redaction is.

## What Jude takes from this

* **GLiNER truncates at 384 word-tokens** (`predict_entities`,
  `truncation=True`), found while writing the runners. Two of the
  corpus documents are near the limit; a real pleading is far past it.
  Fixed in v0.7.9: Jude's detector now windows the text on paragraph
  boundaries (`jude.detect.chunking`), the same code the GLiNER runners
  above use.
* **The GLiNER layer had no shape filter.** Chunking exposed it: on a
  short window GLiNER labels `the Firm`, `our client`, `Counsel for the
  Claimant` as organisations, and nothing dropped them. v0.7.9 runs
  GLiNER's PERSON / ORG / LOC output through the same normaliser as
  the spaCy layer, balances the windows, and extends the stop-list
  (litigation roles, defined terms, demonyms). Precision 0.892 → 0.922.
* **Whitelist matching** (v0.7.9): nationality adjectives stripped
  before alias lookup (`Belgian SPF Finances`, `Autorité de la
  concurrence française`); courts, prosecutors, statistical agencies
  and US/EU jurisdictions added (`Commercial Court of London`,
  `Department of Justice`, `Parquet National Financier`, `Eurostat`,
  `United States`, `France` …). Public-body over-redaction 7 % → 3 %.
* **A month is not a first name.** The shape filter rejected any span
  containing a month token — including *Jan Peeters*, since `jan` is
  January. Found because the filter now also applies to GLiNER; fixed.
* **Annotation policy on codenames** (`Helios` ×6 is half of Jude's
  remaining misses, and it is deliberate — `helios` sits in the
  header-stopword list). Deal codenames are confidential and should
  probably be redacted; that is a policy call, not a bug.
* **`nvidia/gliner-PII` as an opt-in detector**: +0.03 F1 over the base
  checkpoint on Jude's labels in isolation. Its licence (NVIDIA Open
  Model License) is not MIT-compatible for redistribution but fine as a
  runtime download. Needs an in-pipeline ablation before it earns a
  flag.

Where the remaining misses are and what closes them:
[Towards zero misses](towards-recall-one.html).

## What a legal-anonymisation model would need

For anyone minded to train one:

1. **Labels that encode the legal distinction, not the PII one.**
   `party_organisation` *versus* `public_body`; `private_person`
   *versus* `official_in_public_capacity`; `case_reference` and
   `internal_docket`; `place_of_business` alongside postal address;
   plus the usual contact identifiers. The negative class must be a
   label, not a post-hoc list.
2. **Legal synthetic data, multilingual, EU formats.** NVIDIA's
   data-designer approach works; the missing ingredient is the domain:
   term sheets, pleadings, board minutes, regulatory filings, in
   EN / FR / NL / DE, with EU case numbers, ECLI, IBANs, VAT numbers,
   Belgian national register numbers.
3. **Long context or built-in chunking** with consistent decisions
   across chunks — two pages is a short document here.
4. **Alias consistency**: *Mr. Tan* / *Wei Tan* / *the Claimant* must
   map to one pseudonym. A post-processing layer can do it; a model that
   emits coreference makes it much cheaper.
5. **Evaluation on real public documents** as well as synthetic ones:
   Commission decisions on EUR-Lex, US opinions on CourtListener, UK
   judgments on BAILII carry real party names with no confidentiality
   problem. That is the next extension of this corpus.

## Limitations of this benchmark

* Twenty synthetic documents, 400 spans, one annotation policy, two
  non-English documents, not yet reviewed by a lawyer (the Word
  protocol exists for that). The numbers are indicative; the *ranking* is
  robust — the gaps are 20 to 40 points, not 2.
* Where a mapping choice was ambiguous it was made in the external
  model's favour: dates and demographic labels are dropped rather than
  counted as false positives; adjacent name fragments are merged.
* Jude's whitelist was built on the same *genre* of document as the
  corpus (not on these documents), and its over-redaction figure
  benefits from that.
* Thresholds are the model cards' defaults; lowering NVIDIA's to 0.3
  changes nothing.
* Roblox's own card reports 45.5 % F1 on the Kaggle PII essay dataset;
  that number is not comparable to anything here and is not used.
