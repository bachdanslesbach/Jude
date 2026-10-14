---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 44-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.690 | 0.910 | **0.785** | 0.815 | 132/613 (22%) | 53/146 | 16 | 0.859 | 541 | 2,445 MB |
| `jude-full-gliner-small` | 0.688 | 0.883 | **0.774** | 0.815 | 129/613 (21%) | 78/190 | 16 | 0.856 | 1,633 | 1,949 MB |
| `jude-full-no-gliner` | 0.690 | 0.846 | **0.760** | 0.812 | 116/613 (19%) | 119/250 | 18 | 0.856 | 2,896 | 2,059 MB |
| `jude-no-public-filter` | 0.601 | 0.865 | **0.709** | 0.773 | 335/613 (55%) | 63/220 | 16 | 0.834 | 658 | 3,423 MB |
| `rules-only` | 0.962 | 0.604 | **0.742** | 0.744 | 18/613 (3%) | 574/644 | 29 | 0.770 | 350,183 | 308 MB |
| `spacy-only` | 0.640 | 0.602 | **0.621** | 0.685 | 247/613 (40%) | 315/647 | 23 | 0.790 | 5,311 | 2,206 MB |
| `regex-only` | 0.956 | 0.148 | **0.257** | 0.257 | 0/613 (0%) | 1337/1386 | 42 | 0.287 | 3,475,995 | 308 MB |

## By corpus split

`dev`: the documents Jude's whitelist and stop-lists were tuned on. `heldout`: added later, never consulted while tuning — the honest number.

