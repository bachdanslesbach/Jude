---
title: PII models on legal documents
layout: default
---

# PII models on legal documents

## Why this comparison exists

Generic PII detectors are built for chat logs, support tickets and
customer forms. Legal anonymisation is a different task, in three
ways that the numbers below make concrete:

1. **The parties are organisations.** In a competition or M&A file the
   identifying information is *which companies* are involved, far more
   than which individuals. A detector without an organisation label
   cannot do the job, whatever its score on names and e-mails.
2. **The regulatory framing must survive.** A memo in which every
   mention of the European Commission, the Bundeskartellamt, the DMA or
   Article 102 TFEU has become `Org7` is useless to the model that
   receives it — and none of that framing identifies the client. The
   *public-body over-redaction* column measures this directly.
3. **Case references and internal dockets are identifiers.**
   `Case T-203/24`, `1:26-cv-00489-RGA`, `IPR2025-00712`, `M-2026-PIO-001`
   identify a matter as surely as a name does. No generic PII taxonomy
   has a label for them.

Beyond those, legal documents are long (two pages is short), routinely
multilingual in Brussels practice (EN/FR/NL in one file), and refer to
the same person under several surface forms — all of which a
span-level model sees nothing of.

## Systems compared

| System | What it is | Params | Labels | Languages | Licence |
|---|---|---|---|---|---|
| `jude-full` | Jude's shipped pipeline: regex + spaCy `en_core_web_trf` + GLiNER large (legal labels) + per-matter dictionary, two-pass, public-knowledge whitelist | ~0.9 B across models | Jude schema (PERSON, ORG, LOC, EMAIL, PHONE, IBAN, CASE_REF, URL, SECRET) | EN / FR / NL routed per paragraph | MIT |
| `jude-no-public-filter` | Same, whitelist disabled (ablation) | — | — | — | — |
| `spacy-only` / `regex-only` | Single-layer ablations | — | — | — | — |
| `gliner-large-v2.1-jude-labels` | The base GLiNER checkpoint Jude uses, alone, with Jude's legal labels | ~0.45 B | zero-shot | EN | Apache-2.0 |
| `nvidia-gliner-pii-native` | `nvidia/gliner-PII`: GLiNER large fine-tuned on 100k synthetic Nemotron-PII records (55 categories, US + international formats), queried with the 18 native labels that map onto Jude's schema, thresholds 0.5 and 0.3 | ~0.45 B | 55 native | EN only | NVIDIA Open Model License |
| `nvidia-gliner-pii-jude-labels` | Same checkpoint queried with Jude's legal labels — isolates the effect of the PII fine-tune from the label set | ~0.45 B | zero-shot | EN | — |
| `pplx-pii-masking` | `perplexity-ai/pplx-pii-masking`: bidirectional Qwen3 encoder, BIOES token head + Viterbi decoder, 4096-token window | 0.60 B | 9 (`private_person`, `private_email`, `private_phone`, `private_address`, `private_url`, `private_date`, `account_number`, `secret`, `other_pii`) | EN + multilingual (card) | MIT, `trust_remote_code` (reviewed, pinned) |
| `roblox-pii-classifier` | XLM-RoBERTa-large message classifier: *asking for* / *giving* PII, no spans | 0.56 B | 2 | multilingual | Apache-2.0 |

Model revisions are pinned in the runner sources and listed under
*Runner notes*.

## Protocol

* **Corpus.** The 20 gold-annotated documents in `benchmark/corpus/`
  (401 spans): term sheets, credit facilities, witness statements,
  regulatory submissions, sanctions memos, engagement letters, patent
  and antitrust pleadings, insolvency updates — 18 in English, one
  French, one Dutch. All synthetic: professional secrecy rules out
  real files. Annotation policy: redact anything that identifies a
  party, adviser, witness or matter; leave public institutions,
  statutes, courts and jurisdictions in place.
* **Matching.** Lenient overlap (≥ 1 character), one-to-one, largest
  overlap first. *Type-strict* requires the predicted type to equal
  the gold type after mapping the system's labels onto Jude's schema;
  *any type* drops that requirement and answers "did it redact the
  right characters".
* **Label mapping.** Each external system's labels are mapped to the
  closest Jude type (tables in `benchmark/runners/`). Labels with no
  counterpart — dates, demographic attributes, `other_pii` — are
  dropped and counted, not scored as false positives. NVIDIA's
  `first_name` / `last_name` predictions are merged when adjacent.
* **Public-body over-redaction.** Occurrences in the corpus of the
  190 whitelisted institutions, statutes and jurisdictions (with their
  aliases, ignoring demonyms and legal-form suffixes) that no gold span
  covers: 95 mentions. The column reports how many of them each system
  redacted.
* **Sentence level.** Every document split into sentences; a sentence
  is positive iff it overlaps a gold span; a system flags it iff it
  predicts anything inside it. The only grid on which a message
  classifier can be compared with span extractors.
* **Hardware.** MacBook M2, 8 GB, one runner per process; external
  models on MPS (`PYTORCH_ENABLE_MPS_FALLBACK=1`), Jude's own stack on
  CPU as shipped. Throughput excludes model load; peak RSS is the
  process high-water mark.

Span-level F1 across the 20-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.892 | 0.965 | **0.927** | 0.932 | 7/95 (7%) | 0.903 | 464 | 3,428 MB |
| `jude-no-public-filter` | 0.762 | 0.960 | **0.850** | 0.854 | 82/95 (86%) | 0.857 | 471 | 3,443 MB |
| `spacy-only` | 0.737 | 0.706 | **0.721** | 0.736 | 66/95 (69%) | 0.795 | 2,355 | 3,129 MB |
| `regex-only` | 0.920 | 0.200 | **0.328** | 0.328 | 0/95 (0%) | 0.408 | 3,291,201 | 34 MB |
| `gliner-large-v2.1-jude-labels` | 0.687 | 0.526 | **0.596** | 0.647 | 48/95 (51%) | 0.711 | 2,245 | 2,451 MB |
| `nvidia-gliner-pii-native` | 0.777 | 0.633 | **0.698** | 0.780 | 17/95 (18%) | 0.825 | 2,546 | 3,541 MB |
| `nvidia-gliner-pii-native-t03` | 0.747 | 0.648 | **0.694** | 0.777 | 21/95 (22%) | 0.825 | 2,588 | 3,969 MB |
| `nvidia-gliner-pii-jude-labels` | 0.781 | 0.551 | **0.646** | 0.655 | 34/95 (36%) | 0.742 | 2,885 | 3,804 MB |
| `pplx-pii-masking` | 0.879 | 0.382 | **0.532** | 0.577 | 3/95 (3%) | 0.711 | 2,542 | 749 MB |
| `roblox-pii-classifier` | — | — | — | — | — | 0.764 | 2,293 | 946 MB |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.862 | 0.949 | **0.903** | 224 | 36 | 12 |
| `jude-no-public-filter` | 0.780 | 0.949 | **0.857** | 224 | 63 | 12 |
| `spacy-only` | 0.793 | 0.797 | **0.795** | 188 | 49 | 48 |
| `regex-only` | 0.968 | 0.258 | **0.408** | 61 | 2 | 175 |
| `gliner-large-v2.1-jude-labels` | 0.742 | 0.682 | **0.711** | 161 | 56 | 75 |
| `nvidia-gliner-pii-native` | 0.876 | 0.780 | **0.825** | 184 | 26 | 52 |
| `nvidia-gliner-pii-native-t03` | 0.851 | 0.801 | **0.825** | 189 | 33 | 47 |
| `nvidia-gliner-pii-jude-labels` | 0.832 | 0.669 | **0.742** | 158 | 32 | 78 |
| `pplx-pii-masking` | 0.861 | 0.606 | **0.711** | 143 | 23 | 93 |
| `roblox-pii-classifier` | 0.968 | 0.631 | **0.764** | 149 | 5 | 87 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only | gliner-large-v2.1-jude-labels | nvidia-gliner-pii-native | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-jude-labels | pplx-pii-masking |
|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.933 | 0.609 | 0.526 | 0.667 | 0.690 | 0.690 | 0.640 | 0.571 |
| doc_002_credit_facility_en | 0.929 | 0.875 | 0.692 | 0.500 | 0.435 | 0.741 | 0.741 | 0.545 | 0.750 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 | 0.606 | 0.737 | 0.769 | 0.562 | 0.571 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 | 0.700 | 0.842 | 0.800 | 0.778 | 0.588 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 | 0.667 | 0.759 | 0.759 | 0.750 | 0.526 |
| doc_006_employment_dispute_en | 1.000 | 0.974 | 0.824 | 0.348 | 0.429 | 0.944 | 0.944 | 0.727 | 0.848 |
| doc_007_patent_litigation_en | 0.857 | 0.800 | 0.667 | 0.229 | 0.558 | 0.638 | 0.640 | 0.512 | 0.450 |
| doc_008_regulatory_submission_en | 0.926 | 0.847 | 0.792 | 0.267 | 0.513 | 0.526 | 0.526 | 0.526 | 0.323 |
| doc_009_witness_statement_en | 0.960 | 0.923 | 0.826 | 0.286 | 0.651 | 0.870 | 0.870 | 0.750 | 0.579 |
| doc_010_expert_economist_en | 0.923 | 0.766 | 0.714 | 0.200 | 0.444 | 0.552 | 0.533 | 0.438 | 0.261 |
| doc_011_sanctions_memo_en | 0.973 | 0.750 | 0.683 | 0.348 | 0.514 | 0.800 | 0.800 | 0.606 | 0.480 |
| doc_012_engagement_letter_en | 0.870 | 0.851 | 0.650 | 0.320 | 0.634 | 0.619 | 0.619 | 0.615 | 0.562 |
| doc_013_settlement_offer_en | 0.909 | 0.909 | 0.737 | 0.370 | 0.562 | 0.541 | 0.579 | 0.686 | 0.500 |
| doc_014_compliance_investigation_en | 0.909 | 0.909 | 0.769 | 0.320 | 0.667 | 0.811 | 0.769 | 0.757 | 0.621 |
| doc_015_corporate_restructuring_en | 0.926 | 0.877 | 0.784 | 0.267 | 0.489 | 0.571 | 0.596 | 0.600 | 0.471 |
| doc_016_tax_memo_en | 0.894 | 0.792 | 0.739 | 0.296 | 0.622 | 0.651 | 0.667 | 0.651 | 0.414 |
| doc_017_data_breach_notification_en | 0.968 | 0.882 | 0.621 | 0.400 | 0.667 | 0.688 | 0.647 | 0.710 | 0.609 |
| doc_018_cease_and_desist_en | 0.821 | 0.889 | 0.743 | 0.286 | 0.727 | 0.600 | 0.545 | 0.710 | 0.522 |
| doc_019_antitrust_complaint_en | 0.982 | 0.781 | 0.706 | 0.258 | 0.625 | 0.667 | 0.667 | 0.651 | 0.474 |
| doc_020_insolvency_update_en | 0.929 | 0.893 | 0.792 | 0.267 | 0.727 | 0.766 | 0.766 | 0.756 | 0.556 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.831 | 0.964 | 0.893 | 54 | 11 | 2 |
| ORG | 0.859 | 0.948 | 0.901 | 164 | 27 | 9 |
| PERSON | 0.926 | 0.978 | 0.951 | 87 | 7 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.640 | 0.982 | 0.775 | 55 | 31 | 1 |
| ORG | 0.668 | 0.931 | 0.778 | 161 | 80 | 12 |
| PERSON | 0.926 | 0.978 | 0.951 | 87 | 7 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.595 | 0.786 | 0.677 | 44 | 30 | 12 |
| ORG | 0.711 | 0.896 | 0.793 | 155 | 63 | 18 |
| PERSON | 0.913 | 0.944 | 0.928 | 84 | 8 | 5 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.696 | 0.889 | 0.780 | 16 | 7 | 2 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 56 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 173 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 89 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.333 | 0.500 | 6 | 0 | 12 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.607 | 0.911 | 0.729 | 51 | 33 | 5 |
| ORG | 0.641 | 0.578 | 0.608 | 100 | 56 | 73 |
| PERSON | 0.885 | 0.607 | 0.720 | 54 | 7 | 35 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-native — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 1.000 | 0.400 | 0.571 | 12 | 0 | 18 |
| IBAN | 0.556 | 0.833 | 0.667 | 10 | 8 | 2 |
| LOC | 0.634 | 0.929 | 0.754 | 52 | 30 | 4 |
| ORG | 1.000 | 0.434 | 0.605 | 75 | 0 | 98 |
| PERSON | 0.715 | 0.989 | 0.830 | 88 | 35 | 1 |
| PHONE | 1.000 | 0.773 | 0.872 | 17 | 0 | 5 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-native-t03 — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 1.000 | 0.400 | 0.571 | 12 | 0 | 18 |
| IBAN | 0.500 | 0.917 | 0.647 | 11 | 11 | 1 |
| LOC | 0.558 | 0.946 | 0.702 | 53 | 42 | 3 |
| ORG | 1.000 | 0.457 | 0.627 | 79 | 0 | 94 |
| PERSON | 0.715 | 0.989 | 0.830 | 88 | 35 | 1 |
| PHONE | 1.000 | 0.773 | 0.872 | 17 | 0 | 5 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.556 | 0.714 | 10 | 0 | 8 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.613 | 0.875 | 0.721 | 49 | 31 | 7 |
| ORG | 0.778 | 0.526 | 0.628 | 91 | 26 | 82 |
| PERSON | 0.934 | 0.798 | 0.861 | 71 | 5 | 18 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### pplx-pii-masking — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 0.857 | 1.000 | 0.923 | 30 | 5 | 0 |
| IBAN | 0.522 | 1.000 | 0.686 | 12 | 11 | 0 |
| LOC | 1.000 | 0.268 | 0.423 | 15 | 0 | 41 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 173 |
| PERSON | 0.943 | 0.933 | 0.938 | 83 | 5 | 6 |
| PHONE | 1.000 | 0.545 | 0.706 | 12 | 0 | 10 |
| URL | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
- **`gliner-large-v2.1-jude-labels`** — model `urchade/gliner_large-v2.1`; device mps; load 17.1 s; threshold 0.5.
- **`nvidia-gliner-pii-native`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.4 s; threshold 0.5.
- **`nvidia-gliner-pii-native-t03`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 11.8 s; threshold 0.3.
- **`nvidia-gliner-pii-jude-labels`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 11.9 s; threshold 0.5.
- **`pplx-pii-masking`** — model `perplexity-ai/pplx-pii-masking` @ `f1f90a53`; device mps; load 5.7 s; out-of-schema predictions dropped: other_pii×4, private_date×24; mean document sensitivity 0.11.
  - No organisation label: ORG recall is 0 by construction.
  - `private_date` / `other_pii` predictions dropped as out-of-schema (counted, not scored as FP).
  - Input truncated at 4096 tokens; corpus documents are far shorter.
- **`roblox-pii-classifier`** — model `roblox/roblox-pii-classifier` @ `253c2057`; device mps; load 9.3 s; threshold 0.2691.
  - Message-level classifier (asking-for / giving PII); no spans. Scored on the sentence grid only.
  - Trained on chat; the model card itself reports 45.5% F1 on the Kaggle PII essay dataset.

## Failure taxonomy

Everything below is read off `python -m benchmark.analyze
benchmark/results/*.json`; the counts are exact for this corpus.

### 1. Generic PII taxonomies have no word for half of what a legal document must hide

ORG (173 spans) and CASE_REF (18) together are 191 of the 401 gold
spans — 48 %. `pplx-pii-masking` has no organisation label: ORG recall
is **0.000** by construction. NVIDIA's `company_name` fires on 43 % of
ORG spans — with perfect precision when it does — and misses the rest:
short names (`UBS`, `BIL`, `BNP Paribas`), trading names
(`TotalEnergies` without its `SE`), codenames (`Helios`, `Northbridge`),
a bank named only by acronym (`BCEE`). Neither system has a notion of a
case reference; `pplx` files 7 of the 18 under `account_number`.

Seven of the twenty documents score below 0.5 for `pplx` (an eighth at
exactly 0.500); the antitrust complaint, the regulatory submission and
the expert-economist report — the documents densest in company names —
are the worst (0.474, 0.323, 0.261).

