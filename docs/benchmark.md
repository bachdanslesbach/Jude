---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 44-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.678 | 0.916 | **0.779** | 0.815 | 151/612 (25%) | 38/149 | 12 | 0.864 | 622 | 2,612 MB |
| `jude-full-gliner-small` | 0.673 | 0.885 | **0.764** | 0.815 | 146/612 (24%) | 63/204 | 13 | 0.863 | 1,716 | 2,451 MB |
| `jude-full-no-gliner` | 0.663 | 0.852 | **0.745** | 0.806 | 143/612 (23%) | 97/263 | 13 | 0.859 | 3,001 | 3,037 MB |
| `jude-no-public-filter` | 0.575 | 0.869 | **0.692** | 0.762 | 436/612 (71%) | 45/232 | 11 | 0.836 | 724 | 3,506 MB |
| `rules-only` | 0.963 | 0.554 | **0.704** | 0.705 | 18/612 (3%) | 709/791 | 29 | 0.758 | 350,118 | 308 MB |
| `spacy-only` | 0.584 | 0.630 | **0.606** | 0.680 | 353/612 (58%) | 285/657 | 19 | 0.793 | 5,515 | 3,030 MB |
| `regex-only` | 0.956 | 0.136 | **0.238** | 0.238 | 0/612 (0%) | 1476/1534 | 42 | 0.278 | 3,453,664 | 308 MB |

## By corpus split

`dev`: the documents Jude's whitelist and stop-lists were tuned on. `heldout`: added later, never consulted while tuning — the honest number.

| Runner | dev — F1 (P / R, docs) | heldout — F1 (P / R, docs) |
|---|---|---|
| `jude-full` | **0.963** (0.93 / 1.00, 19) | **0.735** (0.62 / 0.89, 25) |
| `jude-full-gliner-small` | **0.960** (0.93 / 0.99, 19) | **0.716** (0.62 / 0.85, 25) |
| `jude-full-no-gliner` | **0.960** (0.94 / 0.98, 19) | **0.693** (0.60 / 0.82, 25) |
| `jude-no-public-filter` | **0.859** (0.76 / 0.98, 19) | **0.650** (0.53 / 0.84, 25) |
| `rules-only` | **0.790** (0.99 / 0.66, 19) | **0.678** (0.95 / 0.53, 25) |
| `spacy-only` | **0.730** (0.75 / 0.72, 19) | **0.573** (0.54 / 0.61, 25) |
| `regex-only` | **0.321** (0.92 / 0.19, 19) | **0.212** (0.98 / 0.12, 25) |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.797 | 0.944 | **0.864** | 1003 | 256 | 60 |
| `jude-full-gliner-small` | 0.801 | 0.936 | **0.863** | 995 | 247 | 68 |
| `jude-full-no-gliner` | 0.803 | 0.924 | **0.859** | 982 | 241 | 81 |
| `jude-no-public-filter` | 0.749 | 0.945 | **0.836** | 1005 | 337 | 58 |
| `rules-only` | 0.941 | 0.635 | **0.758** | 675 | 42 | 388 |
| `spacy-only` | 0.792 | 0.795 | **0.793** | 845 | 222 | 218 |
| `regex-only` | 0.989 | 0.162 | **0.278** | 172 | 2 | 891 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only |
|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 1.000 | 0.963 | 0.966 | 0.923 | 0.636 | 0.526 |
| doc_002_credit_facility_en | 0.929 | 0.929 | 0.929 | 0.875 | 0.750 | 0.692 | 0.500 |
| doc_003_solaris_jv_fr | 0.927 | 0.927 | 0.927 | 0.826 | 0.643 | 0.667 | 0.348 |
| doc_005_supply_agreement_en | 1.000 | 1.000 | 1.000 | 0.765 | 0.870 | 0.643 | 0.471 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 1.000 | 0.974 | 0.848 | 0.824 | 0.348 |
| doc_007_patent_litigation_en | 0.984 | 0.984 | 0.968 | 0.806 | 0.735 | 0.679 | 0.229 |
| doc_008_regulatory_submission_en | 1.000 | 1.000 | 1.000 | 0.912 | 0.732 | 0.808 | 0.267 |
| doc_009_witness_statement_en | 0.960 | 0.960 | 0.980 | 0.923 | 0.909 | 0.826 | 0.286 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 1.000 | 0.973 | 0.973 | 0.766 | 0.839 | 0.683 | 0.348 |
| doc_012_engagement_letter_en | 0.976 | 0.952 | 0.976 | 0.870 | 0.750 | 0.667 | 0.333 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 |
| doc_014_compliance_investigation_en | 0.976 | 0.976 | 0.976 | 0.909 | 0.788 | 0.769 | 0.320 |
| doc_015_corporate_restructuring_en | 0.963 | 0.981 | 0.981 | 0.897 | 0.818 | 0.784 | 0.267 |
| doc_016_tax_memo_en | 0.902 | 0.958 | 1.000 | 0.821 | 0.878 | 0.739 | 0.296 |
| doc_017_data_breach_notification_en | 0.909 | 0.968 | 0.933 | 0.789 | 0.889 | 0.621 | 0.400 |
| doc_018_cease_and_desist_en | 0.895 | 0.872 | 0.895 | 0.850 | 0.692 | 0.765 | 0.286 |
| doc_019_antitrust_complaint_en | 0.982 | 0.945 | 0.945 | 0.800 | 0.773 | 0.706 | 0.258 |
| doc_020_insolvency_update_en | 0.963 | 0.945 | 0.906 | 0.909 | 0.762 | 0.792 | 0.267 |
| doc_021_board_minutes_en | 0.899 | 0.905 | 0.872 | 0.828 | 0.748 | 0.785 | 0.114 |
| doc_022_nda_fr | 0.590 | 0.539 | 0.500 | 0.562 | 0.687 | 0.405 | 0.213 |
| doc_023_form_co_excerpt_en | 0.786 | 0.779 | 0.779 | 0.688 | 0.769 | 0.563 | 0.296 |
| doc_024_dawn_raid_memo_fr | 0.775 | 0.750 | 0.721 | 0.685 | 0.659 | 0.508 | 0.257 |
| doc_025_leniency_marker_en | 0.894 | 0.862 | 0.852 | 0.706 | 0.681 | 0.689 | 0.188 |
| doc_026_rfi_response_fr | 0.597 | 0.582 | 0.582 | 0.557 | 0.843 | 0.400 | 0.157 |
| doc_027_spa_excerpt_en | 0.748 | 0.721 | 0.699 | 0.687 | 0.719 | 0.629 | 0.233 |
| doc_028_client_email_thread_en | 0.882 | 0.762 | 0.778 | 0.812 | 0.450 | 0.612 | 0.229 |
| doc_029_cepani_request_en | 0.768 | 0.774 | 0.706 | 0.726 | 0.641 | 0.609 | 0.207 |
| doc_030_dpia_memo_fr | 0.823 | 0.748 | 0.730 | 0.734 | 0.633 | 0.550 | 0.197 |
| doc_031_dd_redflag_report_en | 0.775 | 0.741 | 0.731 | 0.694 | 0.695 | 0.721 | 0.095 |
| doc_032_conclusions_tribunal_fr | 0.734 | 0.679 | 0.561 | 0.596 | 0.515 | 0.408 | 0.115 |
| doc_033_transaction_fr | 0.580 | 0.574 | 0.488 | 0.571 | 0.730 | 0.314 | 0.298 |
| doc_034_state_aid_complaint_en | 0.677 | 0.678 | 0.678 | 0.633 | 0.627 | 0.655 | 0.163 |
| doc_035_data_room_index_en | 0.842 | 0.850 | 0.873 | 0.800 | 0.805 | 0.688 | 0.246 |
| doc_036_licenciement_motif_grave_fr | 0.667 | 0.689 | 0.609 | 0.650 | 0.732 | 0.433 | 0.364 |
| doc_037_merger_thresholds_memo_en | 0.803 | 0.794 | 0.818 | 0.561 | 0.729 | 0.519 | 0.265 |
| doc_038_reponse_apd_plainte_fr | 0.594 | 0.617 | 0.559 | 0.514 | 0.767 | 0.297 | 0.318 |
| doc_039_contrat_franchise_extrait_fr | 0.528 | 0.521 | 0.524 | 0.514 | 0.853 | 0.427 | 0.280 |
| doc_040_interview_notes_en | 0.760 | 0.807 | 0.667 | 0.461 | 0.426 | 0.624 | 0.046 |
| doc_041_shareholders_agreement_excerpt_en | 0.736 | 0.645 | 0.729 | 0.561 | 0.718 | 0.766 | 0.200 |
| doc_042_settlement_submission_en | 0.851 | 0.807 | 0.787 | 0.740 | 0.614 | 0.757 | 0.115 |
| doc_043_mise_en_demeure_fr | 0.561 | 0.630 | 0.630 | 0.561 | 0.787 | 0.390 | 0.356 |
| doc_044_fil_emails_budget_fr | 0.667 | 0.663 | 0.634 | 0.659 | 0.500 | 0.496 | 0.317 |
| doc_045_escrow_agreement_excerpt_en | 0.773 | 0.745 | 0.725 | 0.764 | 0.714 | 0.676 | 0.217 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.800 | 0.650 | 0.717 | 52 | 13 | 28 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.560 | 0.948 | 0.704 | 235 | 185 | 13 |
| ORG | 0.600 | 0.941 | 0.732 | 665 | 444 | 42 |
| PERSON | 0.768 | 0.919 | 0.837 | 430 | 130 | 38 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-gliner-small — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.947 | 0.450 | 0.610 | 36 | 2 | 44 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.517 | 0.923 | 0.663 | 229 | 214 | 19 |
| ORG | 0.610 | 0.893 | 0.725 | 631 | 403 | 76 |
| PERSON | 0.747 | 0.921 | 0.825 | 431 | 146 | 37 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-no-gliner — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.929 | 0.325 | 0.481 | 26 | 2 | 54 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.494 | 0.883 | 0.634 | 219 | 224 | 29 |
| ORG | 0.587 | 0.849 | 0.694 | 600 | 422 | 107 |
| PERSON | 0.776 | 0.904 | 0.835 | 423 | 122 | 45 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.797 | 0.637 | 0.708 | 51 | 13 | 29 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.455 | 0.952 | 0.615 | 236 | 283 | 12 |
| ORG | 0.465 | 0.853 | 0.602 | 603 | 693 | 104 |
| PERSON | 0.729 | 0.874 | 0.795 | 409 | 152 | 59 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### rules-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.929 | 0.325 | 0.481 | 26 | 2 | 54 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.957 | 0.355 | 0.518 | 88 | 4 | 160 |
| ORG | 0.918 | 0.505 | 0.651 | 357 | 32 | 350 |
| PERSON | 1.000 | 0.575 | 0.730 | 269 | 0 | 199 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.421 | 0.790 | 0.549 | 196 | 270 | 52 |
| ORG | 0.541 | 0.707 | 0.613 | 500 | 424 | 207 |
| PERSON | 0.804 | 0.902 | 0.850 | 422 | 103 | 46 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.703 | 0.325 | 0.444 | 26 | 11 | 54 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 248 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 707 |
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
