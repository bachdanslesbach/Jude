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
  (400 spans): term sheets, credit facilities, witness statements,
  regulatory submissions, sanctions memos, engagement letters, patent
  and antitrust pleadings, insolvency updates — 18 in English, one
  French, one Dutch. All synthetic: professional secrecy rules out
  real files. Annotation policy: redact anything that identifies a
  party, adviser, witness or matter; leave public institutions,
  statutes, courts and jurisdictions in place. New documents are
  annotated in Word with one highlight colour per type
  ([protocol](annotation-protocol.html)); Jude pre-highlights, the
  reviewer corrects.
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
  213 whitelisted institutions, statutes and jurisdictions (with their
  aliases, ignoring demonyms and legal-form suffixes) that no gold span
  covers: 117 mentions. The column reports how many of them each system
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

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.930 | 0.998 | **0.963** | 0.963 | 3/119 (3%) | 0/1 | 6 | 0.928 | 472 | 3,576 MB |
| `jude-no-public-filter` | 0.756 | 0.970 | **0.850** | 0.852 | 96/119 (81%) | 6/12 | 5 | 0.859 | 398 | 3,252 MB |
| `spacy-only` | 0.745 | 0.708 | **0.726** | 0.741 | 79/119 (66%) | 55/117 | 9 | 0.797 | 2,079 | 1,926 MB |
| `regex-only` | 0.920 | 0.200 | **0.329** | 0.329 | 0/119 (0%) | 314/320 | 19 | 0.408 | 3,422,560 | 34 MB |
| `gliner-large-v2.1-jude-labels` | 0.713 | 0.610 | **0.658** | 0.709 | 64/119 (54%) | 93/156 | 10 | 0.763 | 2,660 | 1,694 MB |
| `nvidia-gliner-pii-native` | 0.780 | 0.675 | **0.724** | 0.812 | 26/119 (22%) | 82/130 | 10 | 0.843 | 2,475 | 3,433 MB |
| `nvidia-gliner-pii-native-t03` | 0.766 | 0.695 | **0.729** | 0.818 | 30/119 (25%) | 75/122 | 9 | 0.843 | 2,487 | 3,634 MB |
| `nvidia-gliner-pii-jude-labels` | 0.797 | 0.608 | **0.689** | 0.698 | 48/119 (40%) | 93/157 | 10 | 0.775 | 2,906 | 3,432 MB |
| `pplx-pii-masking` | 0.879 | 0.383 | **0.533** | 0.578 | 3/119 (3%) | 203/247 | 13 | 0.711 | 2,542 | 749 MB |
| `roblox-pii-classifier` | — | — | — | — | — | — | — | 0.764 | 2,293 | 946 MB |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.904 | 0.953 | **0.928** | 225 | 24 | 11 |
| `jude-no-public-filter` | 0.781 | 0.953 | **0.859** | 225 | 63 | 11 |
| `spacy-only` | 0.797 | 0.797 | **0.797** | 188 | 48 | 48 |
| `regex-only` | 0.968 | 0.258 | **0.408** | 61 | 2 | 175 |
| `gliner-large-v2.1-jude-labels` | 0.750 | 0.775 | **0.763** | 183 | 61 | 53 |
| `nvidia-gliner-pii-native` | 0.884 | 0.805 | **0.843** | 190 | 25 | 46 |
| `nvidia-gliner-pii-native-t03` | 0.866 | 0.822 | **0.843** | 194 | 30 | 42 |
| `nvidia-gliner-pii-jude-labels` | 0.845 | 0.716 | **0.775** | 169 | 31 | 67 |
| `pplx-pii-masking` | 0.861 | 0.606 | **0.711** | 143 | 23 | 93 |
| `roblox-pii-classifier` | 0.968 | 0.631 | **0.764** | 149 | 5 | 87 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only | gliner-large-v2.1-jude-labels | nvidia-gliner-pii-native | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-jude-labels | pplx-pii-masking |
|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.966 | 0.636 | 0.526 | 0.667 | 0.690 | 0.690 | 0.640 | 0.571 |
| doc_002_credit_facility_en | 0.929 | 0.875 | 0.692 | 0.500 | 0.435 | 0.741 | 0.741 | 0.545 | 0.750 |
| doc_003_solaris_jv_fr | 0.927 | 0.826 | 0.667 | 0.348 | 0.606 | 0.737 | 0.769 | 0.562 | 0.571 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 | 0.700 | 0.842 | 0.800 | 0.778 | 0.588 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 | 0.667 | 0.759 | 0.759 | 0.750 | 0.526 |
| doc_006_employment_dispute_en | 1.000 | 0.974 | 0.824 | 0.348 | 0.606 | 0.842 | 0.842 | 0.706 | 0.848 |
| doc_007_patent_litigation_en | 0.984 | 0.806 | 0.679 | 0.229 | 0.778 | 0.815 | 0.877 | 0.735 | 0.450 |
| doc_008_regulatory_submission_en | 1.000 | 0.912 | 0.808 | 0.267 | 0.636 | 0.714 | 0.714 | 0.698 | 0.323 |
| doc_009_witness_statement_en | 0.960 | 0.902 | 0.826 | 0.286 | 0.651 | 0.783 | 0.766 | 0.667 | 0.579 |
| doc_010_expert_economist_en | 0.973 | 0.739 | 0.714 | 0.200 | 0.500 | 0.600 | 0.645 | 0.500 | 0.261 |
| doc_011_sanctions_memo_en | 1.000 | 0.766 | 0.683 | 0.348 | 0.649 | 0.765 | 0.800 | 0.765 | 0.480 |
| doc_012_engagement_letter_en | 0.976 | 0.870 | 0.667 | 0.333 | 0.769 | 0.634 | 0.634 | 0.632 | 0.581 |
| doc_013_settlement_offer_en | 0.955 | 0.933 | 0.737 | 0.370 | 0.703 | 0.700 | 0.683 | 0.789 | 0.500 |
| doc_014_compliance_investigation_en | 0.976 | 0.909 | 0.769 | 0.320 | 0.667 | 0.811 | 0.769 | 0.757 | 0.621 |
| doc_015_corporate_restructuring_en | 0.963 | 0.897 | 0.784 | 0.267 | 0.651 | 0.667 | 0.652 | 0.698 | 0.471 |
| doc_016_tax_memo_en | 0.902 | 0.807 | 0.739 | 0.296 | 0.622 | 0.667 | 0.682 | 0.698 | 0.414 |
| doc_017_data_breach_notification_en | 0.909 | 0.757 | 0.621 | 0.400 | 0.647 | 0.710 | 0.667 | 0.759 | 0.609 |
| doc_018_cease_and_desist_en | 0.895 | 0.821 | 0.765 | 0.286 | 0.727 | 0.581 | 0.581 | 0.667 | 0.522 |
| doc_019_antitrust_complaint_en | 0.982 | 0.769 | 0.706 | 0.258 | 0.643 | 0.696 | 0.723 | 0.640 | 0.474 |
| doc_020_insolvency_update_en | 0.963 | 0.909 | 0.792 | 0.267 | 0.711 | 0.723 | 0.723 | 0.756 | 0.556 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.902 | 0.982 | 0.940 | 55 | 6 | 1 |
| ORG | 0.905 | 1.000 | 0.950 | 172 | 18 | 0 |
| PERSON | 0.957 | 1.000 | 0.978 | 89 | 4 | 0 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.618 | 0.982 | 0.759 | 55 | 34 | 1 |
| ORG | 0.663 | 0.959 | 0.784 | 165 | 84 | 7 |
| PERSON | 0.945 | 0.966 | 0.956 | 86 | 5 | 3 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.595 | 0.786 | 0.677 | 44 | 30 | 12 |
| ORG | 0.718 | 0.901 | 0.799 | 155 | 61 | 17 |
| PERSON | 0.933 | 0.944 | 0.939 | 84 | 6 | 5 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.696 | 0.889 | 0.780 | 16 | 7 | 2 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 56 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 172 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 89 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.389 | 0.560 | 7 | 0 | 11 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.614 | 0.911 | 0.734 | 51 | 32 | 5 |
| ORG | 0.667 | 0.709 | 0.687 | 122 | 61 | 50 |
| PERSON | 0.928 | 0.719 | 0.810 | 64 | 5 | 25 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-native — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 1.000 | 0.267 | 0.421 | 8 | 0 | 22 |
| IBAN | 0.611 | 0.917 | 0.733 | 11 | 7 | 1 |
| LOC | 0.631 | 0.946 | 0.757 | 53 | 31 | 3 |
| ORG | 1.000 | 0.541 | 0.702 | 93 | 0 | 79 |
| PERSON | 0.698 | 0.989 | 0.819 | 88 | 38 | 1 |
| PHONE | 1.000 | 0.773 | 0.872 | 17 | 0 | 5 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-native-t03 — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 0.900 | 0.300 | 0.450 | 9 | 1 | 21 |
| IBAN | 0.524 | 0.917 | 0.667 | 11 | 10 | 1 |
| LOC | 0.596 | 0.946 | 0.731 | 53 | 36 | 3 |
| ORG | 1.000 | 0.576 | 0.731 | 99 | 0 | 73 |
| PERSON | 0.698 | 0.989 | 0.819 | 88 | 38 | 1 |
| PHONE | 1.000 | 0.818 | 0.900 | 18 | 0 | 4 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### nvidia-gliner-pii-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.611 | 0.759 | 11 | 0 | 7 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 30 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| LOC | 0.641 | 0.893 | 0.746 | 50 | 28 | 6 |
| ORG | 0.790 | 0.634 | 0.703 | 109 | 29 | 63 |
| PERSON | 0.936 | 0.820 | 0.874 | 73 | 5 | 16 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### pplx-pii-masking — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 18 |
| EMAIL | 0.857 | 1.000 | 0.923 | 30 | 5 | 0 |
| IBAN | 0.522 | 1.000 | 0.686 | 12 | 11 | 0 |
| LOC | 1.000 | 0.268 | 0.423 | 15 | 0 | 41 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 172 |
| PERSON | 0.943 | 0.933 | 0.938 | 83 | 5 | 6 |
| PHONE | 1.000 | 0.545 | 0.706 | 12 | 0 | 10 |
| URL | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
- **`gliner-large-v2.1-jude-labels`** — model `urchade/gliner_large-v2.1`; device mps; load 27.1 s; threshold 0.5.
- **`nvidia-gliner-pii-native`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 13.1 s; threshold 0.5.
- **`nvidia-gliner-pii-native-t03`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.1 s; threshold 0.3.
- **`nvidia-gliner-pii-jude-labels`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 13.2 s; threshold 0.5.
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

* **Long-tail rules and the review report** (v0.7.10). Deterministic
  rules for what statistical NER predictably misses — legal-form
  suffixes, short names defined in parentheses, honorific + name,
  vessels, street addresses, bare domains, a family behind a trust —
  plus the bundled banks and public companies as a detector. Recall
  0.970 → **0.998**, F1 0.945 → 0.963, no new false positives; the one
  remaining miss is an annotation-policy conflict (*Luxembourg* as a
  place of business, which the whitelist treats as a jurisdiction — so
  the review report, which honours the whitelist, cannot surface it
  either: hence "0/1" in the *misses surfaced* column). And the
  fail-closed half: `jude review` and the review panel list every
  capitalised or identifier-shaped term that is neither redacted nor
  public — six items per corpus document.
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