### 2. Address ≠ location

`private_address` catches full postal addresses and nothing else
(precision 1.000, LOC recall **0.268**). *Brussels*, *Paris*, *Munich*,
*Hamburg* are not PII to `pplx`. For a lawyer, the city of a party's
registered office is often the strongest quasi-identifier in the file —
the seat of the only listed brewer in a small country is the brewer.

### 3. E-mail addresses read as names

NVIDIA's model labels the local part of an e-mail address as
`first_name` / `last_name` — *sophie*, *martin*, *chen*, *hartmann* — so
18 of 30 e-mails are lost (EMAIL recall 0.400) and 35 spurious PERSON
spans appear. Its type-agnostic F1 (0.780 against 0.698 strict) shows
that a third of its gap is label confusion, not blindness. `pplx` has
the mirror problem: five phone numbers were fused into the preceding
e-mail span (`sophie.martin@example-law.eu, +33 1 44 55 66 77` as one
`private_email`).

### 4. Over-redaction of the public sphere

Share of the 95 public-body mentions redacted: base GLiNER **51 %**,
NVIDIA with Jude's labels 36 %, NVIDIA native 18 %, Jude without its
whitelist 86 %, Jude 7 %, `pplx` 3 %. NVIDIA's native run classifies
*Bundeskartellamt* as an identification number three times and redacts
*UK*, *Cayman*, *Ireland*, *Luxembourg* as countries. `pplx`'s 3 % is
the flip side of §1–2: it barely redacts places or organisations at
all, public or private. Jude's seven residual hits are alias-
normalisation gaps (`Autorité de la concurrence française`, `Belgian
SPF Finances`) and long spans that swallow a whitelisted word
(`UNITED STATES DISTRICT COURT FOR THE DISTRICT OF DELAWARE`) — fixable,
and on the list.

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