| Runner | dev — F1 (P / R, docs) | heldout — F1 (P / R, docs) |
|---|---|---|
| `jude-full` | **0.952** (0.92 / 0.99, 19) | **0.745** (0.64 / 0.89, 25) |
| `jude-full-gliner-small` | **0.941** (0.90 / 0.98, 19) | **0.732** (0.64 / 0.86, 25) |
| `jude-full-no-gliner` | **0.946** (0.92 / 0.97, 19) | **0.714** (0.64 / 0.81, 25) |
| `jude-no-public-filter` | **0.879** (0.80 / 0.98, 19) | **0.667** (0.56 / 0.83, 25) |
| `rules-only` | **0.836** (0.99 / 0.72, 19) | **0.714** (0.95 / 0.57, 25) |
| `spacy-only` | **0.726** (0.78 / 0.68, 19) | **0.593** (0.61 / 0.58, 25) |
| `regex-only` | **0.349** (0.92 / 0.22, 19) | **0.229** (0.98 / 0.13, 25) |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.788 | 0.943 | **0.859** | 967 | 260 | 58 |
| `jude-full-gliner-small` | 0.793 | 0.930 | **0.856** | 953 | 249 | 72 |
| `jude-full-no-gliner` | 0.800 | 0.919 | **0.856** | 942 | 235 | 83 |
| `jude-no-public-filter` | 0.748 | 0.942 | **0.834** | 966 | 326 | 59 |
| `rules-only` | 0.936 | 0.655 | **0.770** | 671 | 46 | 354 |
| `spacy-only` | 0.803 | 0.778 | **0.790** | 797 | 196 | 228 |
| `regex-only` | 0.989 | 0.168 | **0.287** | 172 | 2 | 853 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only |
|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.960 | 1.000 | 0.960 | 1.000 | 0.632 | 0.588 |
| doc_002_credit_facility_en | 0.963 | 0.963 | 0.963 | 0.867 | 0.783 | 0.667 | 0.526 |
| doc_003_solaris_jv_fr | 0.970 | 0.941 | 0.970 | 0.842 | 0.720 | 0.647 | 0.400 |
| doc_005_supply_agreement_en | 1.000 | 1.000 | 1.000 | 0.759 | 0.952 | 0.609 | 0.533 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 0.973 | 0.974 | 0.848 | 0.788 | 0.348 |
| doc_007_patent_litigation_en | 0.846 | 0.830 | 0.863 | 0.917 | 0.829 | 0.829 | 0.296 |
| doc_008_regulatory_submission_en | 0.979 | 0.979 | 0.979 | 0.885 | 0.769 | 0.766 | 0.286 |
| doc_009_witness_statement_en | 0.958 | 0.958 | 0.979 | 0.958 | 0.930 | 0.857 | 0.296 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 |
| doc_011_sanctions_memo_en | 1.000 | 0.968 | 0.968 | 0.769 | 0.929 | 0.667 | 0.400 |
| doc_012_engagement_letter_en | 0.971 | 0.919 | 0.971 | 0.944 | 0.828 | 0.690 | 0.381 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 |
| doc_014_compliance_investigation_en | 0.970 | 0.970 | 0.970 | 0.914 | 0.897 | 0.710 | 0.381 |
| doc_015_corporate_restructuring_en | 0.980 | 0.980 | 0.960 | 0.980 | 0.837 | 0.800 | 0.276 |
| doc_016_tax_memo_en | 0.955 | 0.977 | 1.000 | 0.955 | 0.923 | 0.811 | 0.320 |
| doc_017_data_breach_notification_en | 0.897 | 0.963 | 0.963 | 0.788 | 0.960 | 0.583 | 0.444 |
| doc_018_cease_and_desist_en | 0.875 | 0.875 | 0.875 | 0.848 | 0.783 | 0.692 | 0.333 |
| doc_019_antitrust_complaint_en | 0.963 | 0.926 | 0.926 | 0.794 | 0.791 | 0.694 | 0.267 |
| doc_020_insolvency_update_en | 0.902 | 0.885 | 0.840 | 0.846 | 0.762 | 0.682 | 0.267 |
| doc_021_board_minutes_en | 0.893 | 0.891 | 0.898 | 0.819 | 0.816 | 0.786 | 0.131 |
| doc_022_nda_fr | 0.629 | 0.611 | 0.578 | 0.574 | 0.742 | 0.423 | 0.238 |
| doc_023_form_co_excerpt_en | 0.748 | 0.736 | 0.724 | 0.672 | 0.789 | 0.524 | 0.308 |
| doc_024_dawn_raid_memo_fr | 0.767 | 0.756 | 0.736 | 0.676 | 0.698 | 0.509 | 0.277 |
| doc_025_leniency_marker_en | 0.876 | 0.857 | 0.846 | 0.667 | 0.756 | 0.660 | 0.218 |
| doc_026_rfi_response_fr | 0.689 | 0.696 | 0.690 | 0.656 | 0.843 | 0.476 | 0.157 |
| doc_027_spa_excerpt_en | 0.708 | 0.708 | 0.667 | 0.661 | 0.744 | 0.593 | 0.246 |
| doc_028_client_email_thread_en | 0.877 | 0.832 | 0.839 | 0.839 | 0.514 | 0.653 | 0.267 |
| doc_029_cepani_request_en | 0.842 | 0.839 | 0.759 | 0.845 | 0.641 | 0.680 | 0.207 |
| doc_030_dpia_memo_fr | 0.830 | 0.690 | 0.706 | 0.724 | 0.781 | 0.462 | 0.261 |
| doc_031_dd_redflag_report_en | 0.744 | 0.715 | 0.733 | 0.672 | 0.767 | 0.734 | 0.111 |
| doc_032_conclusions_tribunal_fr | 0.817 | 0.731 | 0.562 | 0.653 | 0.557 | 0.400 | 0.128 |
| doc_033_transaction_fr | 0.633 | 0.622 | 0.606 | 0.628 | 0.730 | 0.421 | 0.298 |
| doc_034_state_aid_complaint_en | 0.642 | 0.636 | 0.642 | 0.617 | 0.700 | 0.674 | 0.190 |
| doc_035_data_room_index_en | 0.769 | 0.777 | 0.800 | 0.741 | 0.868 | 0.667 | 0.275 |
| doc_036_licenciement_motif_grave_fr | 0.734 | 0.759 | 0.680 | 0.716 | 0.754 | 0.494 | 0.377 |
| doc_037_merger_thresholds_memo_en | 0.810 | 0.784 | 0.816 | 0.690 | 0.753 | 0.592 | 0.277 |
| doc_038_reponse_apd_plainte_fr | 0.660 | 0.682 | 0.595 | 0.549 | 0.780 | 0.317 | 0.326 |
| doc_039_contrat_franchise_extrait_fr | 0.592 | 0.583 | 0.592 | 0.578 | 0.865 | 0.527 | 0.286 |
| doc_040_interview_notes_en | 0.730 | 0.775 | 0.637 | 0.398 | 0.455 | 0.600 | 0.050 |
| doc_041_shareholders_agreement_excerpt_en | 0.727 | 0.637 | 0.724 | 0.562 | 0.737 | 0.779 | 0.208 |
| doc_042_settlement_submission_en | 0.840 | 0.800 | 0.805 | 0.717 | 0.661 | 0.760 | 0.128 |
| doc_043_mise_en_demeure_fr | 0.574 | 0.644 | 0.682 | 0.594 | 0.738 | 0.417 | 0.327 |
| doc_044_fil_emails_budget_fr | 0.752 | 0.761 | 0.721 | 0.759 | 0.500 | 0.536 | 0.317 |
| doc_045_escrow_agreement_excerpt_en | 0.719 | 0.740 | 0.698 | 0.719 | 0.732 | 0.645 | 0.225 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.786 | 0.655 | 0.714 | 55 | 15 | 29 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.907 | 0.807 | 0.854 | 117 | 12 | 28 |
| ORG | 0.568 | 0.962 | 0.714 | 633 | 481 | 25 |
| PERSON | 0.733 | 0.923 | 0.817 | 432 | 157 | 36 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-gliner-small — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.923 | 0.429 | 0.585 | 36 | 3 | 48 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.807 | 0.807 | 0.807 | 117 | 28 | 28 |
| ORG | 0.574 | 0.922 | 0.707 | 607 | 451 | 51 |
| PERSON | 0.719 | 0.925 | 0.809 | 433 | 169 | 35 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-full-no-gliner — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.929 | 0.310 | 0.464 | 26 | 2 | 58 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.914 | 0.731 | 0.812 | 106 | 10 | 39 |
| ORG | 0.555 | 0.875 | 0.679 | 576 | 462 | 82 |
| PERSON | 0.747 | 0.908 | 0.820 | 425 | 144 | 43 |
| PHONE | 1.000 | 1.000 | 1.000 | 84 | 0 | 0 |
| URL | 1.000 | 1.000 | 1.000 | 29 | 0 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.786 | 0.655 | 0.714 | 55 | 15 | 29 |
| EMAIL | 1.000 | 1.000 | 1.000 | 99 | 0 | 0 |
| IBAN | 1.000 | 0.533 | 0.696 | 32 | 0 | 28 |
| LOC | 0.900 | 0.807 | 0.851 | 117 | 13 | 28 |
| ORG | 0.447 | 0.880 | 0.593 | 579 | 717 | 79 |
| PERSON | 0.683 | 0.880 | 0.769 | 412 | 191 | 56 |
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
| LOC | 0.843 | 0.483 | 0.614 | 70 | 13 | 75 |
| ORG | 0.529 | 0.742 | 0.617 | 488 | 435 | 170 |
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
