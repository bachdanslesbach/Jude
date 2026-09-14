---
title: PII models on legal documents
layout: default
---

# PII models on legal documents

## Why this comparison exists

Generic PII detectors are built for chat logs, support tickets and
customer forms. Legal anonymisation is a different task, in three
ways that the numbers below make concrete:

1. **The parties are organisations.** In a competition or M&A file the
   identifying information is *which companies* are involved, far more
   than which individuals. A detector without an organisation label
   cannot do the job, whatever its score on names and e-mails.
2. **The regulatory framing must survive.** A memo in which every
   mention of the European Commission, the Bundeskartellamt, the DMA or
   Article 102 TFEU has become `Org7` is useless to the model that
   receives it — and none of that framing identifies the client. The
   *public-body over-redaction* column measures this directly.
3. **Case references and internal dockets are identifiers.**
   `Case T-203/24`, `1:26-cv-00489-RGA`, `IPR2025-00712`, `M-2026-PIO-001`
   identify a matter as surely as a name does. No generic PII taxonomy
   has a label for them.

Beyond those, legal documents are long (two pages is short), routinely
multilingual in Brussels practice (EN/FR/NL in one file), and refer to
the same person under several surface forms — all of which a
span-level model sees nothing of.

## Systems compared

| System | What it is | Params | Labels | Languages | Licence |
|---|---|---|---|---|---|
| `jude-full` | Jude's shipped pipeline: regex + spaCy `en_core_web_trf` + GLiNER large (legal labels) + per-matter dictionary, two-pass, public-knowledge whitelist | ~0.9 B across models | Jude schema (PERSON, ORG, LOC, EMAIL, PHONE, IBAN, CASE_REF, URL, SECRET) | EN / FR / NL routed per paragraph | MIT |
| `jude-no-public-filter` | Same, whitelist disabled (ablation) | — | — | — | — |
| `spacy-only` / `regex-only` | Single-layer ablations | — | — | — | — |
| `gliner-large-v2.1-jude-labels` | The base GLiNER checkpoint Jude uses, alone, with Jude's legal labels | ~0.45 B | zero-shot | EN | Apache-2.0 |
| `nvidia-gliner-pii-native` | `nvidia/gliner-PII`: GLiNER large fine-tuned on 100k synthetic Nemotron-PII records (55 categories, US + international formats), queried with the 18 native labels that map onto Jude's schema, thresholds 0.5 and 0.3 | ~0.45 B | 55 native | EN only | NVIDIA Open Model License |
| `nvidia-gliner-pii-jude-labels` | Same checkpoint queried with Jude's legal labels — isolates the effect of the PII fine-tune from the label set | ~0.45 B | zero-shot | EN | — |
| `pplx-pii-masking` | `perplexity-ai/pplx-pii-masking`: bidirectional Qwen3 encoder, BIOES token head + Viterbi decoder, 4096-token window | 0.60 B | 9 (`private_person`, `private_email`, `private_phone`, `private_address`, `private_url`, `private_date`, `account_number`, `secret`, `other_pii`) | EN + multilingual (card) | MIT, `trust_remote_code` (reviewed, pinned) |
| `roblox-pii-classifier` | XLM-RoBERTa-large message classifier: *asking for* / *giving* PII, no spans | 0.56 B | 2 | multilingual | Apache-2.0 |

Model revisions are pinned in the runner sources and listed under
*Runner notes*.

## Protocol

* **Corpus.** 44 gold-annotated documents in `benchmark/corpus/`
  (1,775 spans), English and French, in two splits. `dev` (19
  documents: term sheets, credit facilities, witness statements,
  regulatory submissions, sanctions memos, engagement letters, patent
  and antitrust pleadings, insolvency updates) is the set Jude's
  whitelist and stop-lists were tuned on. `heldout` (25 documents,
  14 EN / 11 FR: board minutes, NDA, Form CO excerpt, dawn-raid memo,
  leniency marker and settlement submission, RFI response, SPA, SHA
  and escrow excerpts, e-mail threads, arbitration request, DPIA memo
  and DPA response, due-diligence report, interview notes, conclusions,
  mise en demeure, dismissal letter, settlement, franchise excerpt,
  merger-thresholds memo, state-aid complaint, data-room index) was
  drafted by agents against a programmatic quality bar
  (`benchmark/synth.py`, including a cross-document uniqueness check),
  judged for realism, and never consulted while tuning — the honest
  number. All synthetic: professional
  secrecy rules out real files. Annotation policy: redact anything
  that identifies a party, adviser, witness or matter; leave public
  institutions, statutes, courts and jurisdictions in place; open
  rulings in `benchmark/synth/POLICY_QUESTIONS.md`. Documents are
  reviewed in Word with one highlight colour per type
  ([protocol](annotation-protocol.html)); Jude pre-highlights, the
  reviewer corrects.
* **Matching.** Lenient overlap (≥ 1 character), one-to-one, largest
  overlap first. *Type-strict* requires the predicted type to equal
  the gold type after mapping the system's labels onto Jude's schema;
  *any type* drops that requirement and answers "did it redact the
  right characters".
* **Label mapping.** Each external system's labels are mapped to the
  closest Jude type (tables in `benchmark/runners/`). Labels with no
  counterpart — dates, demographic attributes, `other_pii` — are
  dropped and counted, not scored as false positives. NVIDIA's
  `first_name` / `last_name` predictions are merged when adjacent.
* **Public-body over-redaction.** Occurrences in the corpus of the
  213 whitelisted institutions, statutes and jurisdictions (with their
  aliases, ignoring demonyms and legal-form suffixes) that no gold span
  covers: 117 mentions. The column reports how many of them each system
  redacted.
* **Sentence level.** Every document split into sentences; a sentence
  is positive iff it overlaps a gold span; a system flags it iff it
  predicts anything inside it. The only grid on which a message
  classifier can be compared with span extractors.
* **Hardware.** MacBook M2, 8 GB, one runner per process; external
  models on MPS (`PYTORCH_ENABLE_MPS_FALLBACK=1`), Jude's own stack on
  CPU as shipped. Throughput excludes model load; peak RSS is the
  process high-water mark.

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
| `gliner-large-v2.1-jude-labels` | 0.641 | 0.582 | **0.610** | 0.645 | 313/612 (51%) | 465/742 | 24 | 0.753 | 2,830 | 3,440 MB |
| `nvidia-gliner-pii-native` | 0.715 | 0.634 | **0.672** | 0.771 | 144/612 (24%) | 404/650 | 23 | 0.847 | 2,488 | 3,434 MB |
| `nvidia-gliner-pii-native-t03` | 0.702 | 0.653 | **0.677** | 0.782 | 156/612 (25%) | 370/616 | 22 | 0.857 | 2,508 | 3,553 MB |
| `nvidia-gliner-pii-jude-labels` | 0.714 | 0.559 | **0.627** | 0.644 | 243/612 (40%) | 500/783 | 23 | 0.765 | 2,799 | 3,898 MB |
| `pplx-pii-masking` | 0.916 | 0.429 | **0.584** | 0.628 | 15/612 (2%) | 827/1014 | 30 | 0.734 | 2,107 | 755 MB |
| `pplx-pii-masking-cpu` | 0.916 | 0.430 | **0.585** | 0.629 | 15/612 (2%) | 825/1012 | 30 | 0.736 | 130 | 1,572 MB |
| `roblox-pii-classifier` | — | — | — | — | — | — | — | 0.751 | 3,198 | 943 MB |

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
| `gliner-large-v2.1-jude-labels` | **0.657** (0.71 / 0.61, 19) | **0.597** (0.62 / 0.57, 25) |
| `nvidia-gliner-pii-native` | **0.721** (0.78 / 0.67, 19) | **0.658** (0.70 / 0.62, 25) |
| `nvidia-gliner-pii-native-t03` | **0.727** (0.76 / 0.69, 19) | **0.663** (0.69 / 0.64, 25) |
| `nvidia-gliner-pii-jude-labels` | **0.687** (0.79 / 0.61, 19) | **0.610** (0.69 / 0.55, 25) |
| `pplx-pii-masking` | **0.531** (0.89 / 0.38, 19) | **0.598** (0.92 / 0.44, 25) |
| `pplx-pii-masking-cpu` | **0.531** (0.89 / 0.38, 19) | **0.600** (0.92 / 0.44, 25) |

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
| `gliner-large-v2.1-jude-labels` | 0.763 | 0.742 | **0.753** | 789 | 245 | 274 |
| `nvidia-gliner-pii-native` | 0.900 | 0.801 | **0.847** | 851 | 95 | 212 |
| `nvidia-gliner-pii-native-t03` | 0.891 | 0.826 | **0.857** | 878 | 107 | 185 |
| `nvidia-gliner-pii-jude-labels` | 0.838 | 0.703 | **0.765** | 747 | 144 | 316 |
| `pplx-pii-masking` | 0.912 | 0.614 | **0.734** | 653 | 63 | 410 |
| `pplx-pii-masking-cpu` | 0.912 | 0.617 | **0.736** | 656 | 63 | 407 |
| `roblox-pii-classifier` | 0.875 | 0.658 | **0.751** | 699 | 100 | 364 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only | gliner-large-v2.1-jude-labels | nvidia-gliner-pii-native | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-jude-labels | pplx-pii-masking | pplx-pii-masking-cpu |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 1.000 | 0.963 | 0.966 | 0.923 | 0.636 | 0.526 | 0.667 | 0.690 | 0.690 | 0.640 | 0.571 | 0.571 |
| doc_002_credit_facility_en | 0.929 | 0.929 | 0.929 | 0.875 | 0.750 | 0.692 | 0.500 | 0.435 | 0.741 | 0.741 | 0.545 | 0.750 | 0.750 |
| doc_003_solaris_jv_fr | 0.927 | 0.927 | 0.927 | 0.826 | 0.643 | 0.667 | 0.348 | 0.606 | 0.737 | 0.769 | 0.562 | 0.571 | 0.571 |
| doc_005_supply_agreement_en | 1.000 | 1.000 | 1.000 | 0.765 | 0.870 | 0.643 | 0.471 | 0.667 | 0.759 | 0.759 | 0.750 | 0.526 | 0.526 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 1.000 | 0.974 | 0.848 | 0.824 | 0.348 | 0.606 | 0.842 | 0.842 | 0.706 | 0.848 | 0.848 |
| doc_007_patent_litigation_en | 0.984 | 0.984 | 0.968 | 0.806 | 0.735 | 0.679 | 0.229 | 0.778 | 0.815 | 0.877 | 0.735 | 0.450 | 0.450 |
| doc_008_regulatory_submission_en | 1.000 | 1.000 | 1.000 | 0.912 | 0.732 | 0.808 | 0.267 | 0.636 | 0.714 | 0.714 | 0.698 | 0.323 | 0.323 |
| doc_009_witness_statement_en | 0.960 | 0.960 | 0.980 | 0.923 | 0.909 | 0.826 | 0.286 | 0.651 | 0.783 | 0.766 | 0.667 | 0.579 | 0.579 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 | 0.500 | 0.600 | 0.645 | 0.500 | 0.261 | 0.261 |
| doc_011_sanctions_memo_en | 1.000 | 0.973 | 0.973 | 0.766 | 0.839 | 0.683 | 0.348 | 0.649 | 0.765 | 0.800 | 0.765 | 0.480 | 0.480 |
| doc_012_engagement_letter_en | 0.976 | 0.952 | 0.976 | 0.870 | 0.750 | 0.667 | 0.333 | 0.769 | 0.634 | 0.634 | 0.632 | 0.581 | 0.581 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 | 0.703 | 0.700 | 0.683 | 0.789 | 0.500 | 0.500 |
| doc_014_compliance_investigation_en | 0.976 | 0.976 | 0.976 | 0.909 | 0.788 | 0.769 | 0.320 | 0.667 | 0.811 | 0.769 | 0.757 | 0.621 | 0.621 |
| doc_015_corporate_restructuring_en | 0.963 | 0.981 | 0.981 | 0.897 | 0.818 | 0.784 | 0.267 | 0.651 | 0.667 | 0.652 | 0.698 | 0.471 | 0.471 |
| doc_016_tax_memo_en | 0.902 | 0.958 | 1.000 | 0.821 | 0.878 | 0.739 | 0.296 | 0.622 | 0.667 | 0.682 | 0.698 | 0.414 | 0.414 |
| doc_017_data_breach_notification_en | 0.909 | 0.968 | 0.933 | 0.789 | 0.889 | 0.621 | 0.400 | 0.647 | 0.710 | 0.667 | 0.759 | 0.609 | 0.609 |
| doc_018_cease_and_desist_en | 0.895 | 0.872 | 0.895 | 0.850 | 0.692 | 0.765 | 0.286 | 0.727 | 0.581 | 0.581 | 0.667 | 0.522 | 0.522 |
| doc_019_antitrust_complaint_en | 0.982 | 0.945 | 0.945 | 0.800 | 0.773 | 0.706 | 0.258 | 0.643 | 0.696 | 0.723 | 0.640 | 0.474 | 0.474 |
| doc_020_insolvency_update_en | 0.963 | 0.945 | 0.906 | 0.909 | 0.762 | 0.792 | 0.267 | 0.711 | 0.723 | 0.723 | 0.756 | 0.556 | 0.556 |
| doc_021_board_minutes_en | 0.899 | 0.905 | 0.872 | 0.828 | 0.748 | 0.785 | 0.114 | 0.794 | 0.860 | 0.862 | 0.790 | 0.506 | 0.506 |
| doc_022_nda_fr | 0.590 | 0.539 | 0.500 | 0.562 | 0.687 | 0.405 | 0.213 | 0.511 | 0.658 | 0.659 | 0.603 | 0.603 | 0.603 |
| doc_023_form_co_excerpt_en | 0.786 | 0.779 | 0.779 | 0.688 | 0.769 | 0.563 | 0.296 | 0.588 | 0.605 | 0.591 | 0.554 | 0.585 | 0.585 |
| doc_024_dawn_raid_memo_fr | 0.775 | 0.750 | 0.721 | 0.685 | 0.659 | 0.508 | 0.257 | 0.485 | 0.759 | 0.732 | 0.531 | 0.600 | 0.615 |
| doc_025_leniency_marker_en | 0.894 | 0.862 | 0.852 | 0.706 | 0.681 | 0.689 | 0.188 | 0.655 | 0.673 | 0.667 | 0.640 | 0.506 | 0.506 |
| doc_026_rfi_response_fr | 0.597 | 0.582 | 0.582 | 0.557 | 0.843 | 0.400 | 0.157 | 0.606 | 0.644 | 0.710 | 0.506 | 0.351 | 0.351 |
| doc_027_spa_excerpt_en | 0.748 | 0.721 | 0.699 | 0.687 | 0.719 | 0.629 | 0.233 | 0.542 | 0.673 | 0.700 | 0.604 | 0.683 | 0.683 |
| doc_028_client_email_thread_en | 0.882 | 0.762 | 0.778 | 0.812 | 0.450 | 0.612 | 0.229 | 0.614 | 0.746 | 0.756 | 0.723 | 0.727 | 0.727 |
| doc_029_cepani_request_en | 0.768 | 0.774 | 0.706 | 0.726 | 0.641 | 0.609 | 0.207 | 0.519 | 0.550 | 0.550 | 0.540 | 0.633 | 0.633 |
| doc_030_dpia_memo_fr | 0.823 | 0.748 | 0.730 | 0.734 | 0.633 | 0.550 | 0.197 | 0.631 | 0.742 | 0.747 | 0.687 | 0.480 | 0.480 |
| doc_031_dd_redflag_report_en | 0.775 | 0.741 | 0.731 | 0.694 | 0.695 | 0.721 | 0.095 | 0.678 | 0.632 | 0.626 | 0.696 | 0.494 | 0.494 |
| doc_032_conclusions_tribunal_fr | 0.734 | 0.679 | 0.561 | 0.596 | 0.515 | 0.408 | 0.115 | 0.624 | 0.615 | 0.617 | 0.688 | 0.515 | 0.515 |
| doc_033_transaction_fr | 0.580 | 0.574 | 0.488 | 0.571 | 0.730 | 0.314 | 0.298 | 0.559 | 0.545 | 0.557 | 0.500 | 0.697 | 0.697 |
| doc_034_state_aid_complaint_en | 0.677 | 0.678 | 0.678 | 0.633 | 0.627 | 0.655 | 0.163 | 0.581 | 0.615 | 0.624 | 0.523 | 0.525 | 0.525 |
| doc_035_data_room_index_en | 0.842 | 0.850 | 0.873 | 0.800 | 0.805 | 0.688 | 0.246 | 0.667 | 0.698 | 0.690 | 0.623 | 0.529 | 0.529 |
| doc_036_licenciement_motif_grave_fr | 0.667 | 0.689 | 0.609 | 0.650 | 0.732 | 0.433 | 0.364 | 0.588 | 0.645 | 0.660 | 0.633 | 0.693 | 0.693 |
| doc_037_merger_thresholds_memo_en | 0.803 | 0.794 | 0.818 | 0.561 | 0.729 | 0.519 | 0.265 | 0.459 | 0.425 | 0.427 | 0.359 | 0.558 | 0.558 |
| doc_038_reponse_apd_plainte_fr | 0.594 | 0.617 | 0.559 | 0.514 | 0.767 | 0.297 | 0.318 | 0.500 | 0.761 | 0.778 | 0.638 | 0.621 | 0.644 |
| doc_039_contrat_franchise_extrait_fr | 0.528 | 0.521 | 0.524 | 0.514 | 0.853 | 0.427 | 0.280 | 0.568 | 0.545 | 0.549 | 0.488 | 0.696 | 0.696 |
| doc_040_interview_notes_en | 0.760 | 0.807 | 0.667 | 0.461 | 0.426 | 0.624 | 0.046 | 0.596 | 0.731 | 0.716 | 0.612 | 0.661 | 0.661 |
| doc_041_shareholders_agreement_excerpt_en | 0.736 | 0.645 | 0.729 | 0.561 | 0.718 | 0.766 | 0.200 | 0.657 | 0.708 | 0.716 | 0.646 | 0.636 | 0.636 |
| doc_042_settlement_submission_en | 0.851 | 0.807 | 0.787 | 0.740 | 0.614 | 0.757 | 0.115 | 0.725 | 0.671 | 0.706 | 0.662 | 0.400 | 0.400 |
| doc_043_mise_en_demeure_fr | 0.561 | 0.630 | 0.630 | 0.561 | 0.787 | 0.390 | 0.356 | 0.475 | 0.649 | 0.640 | 0.647 | 0.706 | 0.706 |
| doc_044_fil_emails_budget_fr | 0.667 | 0.663 | 0.634 | 0.659 | 0.500 | 0.496 | 0.317 | 0.523 | 0.587 | 0.574 | 0.630 | 0.726 | 0.726 |
| doc_045_escrow_agreement_excerpt_en | 0.773 | 0.745 | 0.725 | 0.764 | 0.714 | 0.676 | 0.217 | 0.615 | 0.677 | 0.686 | 0.633 | 0.661 | 0.661 |

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

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.718 | 0.350 | 0.471 | 28 | 11 | 52 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.515 | 0.835 | 0.637 | 207 | 195 | 41 |
| ORG | 0.604 | 0.694 | 0.646 | 491 | 322 | 216 |
| PERSON | 0.858 | 0.656 | 0.743 | 307 | 51 | 161 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### nvidia-gliner-pii-native — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| EMAIL | 0.875 | 0.283 | 0.427 | 28 | 4 | 71 |
| IBAN | 0.607 | 0.617 | 0.612 | 37 | 24 | 23 |
| LOC | 0.480 | 0.940 | 0.636 | 233 | 252 | 15 |
| ORG | 0.957 | 0.441 | 0.604 | 312 | 14 | 395 |
| PERSON | 0.742 | 0.938 | 0.828 | 439 | 153 | 29 |
| PHONE | 0.971 | 0.810 | 0.883 | 68 | 2 | 16 |
| URL | 1.000 | 0.276 | 0.432 | 8 | 0 | 21 |

### nvidia-gliner-pii-native-t03 — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| EMAIL | 0.806 | 0.293 | 0.430 | 29 | 7 | 70 |
| IBAN | 0.541 | 0.667 | 0.597 | 40 | 34 | 20 |
| LOC | 0.459 | 0.944 | 0.617 | 234 | 276 | 14 |
| ORG | 0.951 | 0.467 | 0.626 | 330 | 17 | 377 |
| PERSON | 0.740 | 0.942 | 0.829 | 441 | 155 | 27 |
| PHONE | 0.974 | 0.905 | 0.938 | 76 | 2 | 8 |
| URL | 1.000 | 0.310 | 0.474 | 9 | 0 | 20 |

### nvidia-gliner-pii-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.851 | 0.713 | 0.776 | 57 | 10 | 23 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.504 | 0.923 | 0.652 | 229 | 225 | 19 |
| ORG | 0.725 | 0.537 | 0.617 | 380 | 144 | 327 |
| PERSON | 0.948 | 0.697 | 0.803 | 326 | 18 | 142 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### pplx-pii-masking — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| EMAIL | 0.908 | 1.000 | 0.952 | 99 | 10 | 0 |
| IBAN | 0.552 | 0.883 | 0.679 | 53 | 43 | 7 |
| LOC | 0.990 | 0.407 | 0.577 | 101 | 1 | 147 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 707 |
| PERSON | 0.963 | 0.897 | 0.929 | 420 | 16 | 48 |
| PHONE | 1.000 | 0.893 | 0.943 | 75 | 0 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

### pplx-pii-masking-cpu — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| EMAIL | 0.908 | 1.000 | 0.952 | 99 | 10 | 0 |
| IBAN | 0.552 | 0.883 | 0.679 | 53 | 43 | 7 |
| LOC | 0.990 | 0.411 | 0.581 | 102 | 1 | 146 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 707 |
| PERSON | 0.963 | 0.900 | 0.930 | 421 | 16 | 47 |
| PHONE | 1.000 | 0.893 | 0.943 | 75 | 0 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-full-gliner-small`** — device cpu; load 0.0 s.
- **`jude-full-no-gliner`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`rules-only`** — device cpu; load 0.1 s.
  - Deterministic layers only: regex + patterns + known entities + whitelist.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
- **`gliner-large-v2.1-jude-labels`** — model `urchade/gliner_large-v2.1`; device mps; load 13.7 s; threshold 0.5.
- **`nvidia-gliner-pii-native`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 11.6 s; threshold 0.5.
- **`nvidia-gliner-pii-native-t03`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.1 s; threshold 0.3.
- **`nvidia-gliner-pii-jude-labels`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.3 s; threshold 0.5.
- **`pplx-pii-masking`** — model `perplexity-ai/pplx-pii-masking` @ `f1f90a53`; device mps; load 5.4 s; out-of-schema predictions dropped: other_pii×8, private_date×153; mean document sensitivity 0.21.
  - No organisation label: ORG recall is 0 by construction.
  - `private_date` / `other_pii` predictions dropped as out-of-schema (counted, not scored as FP).
  - Input truncated at 4096 tokens; corpus documents are far shorter.
- **`pplx-pii-masking-cpu`** — model `perplexity-ai/pplx-pii-masking` @ `f1f90a53`; device cpu; load 4.8 s; out-of-schema predictions dropped: other_pii×8, private_date×153; mean document sensitivity 0.21.
  - No organisation label: ORG recall is 0 by construction.
  - `private_date` / `other_pii` predictions dropped as out-of-schema (counted, not scored as FP).
  - Input truncated at 4096 tokens; corpus documents are far shorter.
- **`roblox-pii-classifier`** — model `roblox/roblox-pii-classifier` @ `253c2057`; device mps; load 9.6 s; threshold 0.2691.
  - Message-level classifier (asking-for / giving PII); no spans. Scored on the sentence grid only.
  - Trained on chat; the model card itself reports 45.5% F1 on the Kaggle PII essay dataset.

## The generalisation gap

The first version of this benchmark scored twenty documents on which
Jude's whitelist and stop-lists had been tuned. The `heldout` split —
twenty-five documents drafted later against a programmatic bar and a
judge, never consulted while tuning — is the number to quote:

| System | dev F1 (P / R) | heldout F1 (P / R) | gap |
|---|---|---|---|
| `jude-full` | 0.963 (0.93 / 1.00) | **0.735** (0.62 / 0.89) | −0.23 |
| `jude-full-gliner-small` | 0.960 | 0.716 (0.62 / 0.85) | −0.24 |
| `rules-only` | 0.790 (0.99 / 0.66) | 0.678 (0.95 / 0.53) | −0.11 |
| `nvidia-gliner-pii-native` | 0.721 (0.78 / 0.67) | 0.658 (0.70 / 0.62) | −0.06 |
| `gliner-large-v2.1-jude-labels` | 0.657 | 0.597 | −0.06 |
| `pplx-pii-masking` | 0.531 (0.89 / 0.38) | 0.598 (0.92 / 0.44) | +0.07 |
| `roblox-pii-classifier` (sentence F1) | 0.764 | 0.751 | −0.01 |

Jude loses 23 points between the two splits; the generic models lose
six or gain some. That is the honest measure of how much of the dev
score was tuning. Jude still leads on the held-out set, and its recall
holds (0.89); what collapses is precision (0.93 → 0.62) — the public
sphere it does not know yet, as the taxonomy below shows. Every fix
suggested by a held-out failure is listed here and *not applied*: the
next batch of documents will measure it.

## Failure taxonomy

Read off `python -m benchmark.analyze benchmark/results/*.json`; counts
are exact for this corpus.

### 1. Generic PII taxonomies have no word for half of what a legal document must hide

ORG and CASE_REF are 47 % of the gold spans. `pplx-pii-masking` has no
organisation label: ORG recall is **0.000** by construction, on both
splits; its overall recall is 0.44 and its precision 0.92 — it is a
careful model for the wrong task. NVIDIA's `company_name` reaches
ORG recall 0.47 with precision 0.85 — it misses short names, acronyms
and every codename. Neither has a case-reference label.

### 2. What Jude misses on the held-out split (recall 0.89)

149 misses in 1,775 gold spans, in five classes, each a handful of
lines to fix and each *left unfixed* for the next round:

* **Registry numbers** (28): KBO/BCE `0712.445.303`, `HRB 71244`,
  Companies House eight-digit numbers, an Italian VAT. IBAN precision
  is 1.00 and recall 0.43 on the held-out split — the regex layer
  simply has no pattern for them.
* **Reference formats it has not seen** (28): Belgian *numéro de rôle*
  `A/26/02371`, firm references of the shape `LH/2026/0583-TRV`, a
  pre-notification `M.12384`. CASE_REF recall 0.56 — the same lesson
  as v0.7.7, on new shapes.
* **Bare codenames and short forms** (42 ORG): `Héron`, `Sarcelle`,
  `Kittiwake`, `Valdoire`, `Ambreval`, `Tremonval`. Half of these are
  the codename policy (the corpus says redact; Jude's filter still
  drops bare codename words); the rest are short forms whose full form
  was caught but not propagated.
* **Surname-only repeats** (38 PERSON): `Herbiet` ×3, `Roelandts`,
  `Thonnard`, `Brankovic`, `Pasqualotto`, `Rombouts` — the reference a
  practitioner uses after first mention. The dictionary propagates
  full names; it must propagate surnames.
* **Bare cities and venues** (12 LOC): `Antwerp`, `Rotterdam`,
  `Breda`, `Hotel Löwenkranz`, `9100 Sint-Niklaas` — the annotation
  policy on cities (POLICY_QUESTIONS §6) as much as a detector gap.

### 3. What Jude over-redacts on the held-out split (precision 0.62)

Three-quarters of the 772 spurious spans are the *negative* classes:

* **The public sphere in Belgian and French practice** — 30 % of the
  496 whitelisted mentions redacted: *Auditorat*, *Chambre
  contentieuse*, *Cour des marchés*, *ONSS*, *SPF Emploi*, *Conseil
  national du Travail*, *SETCa*, *loi du 3 juillet 1978*, *Cass.*,
  *Pas.* — a whitelist built on English competition practice meeting
  employment, data-protection and civil-procedure French. A list can
  be extended forever; a model with a `public_body` label learns the
  category.
* **Published citations typed as live case references** (13):
  `C-746/21 P`, `C-311/18`, `T-274/01`, *Hoffmann-La Roche 85/76*.
  The corpus policy (POLICY_QUESTIONS §2) says published = public; the
  regex says every `C-nnn/nn` is a case reference. A model needs the
  distinction as two labels.
* **Roles, defined terms and legal forms** (a large share of 427 ORG
  false positives): *l'Auditeur*, *auditeur général*, *siège des
  Parties*, *Naamloze vennootschap*, *Audit & Risk Committee*,
  *Creditors' Committee*, *Swiss parent*. The stop-list has sixty
  entries; the held-out documents used sixty others.
* **Type confusion on bare short forms** (ORG → PERSON 26, PERSON →
  ORG 20): a bare `Valdoire` or `Steinhauer` is a company in one
  document and a person in the next; without context the neural layer
  guesses. Lenient any-type F1 (0.78 vs 0.74) measures the cost.
* **Countries and regions as LOC** (part of 185 LOC false positives):
  *Pays-Bas*, *England and Wales*, *Afrique du Nord*, the Commission's
  own address. Jurisdictions are public; the whitelist knows twenty.

### 4. Address ≠ location; e-mails as names; the honorific-only reference

Unchanged from the first run and confirmed on the new documents:
`pplx`'s `private_address` catches full postal addresses and no bare
city (LOC recall 0.27); NVIDIA labels the local part of e-mail
addresses as first and last names (EMAIL recall 0.40, dozens of
spurious PERSON spans); `pplx` misses *Mr. Tan*-style references,
NVIDIA catches them.

### 5. A message classifier on legal prose

`roblox-pii-classifier` at sentence level: precision 0.97, recall 0.63
on the held-out split — it almost never flags a clean sentence and
misses a third of the sentences carrying an identifier.

### 6. The review report as the last line

Of Jude's 148 held-out misses, the unverified-term report puts 38 in
front of the reviewer, at 17 items per document. The remaining 110 are
mostly numbers (registry and reference formats) and lower-case or
all-caps short forms the capitalisation heuristic does not see —
which is why the report's next version lists digit-bearing tokens
too.

## What Jude takes from this — for the next version, measured on the next batch

* Registry-number and *numéro de rôle* patterns; surname propagation
  in the dictionary; digit-bearing tokens in the review report.
* French public-sphere entries and the *published citation* rule in
  the whitelist — knowing that every such list is a stopgap the model
  should make redundant.
* The codename ruling (POLICY_QUESTIONS §1) applied consistently in
  corpus and detector.
* GLiNER small as the laptop default is defensible: −3 recall points
  for 2.7× the speed inside the pipeline (see `efficiency-frontier.html`).

## What a legal-anonymisation model would need

For anyone minded to train one — the plan is in `training-data.html`:

1. **Labels that encode the legal distinction, not the PII one.**
   `party_organisation` *versus* `public_body`; `private_person`
   *versus* `official_in_public_capacity`; `case_reference_live`
   *versus* `case_reference_published`; `registry_number`;
   `party_address` *versus* `public_address`; `role` as an explicit
   negative. Every one of these is a class of held-out error above.
2. **Legal synthetic data, EN / FR first (then DE / NL), EU formats**,
   generated the way this corpus was — briefs, a programmatic bar, a
   judge, uniqueness across documents — at a scale of thousands.
3. **Long context or built-in chunking** with consistent decisions
   across chunks.
4. **Alias consistency**: *Herbiet* / *Thomas Herbiet* / *le
   directeur commercial* map to one pseudonym; a model that emits
   coreference makes the propagation cheap.
5. **Evaluation on the held-out split, never on the tuning split**,
   and a fresh batch for every round of fixes.

## Limitations of this benchmark

* Forty-four synthetic documents, one annotation policy with seven
  open rulings, agent-drafted held-out documents judged but not yet
  reviewed by a lawyer. The numbers are indicative; the ranking and
  the size of the generalisation gap are robust.
* Where a mapping choice was ambiguous it was made in the external
  model's favour: dates and demographic labels are dropped rather than
  counted as false positives; adjacent name fragments are merged.
* Thresholds are the model cards' defaults; lowering NVIDIA's to 0.3
  changes little.
* Roblox's own card reports 45.5 % F1 on the Kaggle PII essay dataset;
  that number is not comparable to anything here and is not used.
