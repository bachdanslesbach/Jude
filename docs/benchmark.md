# Jude redaction benchmark

Span-level F1 across the 5-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict.

## Aggregate

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.861 | 0.899 | **0.879** | 62 | 10 | 7 |
| `jude-no-public-filter` | 0.685 | 0.913 | **0.783** | 63 | 29 | 6 |
| `spacy-only` | 0.559 | 0.551 | **0.555** | 38 | 30 | 31 |
| `regex-only` | 1.000 | 0.319 | **0.484** | 22 | 0 | 47 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 0.963 | 0.867 | 0.583 | 0.526 |
| doc_002_credit_facility_en | 0.880 | 0.815 | 0.545 | 0.556 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.632 | 0.609 | 0.222 | 0.571 |
| doc_005_supply_agreement_en | 0.929 | 0.743 | 0.581 | 0.471 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.769 | 0.833 | 0.800 | 10 | 3 | 2 |
| ORG | 0.864 | 0.864 | 0.864 | 19 | 3 | 3 |
| PERSON | 0.733 | 0.846 | 0.786 | 11 | 4 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.769 | 0.833 | 0.800 | 10 | 3 | 2 |
| ORG | 0.526 | 0.909 | 0.667 | 20 | 18 | 2 |
| PERSON | 0.579 | 0.846 | 0.688 | 11 | 8 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 9 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 5 |
| LOC | 0.727 | 0.667 | 0.696 | 8 | 3 | 4 |
| ORG | 0.487 | 0.864 | 0.623 | 19 | 20 | 3 |
| PERSON | 0.611 | 0.846 | 0.710 | 11 | 7 | 2 |
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
