# Jude redaction benchmark

Span-level F1 across the 5-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict.

## Aggregate

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.692 | 0.851 | **0.764** | 63 | 28 | 11 |
| `jude-no-public-filter` | 0.612 | 0.851 | **0.712** | 63 | 40 | 11 |
| `spacy-only` | 0.487 | 0.514 | **0.500** | 38 | 40 | 36 |
| `regex-only` | 1.000 | 0.297 | **0.458** | 22 | 0 | 52 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 0.788 | 0.743 | 0.483 | 0.476 |
| doc_002_credit_facility_en | 0.815 | 0.786 | 0.522 | 0.556 |
| doc_003_solaris_jv_fr | 0.760 | 0.717 | 0.583 | 0.308 |
| doc_004_brussels_letter_nl | 0.636 | 0.583 | 0.211 | 0.571 |
| doc_005_supply_agreement_en | 0.788 | 0.703 | 0.545 | 0.471 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.625 | 0.833 | 0.714 | 10 | 6 | 2 |
| ORG | 0.625 | 0.741 | 0.678 | 20 | 12 | 7 |
| PERSON | 0.524 | 0.846 | 0.647 | 11 | 10 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.625 | 0.833 | 0.714 | 10 | 6 | 2 |
| ORG | 0.455 | 0.741 | 0.563 | 20 | 24 | 7 |
| PERSON | 0.524 | 0.846 | 0.647 | 11 | 10 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 9 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 5 |
| LOC | 0.615 | 0.667 | 0.640 | 8 | 5 | 4 |
| ORG | 0.422 | 0.704 | 0.528 | 19 | 26 | 8 |
| PERSON | 0.550 | 0.846 | 0.667 | 11 | 9 | 2 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 6 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| EMAIL | 1.000 | 1.000 | 1.000 | 9 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 12 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 27 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 13 |
| PHONE | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |
