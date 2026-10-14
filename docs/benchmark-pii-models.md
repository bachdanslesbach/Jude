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
  number. All 44 documents were reviewed in Word by a lawyer on
  13 October 2026 under the annotation rulings of that day. All synthetic: professional
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
| `jude-full` | 0.690 | 0.910 | **0.785** | 0.815 | 132/613 (22%) | 53/146 | 16 | 0.859 | 541 | 2,445 MB |
| `jude-full-gliner-small` | 0.688 | 0.883 | **0.774** | 0.815 | 129/613 (21%) | 78/190 | 16 | 0.856 | 1,633 | 1,949 MB |
| `jude-full-no-gliner` | 0.690 | 0.846 | **0.760** | 0.812 | 116/613 (19%) | 119/250 | 18 | 0.856 | 2,896 | 2,059 MB |
| `jude-no-public-filter` | 0.601 | 0.865 | **0.709** | 0.773 | 335/613 (55%) | 63/220 | 16 | 0.834 | 658 | 3,423 MB |
| `rules-only` | 0.962 | 0.604 | **0.742** | 0.744 | 18/613 (3%) | 574/644 | 29 | 0.770 | 350,183 | 308 MB |
| `spacy-only` | 0.640 | 0.602 | **0.621** | 0.685 | 247/613 (40%) | 315/647 | 23 | 0.790 | 5,311 | 2,206 MB |
| `regex-only` | 0.956 | 0.148 | **0.257** | 0.257 | 0/613 (0%) | 1337/1386 | 42 | 0.287 | 3,475,995 | 308 MB |
| `gliner-large-v2.1-jude-labels` | 0.674 | 0.549 | **0.605** | 0.642 | 227/613 (37%) | 473/733 | 27 | 0.741 | 2,656 | 3,442 MB |
| `nvidia-gliner-pii-native` | 0.646 | 0.625 | **0.635** | 0.735 | 145/613 (24%) | 377/610 | 23 | 0.843 | 2,488 | 3,434 MB |
| `nvidia-gliner-pii-native-t03` | 0.637 | 0.646 | **0.641** | 0.747 | 157/613 (26%) | 344/576 | 22 | 0.853 | 2,508 | 3,553 MB |
| `nvidia-gliner-pii-jude-labels` | 0.798 | 0.516 | **0.627** | 0.636 | 169/613 (28%) | 508/788 | 27 | 0.757 | 2,723 | 3,465 MB |
| `pplx-pii-masking` | 0.916 | 0.468 | **0.619** | 0.669 | 15/613 (2%) | 716/866 | 30 | 0.755 | 2,107 | 755 MB |
| `pplx-pii-masking-cpu` | 0.916 | 0.469 | **0.620** | 0.670 | 15/613 (2%) | 714/864 | 30 | 0.757 | 130 | 1,572 MB |
| `roblox-pii-classifier` | — | — | — | — | — | — | — | 0.751 | 3,198 | 943 MB |
| `ollama-qwen3-4b` | 0.520 | 0.652 | **0.579** | 0.640 | 280/613 (46%) | 390/566 | 19 | 0.745 | 26 | 281 MB |

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
| `gliner-large-v2.1-jude-labels` | **0.624** (0.71 / 0.56, 19) | **0.600** (0.67 / 0.55, 25) |
| `nvidia-gliner-pii-native` | **0.662** (0.68 / 0.65, 19) | **0.628** (0.64 / 0.62, 25) |
| `nvidia-gliner-pii-native-t03` | **0.670** (0.67 / 0.67, 19) | **0.634** (0.63 / 0.64, 25) |
| `nvidia-gliner-pii-jude-labels` | **0.654** (0.82 / 0.55, 19) | **0.619** (0.79 / 0.51, 25) |
| `pplx-pii-masking` | **0.570** (0.89 / 0.42, 19) | **0.632** (0.92 / 0.48, 25) |
| `pplx-pii-masking-cpu` | **0.570** (0.89 / 0.42, 19) | **0.634** (0.92 / 0.48, 25) |
| `ollama-qwen3-4b` | **0.694** (0.59 / 0.85, 19) | **0.544** (0.50 / 0.60, 25) |

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
| `gliner-large-v2.1-jude-labels` | 0.765 | 0.718 | **0.741** | 736 | 226 | 289 |
| `nvidia-gliner-pii-native` | 0.878 | 0.811 | **0.843** | 831 | 115 | 194 |
| `nvidia-gliner-pii-native-t03` | 0.870 | 0.836 | **0.853** | 857 | 128 | 168 |
| `nvidia-gliner-pii-jude-labels` | 0.863 | 0.674 | **0.757** | 691 | 110 | 334 |
| `pplx-pii-masking` | 0.918 | 0.641 | **0.755** | 657 | 59 | 368 |
| `pplx-pii-masking-cpu` | 0.918 | 0.644 | **0.757** | 660 | 59 | 365 |
| `roblox-pii-classifier` | 0.875 | 0.658 | **0.751** | 699 | 100 | 364 |
| `ollama-qwen3-4b` | 0.726 | 0.765 | **0.745** | 784 | 296 | 241 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only | gliner-large-v2.1-jude-labels | nvidia-gliner-pii-native | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-jude-labels | pplx-pii-masking | pplx-pii-masking-cpu | ollama-qwen3-4b |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 1.000 | 0.960 | 1.000 | 0.960 | 1.000 | 0.632 | 0.588 | 0.632 | 0.593 | 0.593 | 0.632 | 0.632 | 0.632 | 0.686 |
| doc_002_credit_facility_en | 0.963 | 0.963 | 0.963 | 0.867 | 0.783 | 0.667 | 0.526 | 0.400 | 0.692 | 0.692 | 0.455 | 0.783 | 0.783 | 0.545 |
| doc_003_solaris_jv_fr | 0.970 | 0.941 | 0.970 | 0.842 | 0.720 | 0.647 | 0.400 | 0.571 | 0.629 | 0.667 | 0.615 | 0.640 | 0.640 | 0.718 |
| doc_005_supply_agreement_en | 1.000 | 1.000 | 1.000 | 0.759 | 0.952 | 0.609 | 0.533 | 0.632 | 0.667 | 0.667 | 0.737 | 0.588 | 0.588 | 0.629 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 0.973 | 0.974 | 0.848 | 0.788 | 0.348 | 0.625 | 0.842 | 0.842 | 0.562 | 0.848 | 0.848 | 0.727 |
| doc_007_patent_litigation_en | 0.846 | 0.830 | 0.863 | 0.917 | 0.829 | 0.829 | 0.296 | 0.636 | 0.652 | 0.735 | 0.579 | 0.563 | 0.563 | 0.581 |
| doc_008_regulatory_submission_en | 0.979 | 0.979 | 0.979 | 0.885 | 0.769 | 0.766 | 0.286 | 0.634 | 0.750 | 0.750 | 0.667 | 0.345 | 0.345 | 0.880 |
| doc_009_witness_statement_en | 0.958 | 0.958 | 0.979 | 0.958 | 0.930 | 0.857 | 0.296 | 0.600 | 0.756 | 0.739 | 0.629 | 0.595 | 0.595 | 0.727 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 | 0.500 | 0.600 | 0.645 | 0.467 | 0.261 | 0.261 | 0.600 |
| doc_011_sanctions_memo_en | 1.000 | 0.968 | 0.968 | 0.769 | 0.929 | 0.667 | 0.400 | 0.581 | 0.645 | 0.688 | 0.714 | 0.545 | 0.545 | 0.757 |
| doc_012_engagement_letter_en | 0.971 | 0.919 | 0.971 | 0.944 | 0.828 | 0.690 | 0.381 | 0.828 | 0.579 | 0.579 | 0.741 | 0.643 | 0.643 | 0.636 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 | 0.778 | 0.700 | 0.683 | 0.811 | 0.500 | 0.500 | 0.780 |
| doc_014_compliance_investigation_en | 0.970 | 0.970 | 0.970 | 0.914 | 0.897 | 0.710 | 0.381 | 0.600 | 0.667 | 0.629 | 0.741 | 0.720 | 0.720 | 0.780 |
| doc_015_corporate_restructuring_en | 0.980 | 0.980 | 0.960 | 0.980 | 0.837 | 0.800 | 0.276 | 0.667 | 0.636 | 0.622 | 0.718 | 0.485 | 0.485 | 0.706 |
| doc_016_tax_memo_en | 0.955 | 0.977 | 1.000 | 0.955 | 0.923 | 0.811 | 0.320 | 0.649 | 0.600 | 0.619 | 0.765 | 0.444 | 0.444 | 0.679 |
| doc_017_data_breach_notification_en | 0.897 | 0.963 | 0.963 | 0.788 | 0.960 | 0.583 | 0.444 | 0.552 | 0.621 | 0.581 | 0.696 | 0.667 | 0.667 | 0.686 |
| doc_018_cease_and_desist_en | 0.875 | 0.875 | 0.875 | 0.848 | 0.783 | 0.692 | 0.333 | 0.692 | 0.429 | 0.429 | 0.636 | 0.600 | 0.600 | 0.615 |
| doc_019_antitrust_complaint_en | 0.963 | 0.926 | 0.926 | 0.794 | 0.791 | 0.694 | 0.267 | 0.630 | 0.667 | 0.696 | 0.625 | 0.486 | 0.486 | 0.743 |
| doc_020_insolvency_update_en | 0.902 | 0.885 | 0.840 | 0.846 | 0.762 | 0.682 | 0.267 | 0.585 | 0.723 | 0.723 | 0.619 | 0.556 | 0.556 | 0.679 |
| doc_021_board_minutes_en | 0.893 | 0.891 | 0.898 | 0.819 | 0.816 | 0.786 | 0.131 | 0.757 | 0.804 | 0.807 | 0.776 | 0.564 | 0.564 | 0.431 |
| doc_022_nda_fr | 0.629 | 0.611 | 0.578 | 0.574 | 0.742 | 0.423 | 0.238 | 0.519 | 0.649 | 0.649 | 0.603 | 0.655 | 0.655 | 0.516 |
| doc_023_form_co_excerpt_en | 0.748 | 0.736 | 0.724 | 0.672 | 0.789 | 0.524 | 0.308 | 0.587 | 0.619 | 0.605 | 0.507 | 0.603 | 0.603 | 0.583 |
| doc_024_dawn_raid_memo_fr | 0.767 | 0.756 | 0.736 | 0.676 | 0.698 | 0.509 | 0.277 | 0.540 | 0.738 | 0.710 | 0.523 | 0.635 | 0.651 | 0.456 |
| doc_025_leniency_marker_en | 0.876 | 0.857 | 0.846 | 0.667 | 0.756 | 0.660 | 0.218 | 0.612 | 0.558 | 0.552 | 0.585 | 0.571 | 0.571 | 0.703 |
| doc_026_rfi_response_fr | 0.689 | 0.696 | 0.690 | 0.656 | 0.843 | 0.476 | 0.157 | 0.659 | 0.644 | 0.710 | 0.597 | 0.351 | 0.351 | 0.522 |
| doc_027_spa_excerpt_en | 0.708 | 0.708 | 0.667 | 0.661 | 0.744 | 0.593 | 0.246 | 0.532 | 0.695 | 0.722 | 0.565 | 0.709 | 0.709 | 0.659 |
| doc_028_client_email_thread_en | 0.877 | 0.832 | 0.839 | 0.839 | 0.514 | 0.653 | 0.267 | 0.612 | 0.722 | 0.734 | 0.742 | 0.809 | 0.809 | 0.660 |
| doc_029_cepani_request_en | 0.842 | 0.839 | 0.759 | 0.845 | 0.641 | 0.680 | 0.207 | 0.566 | 0.550 | 0.550 | 0.610 | 0.633 | 0.633 | 0.472 |
| doc_030_dpia_memo_fr | 0.830 | 0.690 | 0.706 | 0.724 | 0.781 | 0.462 | 0.261 | 0.642 | 0.610 | 0.619 | 0.618 | 0.600 | 0.600 | 0.585 |
| doc_031_dd_redflag_report_en | 0.744 | 0.715 | 0.733 | 0.672 | 0.767 | 0.734 | 0.111 | 0.673 | 0.571 | 0.566 | 0.731 | 0.556 | 0.556 | 0.000 |
| doc_032_conclusions_tribunal_fr | 0.817 | 0.731 | 0.562 | 0.653 | 0.557 | 0.400 | 0.128 | 0.691 | 0.535 | 0.539 | 0.753 | 0.557 | 0.557 | 0.526 |
| doc_033_transaction_fr | 0.633 | 0.622 | 0.606 | 0.628 | 0.730 | 0.421 | 0.298 | 0.617 | 0.545 | 0.557 | 0.600 | 0.697 | 0.697 | 0.557 |
| doc_034_state_aid_complaint_en | 0.642 | 0.636 | 0.642 | 0.617 | 0.700 | 0.674 | 0.190 | 0.587 | 0.548 | 0.558 | 0.571 | 0.593 | 0.593 | 0.483 |
| doc_035_data_room_index_en | 0.769 | 0.777 | 0.800 | 0.741 | 0.868 | 0.667 | 0.275 | 0.579 | 0.675 | 0.667 | 0.545 | 0.581 | 0.581 | 0.753 |
| doc_036_licenciement_motif_grave_fr | 0.734 | 0.759 | 0.680 | 0.716 | 0.754 | 0.494 | 0.377 | 0.608 | 0.659 | 0.674 | 0.704 | 0.712 | 0.712 | 0.496 |
| doc_037_merger_thresholds_memo_en | 0.810 | 0.784 | 0.816 | 0.690 | 0.753 | 0.592 | 0.277 | 0.490 | 0.419 | 0.422 | 0.424 | 0.578 | 0.578 | 0.509 |
| doc_038_reponse_apd_plainte_fr | 0.660 | 0.682 | 0.595 | 0.549 | 0.780 | 0.317 | 0.326 | 0.545 | 0.743 | 0.761 | 0.677 | 0.632 | 0.655 | 0.623 |
| doc_039_contrat_franchise_extrait_fr | 0.592 | 0.583 | 0.592 | 0.578 | 0.865 | 0.527 | 0.286 | 0.642 | 0.531 | 0.535 | 0.600 | 0.706 | 0.706 | 0.658 |
| doc_040_interview_notes_en | 0.730 | 0.775 | 0.637 | 0.398 | 0.455 | 0.600 | 0.050 | 0.578 | 0.681 | 0.667 | 0.605 | 0.700 | 0.700 | 0.416 |
| doc_041_shareholders_agreement_excerpt_en | 0.727 | 0.637 | 0.724 | 0.562 | 0.737 | 0.779 | 0.208 | 0.661 | 0.724 | 0.733 | 0.691 | 0.654 | 0.654 | 0.494 |
| doc_042_settlement_submission_en | 0.840 | 0.800 | 0.805 | 0.717 | 0.661 | 0.760 | 0.128 | 0.725 | 0.586 | 0.625 | 0.574 | 0.438 | 0.438 | 0.492 |
| doc_043_mise_en_demeure_fr | 0.574 | 0.644 | 0.682 | 0.594 | 0.738 | 0.417 | 0.327 | 0.456 | 0.615 | 0.608 | 0.625 | 0.667 | 0.667 | 0.651 |
| doc_044_fil_emails_budget_fr | 0.752 | 0.761 | 0.721 | 0.759 | 0.500 | 0.536 | 0.317 | 0.490 | 0.587 | 0.574 | 0.608 | 0.726 | 0.726 | 0.600 |
| doc_045_escrow_agreement_excerpt_en | 0.719 | 0.740 | 0.698 | 0.719 | 0.732 | 0.645 | 0.225 | 0.538 | 0.692 | 0.701 | 0.585 | 0.679 | 0.679 | 0.742 |

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

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.729 | 0.417 | 0.530 | 35 | 13 | 49 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.648 | 0.738 | 0.690 | 107 | 58 | 38 |
| ORG | 0.591 | 0.682 | 0.633 | 449 | 311 | 209 |
| PERSON | 0.856 | 0.647 | 0.737 | 303 | 51 | 165 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### nvidia-gliner-pii-native — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| EMAIL | 0.875 | 0.283 | 0.427 | 28 | 4 | 71 |
| IBAN | 0.607 | 0.617 | 0.612 | 37 | 24 | 23 |
| LOC | 0.276 | 0.924 | 0.425 | 134 | 351 | 11 |
| ORG | 0.929 | 0.460 | 0.616 | 303 | 23 | 355 |
| PERSON | 0.742 | 0.938 | 0.828 | 439 | 153 | 29 |
| PHONE | 0.971 | 0.810 | 0.883 | 68 | 2 | 16 |
| URL | 1.000 | 0.276 | 0.432 | 8 | 0 | 21 |

### nvidia-gliner-pii-native-t03 — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| EMAIL | 0.806 | 0.293 | 0.430 | 29 | 7 | 70 |
| IBAN | 0.541 | 0.667 | 0.597 | 40 | 34 | 20 |
| LOC | 0.265 | 0.931 | 0.412 | 135 | 375 | 10 |
| ORG | 0.925 | 0.488 | 0.639 | 321 | 26 | 337 |
| PERSON | 0.740 | 0.942 | 0.829 | 441 | 155 | 27 |
| PHONE | 0.974 | 0.905 | 0.938 | 76 | 2 | 8 |
| URL | 1.000 | 0.310 | 0.474 | 9 | 0 | 20 |

### nvidia-gliner-pii-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.851 | 0.750 | 0.797 | 63 | 11 | 21 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.886 | 0.697 | 0.780 | 101 | 13 | 44 |
| ORG | 0.673 | 0.544 | 0.602 | 358 | 174 | 300 |
| PERSON | 0.958 | 0.677 | 0.793 | 317 | 14 | 151 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### pplx-pii-masking — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| EMAIL | 0.908 | 1.000 | 0.952 | 99 | 10 | 0 |
| IBAN | 0.552 | 0.883 | 0.679 | 53 | 43 | 7 |
| LOC | 0.990 | 0.697 | 0.818 | 101 | 1 | 44 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 658 |
| PERSON | 0.963 | 0.897 | 0.929 | 420 | 16 | 48 |
| PHONE | 1.000 | 0.893 | 0.943 | 75 | 0 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

### pplx-pii-masking-cpu — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 84 |
| EMAIL | 0.908 | 1.000 | 0.952 | 99 | 10 | 0 |
| IBAN | 0.552 | 0.883 | 0.679 | 53 | 43 | 7 |
| LOC | 0.990 | 0.703 | 0.823 | 102 | 1 | 43 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 658 |
| PERSON | 0.963 | 0.900 | 0.930 | 421 | 16 | 47 |
| PHONE | 1.000 | 0.893 | 0.943 | 75 | 0 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

### ollama-qwen3-4b — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.673 | 0.810 | 0.735 | 68 | 33 | 16 |
| EMAIL | 1.000 | 0.970 | 0.985 | 96 | 0 | 3 |
| IBAN | 1.000 | 0.633 | 0.776 | 38 | 0 | 22 |
| LOC | 0.443 | 0.807 | 0.572 | 117 | 147 | 28 |
| ORG | 0.681 | 0.573 | 0.622 | 377 | 177 | 281 |
| PERSON | 0.797 | 0.553 | 0.653 | 259 | 66 | 209 |
| PHONE | 0.941 | 0.952 | 0.947 | 80 | 5 | 4 |
| SECRET | 0.000 | 0.000 | 0.000 | 0 | 549 | 0 |
| URL | 0.963 | 0.897 | 0.929 | 26 | 1 | 3 |

## Runner notes

- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-full-gliner-small`** — device cpu; load 0.0 s.
- **`jude-full-no-gliner`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`rules-only`** — device cpu; load 0.1 s.
  - Deterministic layers only: regex + patterns + known entities + whitelist.
- **`spacy-only`** — device cpu; load 0.1 s.
- **`regex-only`** — device cpu; load 0.1 s.
- **`gliner-large-v2.1-jude-labels`** — model `urchade/gliner_large-v2.1`; device mps; load 15.8 s; threshold 0.5.
- **`nvidia-gliner-pii-native`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 11.6 s; threshold 0.5.
- **`nvidia-gliner-pii-native-t03`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.1 s; threshold 0.3.
- **`nvidia-gliner-pii-jude-labels`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.0 s; threshold 0.5.
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
- **`ollama-qwen3-4b`** — model `qwen3:4b`; device ollama; load 11.2 s.
  - Generative extraction via Ollama (local); thinking disabled, temperature 0.
  - Surfaces are located by exact string search — every occurrence counts.

## The generalisation gap

The first version of this benchmark scored twenty documents on which
Jude's whitelist and stop-lists had been tuned. The `heldout` split —
twenty-five documents drafted later against a programmatic bar and a
judge, never consulted while tuning — is the number to quote:

Numbers below follow the annotation rulings of 13 October 2026
(`benchmark/synth/POLICY_QUESTIONS.md`): deal codenames and bare city
names are no longer identifiers, invoice numbers are. Jude's detector
follows rulings 1 and 6 since v0.8.1 (bare cities are never predicted,
codenames only when a matter opts in); every document was reviewed in
Word by a lawyer on the same day.

| System | dev F1 (P / R) | heldout F1 (P / R) | gap |
|---|---|---|---|
| `jude-full` | 0.952 (0.92 / 0.99) | **0.745** (0.64 / 0.89) | −0.21 |
| `jude-full-gliner-small` | 0.941 (0.90 / 0.98) | 0.732 (0.64 / 0.86) | −0.21 |
| `rules-only` | 0.836 (0.99 / 0.72) | 0.714 (0.95 / 0.57) | −0.12 |
| `nvidia-gliner-pii-native` | 0.662 (0.68 / 0.65) | 0.628 (0.64 / 0.62) | −0.03 |
| `gliner-large-v2.1-jude-labels` | 0.624 | 0.600 | −0.02 |
| `pplx-pii-masking` | 0.570 (0.89 / 0.42) | 0.632 (0.92 / 0.48) | +0.06 |
| `ollama-qwen3-4b` (generative, 4 B) | 0.694 (0.59 / 0.85) | 0.544 (0.50 / 0.60) | −0.15 |
| `roblox-pii-classifier` (sentence F1) | 0.764 | 0.751 | −0.01 |

Jude loses 21 points between the two splits; the generic models lose
three or gain some. That is the honest measure of how much of the dev
score was tuning. On the held-out set Jude's recall holds (0.89) while
its precision drops (0.92 → 0.64). The rules alone sit at precision
0.95 and recall 0.57 — three points of F1 behind. F1 is not the
lawyer's objective; recall is, and 0.89 against 0.57 is the whole case
for the neural layers. But the gap says what they cost: 32 points of
recall for 31 points of precision — the public sphere in French
practice, roles and bare short forms they do not yet know to leave
alone, as the taxonomy below shows. Every fix suggested by a held-out
failure is listed here and *not applied*; policy rulings are applied
immediately, to the corpus and to the detector, because a ruling is
not tuning.

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

142 misses in 1,627 gold spans, in five classes, each a handful of
lines to fix and each *left unfixed* for the next round:

* **Registry numbers** (28): KBO/BCE `0712.445.303`, `HRB 71244`,
  Companies House eight-digit numbers, an Italian VAT. IBAN precision
  is 1.00 and recall 0.43 on the held-out split — the regex layer
  simply has no pattern for them.
* **Reference formats it has not seen** (29): Belgian *numéro de rôle*
  `A/26/02371`, firm references of the shape `LH/2026/0583-TRV`, a
  pre-notification `M.12384`. CASE_REF recall 0.56 — the same lesson
  as v0.7.7, on new shapes.
* **Short forms** (25 ORG): `Valdoire`, `Ambreval`, `Tremonval`,
  `Zilverberg` — the full form was caught but not propagated to its
  bare short form. (Codenames are no longer gold under ruling 1.)
* **Surname-only repeats** (36 PERSON): `Herbiet` ×3, `Roelandts`,
  `Thonnard`, `Brankovic`, `Pasqualotto`, `Rombouts` — the reference a
  practitioner uses after first mention. The dictionary propagates
  full names; it must propagate surnames.
* **Postcode-and-city lines and venues** (24 LOC): `1040 Brussels`,
  `2000 Antwerp`, `London EC4A 1NL` on their own letterhead line
  (16 of the 24 — the address pattern wants a street; the normaliser
  keeps any LOC with a number, but nothing detects the line), and
  `Hotel Löwenkranz`, `Kastanjehof conference centre` (a venue named
  on its own).

### 3. What Jude over-redacts on the held-out split (precision 0.64)

With the detector following the rulings, LOC is nearly clean (8
spurious spans, precision 0.93). The 634 spurious spans that remain
are ORG (461) and PERSON (153) — the *negative* classes:

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

### 6. A generative model as the extractor

`qwen3:4b` through Ollama, prompted to list every identifier as JSON
and told not to list institutions: F1 0.596 overall, 0.555 held out
(recall 0.58); **46 % of public-body mentions redacted** — the
instruction does not survive contact with a Belgian filing; 115 s per
page on the laptop; two documents returned invalid JSON and one timed
out twice. A hundred times the compute of the encoders for a result
below the rules alone. The generative route is a second reader at
most (see `efficiency-frontier.html`).

### 7. The review report as the last line

Of Jude's 142 held-out misses, the unverified-term report puts 50 in
front of the reviewer, at 22 items per document. The remaining 110 are
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
* A pattern for postcode-and-city lines (`1040 Brussels`, `London
  EC4A 1NL`) and for venues named on their own — 24 of the 142 misses.
* (Done in v0.8.1: rulings 1 and 6 in the detector, with the
  per-matter option to redact codenames.)
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

* Forty-four synthetic documents, one annotation policy whose seven
  open questions were ruled on 13 October 2026, every document
  reviewed in Word by a lawyer on the same day (no change required;
  see `annotation-protocol.html`). The numbers are indicative; the ranking and
  the size of the generalisation gap are robust.
* Where a mapping choice was ambiguous it was made in the external
  model's favour: dates and demographic labels are dropped rather than
  counted as false positives; adjacent name fragments are merged.
* Thresholds are the model cards' defaults; lowering NVIDIA's to 0.3
  changes little.
* Roblox's own card reports 45.5 % F1 on the Kaggle PII essay dataset;
  that number is not comparable to anything here and is not used.
