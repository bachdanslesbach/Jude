---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 44-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.623 | 0.918 | **0.742** | 0.774 | 151/613 (25%) | 34/134 | 12 | 0.848 | 622 | 2,612 MB |
| `jude-full-gliner-small` | 0.619 | 0.889 | **0.730** | 0.776 | 146/613 (24%) | 56/180 | 13 | 0.847 | 1,716 | 2,451 MB |
| `jude-full-no-gliner` | 0.612 | 0.859 | **0.715** | 0.768 | 143/613 (23%) | 86/230 | 13 | 0.844 | 3,001 | 3,037 MB |
| `jude-no-public-filter` | 0.528 | 0.870 | **0.657** | 0.724 | 437/613 (71%) | 37/211 | 11 | 0.819 | 724 | 3,506 MB |
| `rules-only` | 0.962 | 0.604 | **0.742** | 0.744 | 18/613 (3%) | 574/644 | 29 | 0.770 | 350,118 | 308 MB |
| `spacy-only` | 0.530 | 0.623 | **0.573** | 0.643 | 354/613 (58%) | 256/613 | 19 | 0.786 | 5,515 | 3,030 MB |
| `regex-only` | 0.956 | 0.148 | **0.257** | 0.257 | 0/613 (0%) | 1337/1386 | 42 | 0.287 | 3,453,664 | 308 MB |

## By corpus split

`dev`: the documents Jude's whitelist and stop-lists were tuned on. `heldout`: added later, never consulted while tuning — the honest number.