Same checkpoint family, same labels, same threshold: NVIDIA's
fine-tune against the base GLiNER on Jude's legal labels moves PERSON
0.720 → 0.861, CASE_REF 0.500 → 0.714, ORG 0.608 → 0.628, and public-
body over-redaction 51 % → 36 %. Synthetic-PII training helps on legal
text it never saw. It also says what is missing: not architecture, but
*legal* training data and a label set with parties and public bodies
as first-class, opposite categories.

### 8. Cost

All three external models run at 2.3–2.9 k chars/s on an M2 laptop
(MPS): a twenty-page brief in about twenty seconds. `pplx` is the
lightest to deploy (749 MB resident, bf16, MIT). Jude's shipped stack
is five times slower (464 chars/s: transformer spaCy and GLiNER on CPU,
two passes) and nothing in it has been optimised yet. None of this is
the bottleneck — a lawyer's review of the redaction is.

## What Jude takes from this

* **GLiNER truncates at 384 word-tokens** (`predict_entities`,
  `truncation=True`), found while writing the runners. Jude's own
  detector needs the chunking the benchmark runner has. Two of the
  corpus documents are near the limit; a real pleading is far past it.
* **Whitelist matching**: strip demonym prefixes and adjectival
  suffixes before alias lookup; add courts, prosecutors and statistical
  agencies (`Commercial Court of London`, `Department of Justice`,
  `Parquet National Financier`, `Eurostat`). Worth ~7 false positives.
* **Annotation policy on codenames** (`Helios` ×6 is Jude's largest
  residual miss, and it is deliberate — `helios` sits in the
  header-stopword list). Deal codenames are confidential and should
  probably be redacted; that is a policy call, not a bug.
* **`nvidia/gliner-PII` as an opt-in detector**: +0.05 F1 over the base
  checkpoint on Jude's labels in isolation. Its licence (NVIDIA Open
  Model License) is not MIT-compatible for redistribution but fine as a
  runtime download. Needs an in-pipeline ablation before it earns a
  flag.

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

* Twenty synthetic documents, 401 spans, one annotation policy, two
  non-English documents. The numbers are indicative; the *ranking* is
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
