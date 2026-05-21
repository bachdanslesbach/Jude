# Jude redaction benchmark

Span-level F1 across the 5-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict.

## Aggregate

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.921 | 1.000 | **0.959** | 70 | 6 | 0 |
| `jude-no-public-filter` | 0.729 | 1.000 | **0.843** | 70 | 26 | 0 |
| `spacy-only` | 0.662 | 0.614 | **0.637** | 43 | 22 | 27 |
| `regex-only` | 1.000 | 0.314 | **0.478** | 22 | 0 | 48 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.933 | 0.609 | 0.526 |
| doc_002_credit_facility_en | 0.966 | 0.875 | 0.692 | 0.526 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.857 | 1.000 | 0.923 | 12 | 2 | 0 |
| ORG | 0.880 | 1.000 | 0.936 | 22 | 3 | 0 |
| PERSON | 0.933 | 1.000 | 0.966 | 14 | 1 | 0 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.750 | 1.000 | 0.857 | 12 | 4 | 0 |
| ORG | 0.512 | 1.000 | 0.677 | 22 | 21 | 0 |
| PERSON | 0.933 | 1.000 | 0.966 | 14 | 1 | 0 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 9 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 5 |
| LOC | 0.769 | 0.833 | 0.800 | 10 | 3 | 2 |
| ORG | 0.541 | 0.909 | 0.678 | 20 | 17 | 2 |
| PERSON | 0.867 | 0.929 | 0.897 | 13 | 2 | 1 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 6 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 14 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |
