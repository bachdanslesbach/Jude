---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 20-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.922 | 0.970 | **0.945** | 0.950 | 3/117 (3%) | 0.922 | 426 | 3,423 MB |
| `jude-no-public-filter` | 0.756 | 0.968 | **0.849** | 0.853 | 95/117 (81%) | 0.854 | 453 | 3,360 MB |
| `spacy-only` | 0.745 | 0.708 | **0.726** | 0.741 | 79/117 (68%) | 0.797 | 2,079 | 1,926 MB |
| `regex-only` | 0.920 | 0.200 | **0.329** | 0.329 | 0/117 (0%) | 0.408 | 3,422,560 | 34 MB |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.893 | 0.953 | **0.922** | 225 | 27 | 11 |
| `jude-no-public-filter` | 0.773 | 0.953 | **0.854** | 225 | 66 | 11 |
| `spacy-only` | 0.797 | 0.797 | **0.797** | 188 | 48 | 48 |
| `regex-only` | 0.968 | 0.258 | **0.408** | 61 | 2 | 175 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.966 | 0.636 | 0.526 |
| doc_002_credit_facility_en | 0.929 | 0.875 | 0.692 | 0.500 |
| doc_003_solaris_jv_fr | 0.927 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 |
| doc_006_employment_dispute_en | 1.000 | 0.974 | 0.824 | 0.348 |
| doc_007_patent_litigation_en | 0.857 | 0.787 | 0.679 | 0.229 |
| doc_008_regulatory_submission_en | 0.962 | 0.877 | 0.808 | 0.267 |
| doc_009_witness_statement_en | 0.960 | 0.923 | 0.826 | 0.286 |
| doc_010_expert_economist_en | 0.973 | 0.766 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 1.000 | 0.766 | 0.683 | 0.348 |
| doc_012_engagement_letter_en | 0.976 | 0.870 | 0.667 | 0.333 |
| doc_013_settlement_offer_en | 0.930 | 0.909 | 0.737 | 0.370 |
| doc_014_compliance_investigation_en | 0.976 | 0.909 | 0.769 | 0.320 |
| doc_015_corporate_restructuring_en | 0.926 | 0.862 | 0.784 | 0.267 |
| doc_016_tax_memo_en | 0.880 | 0.800 | 0.739 | 0.296 |
| doc_017_data_breach_notification_en | 0.909 | 0.789 | 0.621 | 0.400 |
| doc_018_cease_and_desist_en | 0.865 | 0.821 | 0.765 | 0.286 |
| doc_019_antitrust_complaint_en | 0.982 | 0.800 | 0.706 | 0.258 |
| doc_020_insolvency_update_en | 0.963 | 0.909 | 0.792 | 0.267 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.885 | 0.964 | 0.923 | 54 | 7 | 2 |
| ORG | 0.891 | 0.953 | 0.921 | 164 | 20 | 8 |
| PERSON | 0.957 | 0.989 | 0.972 | 88 | 4 | 1 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.900 | 1.000 | 0.947 | 18 | 2 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.618 | 0.982 | 0.759 | 55 | 34 | 1 |
| ORG | 0.656 | 0.942 | 0.773 | 162 | 85 | 10 |
| PERSON | 0.957 | 0.989 | 0.972 | 88 | 4 | 1 |
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

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
