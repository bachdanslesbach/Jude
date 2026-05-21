# Jude redaction benchmark

Span-level F1 across the 5-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict.

## Aggregate

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.823 | 0.938 | **0.876** | 376 | 81 | 25 |
| `jude-no-public-filter` | 0.737 | 0.930 | **0.822** | 373 | 133 | 28 |
| `spacy-only` | 0.729 | 0.706 | **0.717** | 283 | 105 | 118 |
| `regex-only` | 1.000 | 0.165 | **0.283** | 66 | 0 | 335 |

## Per document (F1)

| Document | jude-full | jude-no-public-filter | spacy-only | regex-only |
|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.933 | 0.609 | 0.526 |
| doc_002_credit_facility_en | 0.966 | 0.875 | 0.692 | 0.526 |
| doc_003_solaris_jv_fr | 0.905 | 0.826 | 0.667 | 0.348 |
| doc_004_brussels_letter_nl | 0.952 | 0.833 | 0.500 | 0.571 |
| doc_005_supply_agreement_en | 1.000 | 0.765 | 0.643 | 0.471 |
| doc_006_employment_dispute_en | 0.927 | 0.927 | 0.778 | 0.273 |
| doc_007_patent_litigation_en | 0.800 | 0.772 | 0.667 | 0.125 |
| doc_008_regulatory_submission_en | 0.906 | 0.828 | 0.792 | 0.207 |
| doc_009_witness_statement_en | 0.920 | 0.902 | 0.826 | 0.222 |
| doc_010_expert_economist_en | 0.923 | 0.766 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 0.850 | 0.723 | 0.683 | 0.286 |
| doc_012_engagement_letter_en | 0.755 | 0.741 | 0.619 | 0.250 |
| doc_013_settlement_offer_en | 0.837 | 0.837 | 0.737 | 0.250 |
| doc_014_compliance_investigation_en | 0.864 | 0.884 | 0.769 | 0.261 |
| doc_015_corporate_restructuring_en | 0.842 | 0.842 | 0.784 | 0.207 |
| doc_016_tax_memo_en | 0.755 | 0.755 | 0.739 | 0.231 |
| doc_017_data_breach_notification_en | 0.824 | 0.800 | 0.621 | 0.333 |
| doc_018_cease_and_desist_en | 0.789 | 0.857 | 0.743 | 0.211 |
| doc_019_antitrust_complaint_en | 0.964 | 0.781 | 0.706 | 0.258 |
| doc_020_insolvency_update_en | 0.929 | 0.893 | 0.792 | 0.267 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.278 | 0.435 | 5 | 0 | 13 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.679 | 0.982 | 0.803 | 55 | 26 | 1 |
| ORG | 0.775 | 0.954 | 0.855 | 165 | 48 | 8 |
| PERSON | 0.926 | 0.978 | 0.951 | 87 | 7 | 2 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.278 | 0.435 | 5 | 0 | 13 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.640 | 0.982 | 0.775 | 55 | 31 | 1 |
| ORG | 0.630 | 0.936 | 0.753 | 162 | 95 | 11 |
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
| ORG | 0.698 | 0.896 | 0.785 | 155 | 67 | 18 |
| PERSON | 0.913 | 0.944 | 0.928 | 84 | 8 | 5 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 22 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 1.000 | 0.111 | 0.200 | 2 | 0 | 16 |
| EMAIL | 1.000 | 1.000 | 1.000 | 30 | 0 | 0 |
| IBAN | 1.000 | 1.000 | 1.000 | 12 | 0 | 0 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 56 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 173 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 89 |
| PHONE | 1.000 | 1.000 | 1.000 | 22 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 1 |
