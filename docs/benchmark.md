# Jude redaction benchmark

Span-level F1 across the 5-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict.

## Aggregate

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.877 | 0.928 | **0.901** | 64 | 9 | 5 |
| `jude-no-public-filter` | 0.699 | 0.942 | **0.802** | 65 | 28 | 4 |
| `spacy-only` | 0.646 | 0.609 | **0.627** | 42 | 23 | 27 |
| `regex-only` | 1.000 | 0.319 | **0.484** | 22 | 0 | 47 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 0.963 | 0.897 | 0.609 | 0.526 |
| doc_002_credit_facility_en | 0.963 | 0.867 | 0.640 | 0.556 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.632 | 0.609 | 0.500 | 0.571 |
| doc_005_supply_agreement_en | 0.963 | 0.765 | 0.643 | 0.471 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.786 | 0.917 | 0.846 | 11 | 3 | 1 |
| ORG | 0.952 | 0.909 | 0.930 | 20 | 1 | 2 |
| PERSON | 0.688 | 0.846 | 0.759 | 11 | 5 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.786 | 0.917 | 0.846 | 11 | 3 | 1 |
| ORG | 0.525 | 0.955 | 0.677 | 21 | 19 | 1 |
| PERSON | 0.647 | 0.846 | 0.733 | 11 | 6 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 9 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 5 |
| LOC | 0.769 | 0.833 | 0.800 | 10 | 3 | 2 |
| ORG | 0.541 | 0.909 | 0.678 | 20 | 17 | 2 |
| PERSON | 0.800 | 0.923 | 0.857 | 12 | 3 | 1 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 6 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 13 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |
