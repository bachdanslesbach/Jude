---
title: Jude redaction benchmark
layout: default
---

# Jude redaction benchmark

Span-level F1 across the 58-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `jude-full` | 0.688 | 0.900 | **0.780** | 0.811 | 347/1466 (24%) | 73/234 | 16 | 0.854 | 550 | 2,494 MB |
| `jude-full-gliner-small` | 0.684 | 0.872 | **0.767** | 0.803 | 350/1466 (24%) | 115/300 | 16 | 0.847 | 1,601 | 1,834 MB |
| `jude-full-no-gliner` | 0.689 | 0.837 | **0.756** | 0.802 | 311/1466 (21%) | 168/384 | 18 | 0.848 | 2,677 | 1,300 MB |
| `jude-no-public-filter` | 0.612 | 0.859 | **0.715** | 0.778 | 574/1466 (39%) | 83/331 | 16 | 0.836 | 525 | 3,334 MB |
| `rules-only` | 0.950 | 0.473 | **0.632** | 0.633 | 36/1466 (2%) | 1096/1239 | 32 | 0.672 | 346,220 | 290 MB |
| `spacy-only` | 0.672 | 0.652 | **0.661** | 0.718 | 391/1466 (27%) | 406/819 | 23 | 0.799 | 4,930 | 1,234 MB |
| `regex-only` | 0.949 | 0.111 | **0.198** | 0.198 | 3/1466 (0%) | 1981/2091 | 44 | 0.221 | 3,465,718 | 289 MB |

## By corpus split

`dev`: the documents Jude's whitelist and stop-lists were tuned on. `heldout`: added later, never consulted while tuning — the honest number.

| Runner | dev — F1 (P / R, docs) | heldout — F1 (P / R, docs) | public — F1 (P / R, docs) |
|---|---|---|---|
| `jude-full` | **0.952** (0.92 / 0.99, 19) | **0.745** (0.64 / 0.89, 25) | **0.768** (0.68 / 0.88, 14) |
| `jude-full-gliner-small` | **0.941** (0.90 / 0.98, 19) | **0.732** (0.64 / 0.86, 25) | **0.751** (0.67 / 0.85, 14) |
| `jude-full-no-gliner` | **0.946** (0.92 / 0.97, 19) | **0.714** (0.64 / 0.81, 25) | **0.744** (0.69 / 0.81, 14) |
| `jude-no-public-filter` | **0.879** (0.80 / 0.98, 19) | **0.667** (0.56 / 0.83, 25) | **0.730** (0.64 / 0.85, 14) |
| `rules-only` | **0.836** (0.99 / 0.72, 19) | **0.714** (0.95 / 0.57, 25) | **0.296** (0.87 / 0.18, 14) |
| `spacy-only` | **0.726** (0.78 / 0.68, 19) | **0.593** (0.61 / 0.58, 25) | **0.749** (0.74 / 0.76, 14) |
| `regex-only` | **0.349** (0.92 / 0.22, 19) | **0.229** (0.98 / 0.13, 25) | **0.051** (0.86 / 0.03, 14) |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `jude-full` | 0.782 | 0.940 | **0.854** | 1442 | 401 | 92 |
| `jude-full-gliner-small` | 0.783 | 0.923 | **0.847** | 1416 | 393 | 118 |
| `jude-full-no-gliner` | 0.795 | 0.909 | **0.848** | 1394 | 359 | 140 |
| `jude-no-public-filter` | 0.752 | 0.942 | **0.836** | 1445 | 477 | 89 |
| `rules-only` | 0.936 | 0.524 | **0.672** | 804 | 55 | 730 |
| `spacy-only` | 0.807 | 0.790 | **0.799** | 1212 | 289 | 322 |
| `regex-only` | 0.974 | 0.125 | **0.221** | 191 | 5 | 1343 |

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
| doc_101_commercial_2026_central_termica_v_santan_en | 0.829 | 0.807 | 0.815 | 0.807 | 0.537 | 0.828 | 0.043 |
| doc_102_commercial_2026_intralinks_v_nexans_en | 0.712 | 0.699 | 0.706 | 0.685 | 0.386 | 0.810 | 0.050 |
| doc_103_chancery_2026_glencore_v_prax_lindsey_en | 0.771 | 0.759 | 0.748 | 0.778 | 0.545 | 0.848 | 0.045 |
| doc_104_chancery_2026_nocopyrightsounds_v_aei_mu_en | 0.943 | 0.920 | 0.916 | 0.932 | 0.292 | 0.892 | 0.048 |
| doc_105_coa_2026_rasmala_v_trafigura_en | 0.967 | 0.918 | 0.949 | 0.952 | 0.356 | 0.914 | 0.033 |
| doc_106_ca3_2026_sandoz_v_united_therapeutics_en | 0.827 | 0.841 | 0.785 | 0.822 | 0.240 | 0.850 | 0.022 |
| doc_107_ca6_2026_trustees_main_v_appliancesmart_en | 0.939 | 0.895 | 0.906 | 0.939 | 0.089 | 0.921 | 0.000 |
| doc_108_cafc_2026_alexsam_v_simon_property_group_en | 0.738 | 0.768 | 0.768 | 0.556 | 0.129 | 0.744 | 0.023 |
| doc_109_cass_2023_international_tools_service_v__fr | 0.465 | 0.500 | 0.541 | 0.465 | 0.250 | 0.533 | 0.133 |
| doc_110_cass_2025_ville_de_virton_v_trema_archit_fr | 0.642 | 0.642 | 0.739 | 0.642 | 0.182 | 0.762 | 0.095 |
| doc_111_cass_2025_g_v_etat_belge_fr | 0.732 | 0.698 | 0.811 | 0.732 | 0.300 | 0.757 | 0.111 |
| doc_112_cc_2026_rossel_ipm_fr | 0.731 | 0.739 | 0.670 | 0.660 | 0.418 | 0.551 | 0.149 |
| doc_113_rpr_2026_rfb_v_urbsfa_fr | 0.638 | 0.561 | 0.507 | 0.623 | 0.061 | 0.477 | 0.031 |
| doc_114_ccs_2026_rmga_pierre_joel_aag_fr | 0.532 | 0.500 | 0.509 | 0.496 | 0.364 | 0.510 | 0.054 |

## Per entity type

### jude-full — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.796 | 0.638 | 0.709 | 90 | 23 | 51 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.812 | 0.826 | 0.819 | 138 | 32 | 29 |
| ORG | 0.614 | 0.951 | 0.746 | 1077 | 678 | 55 |
| PERSON | 0.714 | 0.917 | 0.803 | 562 | 225 | 51 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.967 | 1.000 | 0.983 | 29 | 1 | 0 |

### jude-full-gliner-small — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.947 | 0.383 | 0.545 | 54 | 3 | 87 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.730 | 0.808 | 0.767 | 135 | 50 | 32 |
| ORG | 0.612 | 0.928 | 0.738 | 1050 | 665 | 82 |
| PERSON | 0.712 | 0.917 | 0.802 | 562 | 227 | 51 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.967 | 1.000 | 0.983 | 29 | 1 | 0 |

### jude-full-no-gliner — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.951 | 0.277 | 0.429 | 39 | 2 | 102 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.813 | 0.731 | 0.770 | 122 | 28 | 45 |
| ORG | 0.603 | 0.886 | 0.718 | 1003 | 660 | 129 |
| PERSON | 0.738 | 0.902 | 0.812 | 553 | 196 | 60 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.967 | 1.000 | 0.983 | 29 | 1 | 0 |

### jude-no-public-filter — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.796 | 0.638 | 0.709 | 90 | 23 | 51 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.812 | 0.826 | 0.819 | 138 | 32 | 29 |
| ORG | 0.516 | 0.883 | 0.651 | 1000 | 939 | 132 |
| PERSON | 0.659 | 0.884 | 0.755 | 542 | 281 | 71 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.967 | 1.000 | 0.983 | 29 | 1 | 0 |

### rules-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.951 | 0.277 | 0.429 | 39 | 2 | 102 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.958 | 0.545 | 0.695 | 91 | 4 | 76 |
| ORG | 0.901 | 0.387 | 0.541 | 438 | 48 | 694 |
| PERSON | 0.997 | 0.480 | 0.648 | 294 | 1 | 319 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.967 | 1.000 | 0.983 | 29 | 1 | 0 |

### spacy-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 141 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 101 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| LOC | 0.724 | 0.503 | 0.594 | 84 | 32 | 83 |
| ORG | 0.607 | 0.783 | 0.684 | 886 | 574 | 246 |
| PERSON | 0.797 | 0.917 | 0.853 | 562 | 143 | 51 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 88 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### regex-only — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.780 | 0.277 | 0.408 | 39 | 11 | 102 |
| EMAIL | 0.990 | 1.000 | 0.995 | 101 | 1 | 0 |
| IBAN | 1.000 | 0.400 | 0.571 | 32 | 0 | 48 |
| LOC | 0.000 | 0.000 | 0.000 | 0 | 0 | 167 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 1132 |
| PERSON | 0.000 | 0.000 | 0.000 | 0 | 0 | 613 |
| PHONE | 0.989 | 1.000 | 0.994 | 88 | 1 | 0 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 1 | 29 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-full-gliner-small`** — device cpu; load 0.0 s.
- **`jude-full-no-gliner`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`rules-only`** — device cpu; load 0.1 s.
  - Deterministic layers only: regex + patterns + known entities + whitelist.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