| Runner | dev — F1 (P / R, docs) | heldout — F1 (P / R, docs) |
|---|---|---|
| `jude-full` | **0.914** (0.84 / 1.00, 19) | **0.701** (0.58 / 0.89, 25) |
| `jude-full-gliner-small` | **0.911** (0.84 / 0.99, 19) | **0.687** (0.57 / 0.86, 25) |
| `jude-full-no-gliner` | **0.916** (0.85 / 0.99, 19) | **0.666** (0.56 / 0.82, 25) |
| `jude-no-public-filter` | **0.820** (0.70 / 0.99, 19) | **0.617** (0.49 / 0.84, 25) |
| `rules-only` | **0.836** (0.99 / 0.72, 19) | **0.714** (0.95 / 0.57, 25) |
| `spacy-only` | **0.683** (0.66 / 0.70, 19) | **0.544** (0.50 / 0.60, 25) |
| `regex-only` | **0.349** (0.92 / 0.22, 19) | **0.229** (0.98 / 0.13, 25) |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.769 | 0.944 | **0.848** | 968 | 291 | 57 |
| `jude-full-gliner-small` | 0.773 | 0.937 | **0.847** | 960 | 282 | 65 |
| `jude-full-no-gliner` | 0.776 | 0.926 | **0.844** | 949 | 274 | 76 |
| `jude-no-public-filter` | 0.722 | 0.945 | **0.819** | 969 | 373 | 56 |
| `rules-only` | 0.936 | 0.655 | **0.770** | 671 | 46 | 354 |
| `spacy-only` | 0.770 | 0.802 | **0.786** | 822 | 245 | 203 |
| `regex-only` | 0.989 | 0.168 | **0.287** | 172 | 2 | 853 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only |
|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 0.923 | 0.923 | 0.960 | 0.889 | 1.000 | 0.600 | 0.588 |
| doc_002_credit_facility_en | 0.963 | 0.963 | 0.963 | 0.839 | 0.783 | 0.640 | 0.526 |
| doc_003_solaris_jv_fr | 0.842 | 0.842 | 0.842 | 0.744 | 0.720 | 0.564 | 0.400 |
| doc_005_supply_agreement_en | 0.917 | 0.917 | 0.917 | 0.688 | 0.952 | 0.538 | 0.533 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 1.000 | 0.974 | 0.848 | 0.824 | 0.348 |
| doc_007_patent_litigation_en | 0.830 | 0.830 | 0.815 | 0.815 | 0.829 | 0.708 | 0.296 |
| doc_008_regulatory_submission_en | 0.960 | 0.960 | 0.960 | 0.873 | 0.769 | 0.760 | 0.286 |
| doc_009_witness_statement_en | 0.939 | 0.939 | 0.958 | 0.902 | 0.930 | 0.800 | 0.296 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 0.909 | 0.882 | 0.882 | 0.682 | 0.929 | 0.579 | 0.400 |
| doc_012_engagement_letter_en | 0.895 | 0.872 | 0.895 | 0.791 | 0.828 | 0.556 | 0.381 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 |
| doc_014_compliance_investigation_en | 0.865 | 0.865 | 0.865 | 0.800 | 0.897 | 0.629 | 0.381 |
| doc_015_corporate_restructuring_en | 0.943 | 0.962 | 0.962 | 0.877 | 0.837 | 0.760 | 0.276 |
| doc_016_tax_memo_en | 0.857 | 0.913 | 0.955 | 0.778 | 0.923 | 0.682 | 0.320 |
| doc_017_data_breach_notification_en | 0.839 | 0.897 | 0.929 | 0.722 | 0.960 | 0.519 | 0.444 |
| doc_018_cease_and_desist_en | 0.800 | 0.778 | 0.800 | 0.757 | 0.783 | 0.645 | 0.333 |
| doc_019_antitrust_complaint_en | 0.963 | 0.926 | 0.926 | 0.781 | 0.791 | 0.680 | 0.267 |
| doc_020_insolvency_update_en | 0.963 | 0.945 | 0.906 | 0.909 | 0.762 | 0.792 | 0.267 |
| doc_021_board_minutes_en | 0.837 | 0.828 | 0.855 | 0.765 | 0.816 | 0.727 | 0.131 |
| doc_022_nda_fr | 0.564 | 0.527 | 0.486 | 0.534 | 0.742 | 0.380 | 0.238 |
| doc_023_form_co_excerpt_en | 0.764 | 0.757 | 0.757 | 0.667 | 0.789 | 0.553 | 0.308 |
| doc_024_dawn_raid_memo_fr | 0.745 | 0.733 | 0.702 | 0.652 | 0.698 | 0.479 | 0.277 |
| doc_025_leniency_marker_en | 0.807 | 0.772 | 0.761 | 0.614 | 0.756 | 0.602 | 0.218 |
| doc_026_rfi_response_fr | 0.597 | 0.582 | 0.582 | 0.557 | 0.843 | 0.400 | 0.157 |
| doc_027_spa_excerpt_en | 0.733 | 0.739 | 0.717 | 0.672 | 0.744 | 0.647 | 0.246 |
| doc_028_client_email_thread_en | 0.855 | 0.793 | 0.793 | 0.813 | 0.514 | 0.595 | 0.267 |
| doc_029_cepani_request_en | 0.768 | 0.774 | 0.706 | 0.726 | 0.641 | 0.609 | 0.207 |
| doc_030_dpia_memo_fr | 0.716 | 0.620 | 0.600 | 0.629 | 0.781 | 0.383 | 0.261 |
| doc_031_dd_redflag_report_en | 0.722 | 0.698 | 0.704 | 0.652 | 0.767 | 0.708 | 0.111 |
| doc_032_conclusions_tribunal_fr | 0.673 | 0.615 | 0.490 | 0.532 | 0.557 | 0.327 | 0.128 |
| doc_033_transaction_fr | 0.580 | 0.574 | 0.488 | 0.571 | 0.730 | 0.314 | 0.298 |
| doc_034_state_aid_complaint_en | 0.598 | 0.596 | 0.596 | 0.561 | 0.700 | 0.583 | 0.190 |
| doc_035_data_room_index_en | 0.778 | 0.785 | 0.808 | 0.737 | 0.868 | 0.644 | 0.275 |
| doc_036_licenciement_motif_grave_fr | 0.678 | 0.701 | 0.619 | 0.661 | 0.754 | 0.442 | 0.377 |
| doc_037_merger_thresholds_memo_en | 0.775 | 0.766 | 0.791 | 0.536 | 0.753 | 0.517 | 0.277 |
| doc_038_reponse_apd_plainte_fr | 0.580 | 0.602 | 0.543 | 0.500 | 0.780 | 0.274 | 0.326 |
| doc_039_contrat_franchise_extrait_fr | 0.517 | 0.510 | 0.514 | 0.503 | 0.865 | 0.414 | 0.286 |
| doc_040_interview_notes_en | 0.720 | 0.756 | 0.634 | 0.398 | 0.455 | 0.590 | 0.050 |
| doc_041_shareholders_agreement_excerpt_en | 0.715 | 0.623 | 0.708 | 0.538 | 0.737 | 0.768 | 0.208 |
| doc_042_settlement_submission_en | 0.791 | 0.767 | 0.757 | 0.678 | 0.661 | 0.725 | 0.128 |
| doc_043_mise_en_demeure_fr | 0.541 | 0.604 | 0.604 | 0.541 | 0.738 | 0.370 | 0.327 |
| doc_044_fil_emails_budget_fr | 0.667 | 0.663 | 0.634 | 0.659 | 0.500 | 0.496 | 0.317 |
| doc_045_escrow_agreement_excerpt_en | 0.762 | 0.734 | 0.713 | 0.753 | 0.732 | 0.662 | 0.225 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.800 | 0.619 | 0.698 | 52 | 13 | 32 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.329 | 0.952 | 0.488 | 138 | 282 | 7 |
| ORG | 0.567 | 0.956 | 0.712 | 629 | 480 | 29 |
| PERSON | 0.768 | 0.919 | 0.837 | 430 | 130 | 38 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-gliner-small — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.947 | 0.429 | 0.590 | 36 | 2 | 48 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.302 | 0.924 | 0.456 | 134 | 309 | 11 |
| ORG | 0.582 | 0.915 | 0.712 | 602 | 432 | 56 |
| PERSON | 0.747 | 0.921 | 0.825 | 431 | 146 | 37 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-no-gliner — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.929 | 0.310 | 0.464 | 26 | 2 | 58 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.298 | 0.910 | 0.449 | 132 | 311 | 13 |
| ORG | 0.560 | 0.869 | 0.681 | 572 | 450 | 86 |
| PERSON | 0.776 | 0.904 | 0.835 | 423 | 122 | 45 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.797 | 0.607 | 0.689 | 51 | 13 | 33 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.266 | 0.952 | 0.416 | 138 | 381 | 7 |
| ORG | 0.443 | 0.872 | 0.588 | 574 | 722 | 84 |
| PERSON | 0.729 | 0.874 | 0.795 | 409 | 152 | 59 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### rules-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.929 | 0.310 | 0.464 | 26 | 2 | 58 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.957 | 0.607 | 0.743 | 88 | 4 | 57 |
| ORG | 0.915 | 0.541 | 0.680 | 356 | 33 | 302 |
| PERSON | 1.000 | 0.575 | 0.730 | 269 | 0 | 199 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.223 | 0.717 | 0.340 | 104 | 362 | 41 |
| ORG | 0.528 | 0.742 | 0.617 | 488 | 436 | 170 |
| PERSON | 0.804 | 0.902 | 0.850 | 422 | 103 | 46 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.703 | 0.310 | 0.430 | 26 | 11 | 58 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 145 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 658 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 468 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-full-gliner-small`** — device cpu; load 0.0 s.
- **`jude-full-no-gliner`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`rules-only`** — device cpu; load 0.1 s.
  - Deterministic layers only: regex + patterns + known entities + whitelist.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
