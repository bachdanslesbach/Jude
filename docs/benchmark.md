---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 20-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.892 | 0.965 | **0.927** | 0.932 | 7/95 (7%) | 0.903 | 464 | 3,428 MB |
| `jude-no-public-filter` | 0.762 | 0.960 | **0.850** | 0.854 | 82/95 (86%) | 0.857 | 471 | 3,443 MB |
| `spacy-only` | 0.737 | 0.706 | **0.721** | 0.736 | 66/95 (69%) | 0.795 | 2,355 | 3,129 MB |
| `regex-only` | 0.920 | 0.200 | **0.328** | 0.328 | 0/95 (0%) | 0.408 | 3,291,201 | 34 MB |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.862 | 0.949 | **0.903** | 224 | 36 | 12 |
| `jude-no-public-filter` | 0.780 | 0.949 | **0.857** | 224 | 63 | 12 |
| `spacy-only` | 0.793 | 0.797 | **0.795** | 188 | 49 | 48 |
| `regex-only` | 0.968 | 0.258 | **0.408** | 61 | 2 | 175 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.933 | 0.609 | 0.526 |
| doc_002_credit_facility_en | 0.929 | 0.875 | 0.692 | 0.500 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 |
| doc_006_employment_dispute_en | 1.000 | 0.974 | 0.824 | 0.348 |
| doc_007_patent_litigation_en | 0.857 | 0.800 | 0.667 | 0.229 |
| doc_008_regulatory_submission_en | 0.926 | 0.847 | 0.792 | 0.267 |
| doc_009_witness_statement_en | 0.960 | 0.923 | 0.826 | 0.286 |
| doc_010_expert_economist_en | 0.923 | 0.766 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 0.973 | 0.750 | 0.683 | 0.348 |
| doc_012_engagement_letter_en | 0.870 | 0.851 | 0.650 | 0.320 |
| doc_013_settlement_offer_en | 0.909 | 0.909 | 0.737 | 0.370 |
| doc_014_compliance_investigation_en | 0.909 | 0.909 | 0.769 | 0.320 |
| doc_015_corporate_restructuring_en | 0.926 | 0.877 | 0.784 | 0.267 |
| doc_016_tax_memo_en | 0.894 | 0.792 | 0.739 | 0.296 |
| doc_017_data_breach_notification_en | 0.968 | 0.882 | 0.621 | 0.400 |
| doc_018_cease_and_desist_en | 0.821 | 0.889 | 0.743 | 0.286 |
| doc_019_antitrust_complaint_en | 0.982 | 0.781 | 0.706 | 0.258 |
| doc_020_insolvency_update_en | 0.929 | 0.893 | 0.792 | 0.267 |

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

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
