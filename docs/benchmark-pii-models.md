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
| `jude-full` | 0.623 | 0.918 | **0.742** | 0.774 | 151/613 (25%) | 34/134 | 12 | 0.848 | 622 | 2,612 MB |
| `jude-full-gliner-small` | 0.619 | 0.889 | **0.730** | 0.776 | 146/613 (24%) | 56/180 | 13 | 0.847 | 1,716 | 2,451 MB |
| `jude-full-no-gliner` | 0.612 | 0.859 | **0.715** | 0.768 | 143/613 (23%) | 86/230 | 13 | 0.844 | 3,001 | 3,037 MB |
| `jude-no-public-filter` | 0.528 | 0.870 | **0.657** | 0.724 | 437/613 (71%) | 37/211 | 11 | 0.819 | 724 | 3,506 MB |
| `rules-only` | 0.962 | 0.604 | **0.742** | 0.744 | 18/613 (3%) | 574/644 | 29 | 0.770 | 350,118 | 308 MB |
| `spacy-only` | 0.530 | 0.623 | **0.573** | 0.643 | 354/613 (58%) | 256/613 | 19 | 0.786 | 5,515 | 3,030 MB |
| `regex-only` | 0.956 | 0.148 | **0.257** | 0.257 | 0/613 (0%) | 1337/1386 | 42 | 0.287 | 3,453,664 | 308 MB |
| `gliner-large-v2.1-jude-labels` | 0.578 | 0.572 | **0.575** | 0.612 | 314/613 (51%) | 429/696 | 24 | 0.743 | 2,830 | 3,440 MB |
| `nvidia-gliner-pii-native` | 0.646 | 0.625 | **0.635** | 0.735 | 145/613 (24%) | 377/610 | 23 | 0.843 | 2,488 | 3,434 MB |
| `nvidia-gliner-pii-native-t03` | 0.637 | 0.646 | **0.641** | 0.747 | 157/613 (26%) | 344/576 | 22 | 0.853 | 2,508 | 3,553 MB |
| `nvidia-gliner-pii-jude-labels` | 0.631 | 0.539 | **0.582** | 0.597 | 244/613 (40%) | 477/750 | 23 | 0.755 | 2,799 | 3,898 MB |
| `pplx-pii-masking` | 0.916 | 0.468 | **0.619** | 0.669 | 15/613 (2%) | 716/866 | 30 | 0.755 | 2,107 | 755 MB |
| `pplx-pii-masking-cpu` | 0.916 | 0.469 | **0.620** | 0.670 | 15/613 (2%) | 714/864 | 30 | 0.757 | 130 | 1,572 MB |
| `roblox-pii-classifier` | — | — | — | — | — | — | — | 0.751 | 3,198 | 943 MB |
| `ollama-qwen3-4b` | 0.520 | 0.652 | **0.579** | 0.640 | 280/613 (46%) | 390/566 | 19 | 0.745 | 26 | 281 MB |

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
| `gliner-large-v2.1-jude-labels` | **0.594** (0.61 / 0.58, 19) | **0.570** (0.57 / 0.57, 25) |
| `nvidia-gliner-pii-native` | **0.662** (0.68 / 0.65, 19) | **0.628** (0.64 / 0.62, 25) |
| `nvidia-gliner-pii-native-t03` | **0.670** (0.67 / 0.67, 19) | **0.634** (0.63 / 0.64, 25) |
| `nvidia-gliner-pii-jude-labels` | **0.626** (0.68 / 0.58, 19) | **0.569** (0.62 / 0.53, 25) |
| `pplx-pii-masking` | **0.570** (0.89 / 0.42, 19) | **0.632** (0.92 / 0.48, 25) |
| `pplx-pii-masking-cpu` | **0.570** (0.89 / 0.42, 19) | **0.634** (0.92 / 0.48, 25) |
| `ollama-qwen3-4b` | **0.694** (0.59 / 0.85, 19) | **0.544** (0.50 / 0.60, 25) |

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
| `gliner-large-v2.1-jude-labels` | 0.740 | 0.746 | **0.743** | 765 | 269 | 260 |
| `nvidia-gliner-pii-native` | 0.878 | 0.811 | **0.843** | 831 | 115 | 194 |
| `nvidia-gliner-pii-native-t03` | 0.870 | 0.836 | **0.853** | 857 | 128 | 168 |
| `nvidia-gliner-pii-jude-labels` | 0.811 | 0.705 | **0.755** | 723 | 168 | 302 |
| `pplx-pii-masking` | 0.918 | 0.641 | **0.755** | 657 | 59 | 368 |
| `pplx-pii-masking-cpu` | 0.918 | 0.644 | **0.757** | 660 | 59 | 365 |
| `roblox-pii-classifier` | 0.875 | 0.658 | **0.751** | 699 | 100 | 364 |
| `ollama-qwen3-4b` | 0.726 | 0.765 | **0.745** | 784 | 296 | 241 |

## Per document (F1)

| Document | jude-full | jude-full-gliner-small | jude-full-no-gliner | jude-no-public-filter | rules-only | spacy-only | regex-only | gliner-large-v2.1-jude-labels | nvidia-gliner-pii-native | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-jude-labels | pplx-pii-masking | pplx-pii-masking-cpu | ollama-qwen3-4b |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 0.923 | 0.923 | 0.960 | 0.889 | 1.000 | 0.600 | 0.588 | 0.545 | 0.593 | 0.593 | 0.522 | 0.632 | 0.632 | 0.686 |
| doc_002_credit_facility_en | 0.963 | 0.963 | 0.963 | 0.839 | 0.783 | 0.640 | 0.526 | 0.364 | 0.692 | 0.692 | 0.476 | 0.783 | 0.783 | 0.545 |
| doc_003_solaris_jv_fr | 0.842 | 0.842 | 0.842 | 0.744 | 0.720 | 0.564 | 0.400 | 0.533 | 0.629 | 0.667 | 0.483 | 0.640 | 0.640 | 0.718 |
| doc_005_supply_agreement_en | 0.917 | 0.917 | 0.917 | 0.688 | 0.952 | 0.538 | 0.533 | 0.545 | 0.667 | 0.667 | 0.636 | 0.588 | 0.588 | 0.629 |
| doc_006_employment_dispute_en | 1.000 | 1.000 | 1.000 | 0.974 | 0.848 | 0.824 | 0.348 | 0.606 | 0.842 | 0.842 | 0.706 | 0.848 | 0.848 | 0.727 |
| doc_007_patent_litigation_en | 0.830 | 0.830 | 0.815 | 0.815 | 0.829 | 0.708 | 0.296 | 0.609 | 0.652 | 0.735 | 0.537 | 0.563 | 0.563 | 0.581 |
| doc_008_regulatory_submission_en | 0.960 | 0.960 | 0.960 | 0.873 | 0.769 | 0.760 | 0.286 | 0.667 | 0.750 | 0.750 | 0.732 | 0.345 | 0.345 | 0.880 |
| doc_009_witness_statement_en | 0.939 | 0.939 | 0.958 | 0.902 | 0.930 | 0.800 | 0.296 | 0.619 | 0.756 | 0.739 | 0.632 | 0.595 | 0.595 | 0.727 |
| doc_010_expert_economist_en | 0.973 | 0.919 | 0.919 | 0.766 | 0.615 | 0.714 | 0.200 | 0.500 | 0.600 | 0.645 | 0.500 | 0.261 | 0.261 | 0.600 |
| doc_011_sanctions_memo_en | 0.909 | 0.882 | 0.882 | 0.682 | 0.929 | 0.579 | 0.400 | 0.529 | 0.645 | 0.688 | 0.645 | 0.545 | 0.545 | 0.757 |
| doc_012_engagement_letter_en | 0.895 | 0.872 | 0.895 | 0.791 | 0.828 | 0.556 | 0.381 | 0.667 | 0.579 | 0.579 | 0.571 | 0.643 | 0.643 | 0.636 |
| doc_013_settlement_offer_en | 0.955 | 0.955 | 0.955 | 0.933 | 0.765 | 0.737 | 0.370 | 0.703 | 0.700 | 0.683 | 0.789 | 0.500 | 0.500 | 0.780 |
| doc_014_compliance_investigation_en | 0.865 | 0.865 | 0.865 | 0.800 | 0.897 | 0.629 | 0.381 | 0.514 | 0.667 | 0.629 | 0.606 | 0.720 | 0.720 | 0.780 |
| doc_015_corporate_restructuring_en | 0.943 | 0.962 | 0.962 | 0.877 | 0.837 | 0.760 | 0.276 | 0.619 | 0.636 | 0.622 | 0.667 | 0.485 | 0.485 | 0.706 |
| doc_016_tax_memo_en | 0.857 | 0.913 | 0.955 | 0.778 | 0.923 | 0.682 | 0.320 | 0.558 | 0.600 | 0.619 | 0.634 | 0.444 | 0.444 | 0.679 |
| doc_017_data_breach_notification_en | 0.839 | 0.897 | 0.929 | 0.722 | 0.960 | 0.519 | 0.444 | 0.562 | 0.621 | 0.581 | 0.667 | 0.667 | 0.667 | 0.686 |
| doc_018_cease_and_desist_en | 0.800 | 0.778 | 0.800 | 0.757 | 0.783 | 0.645 | 0.333 | 0.600 | 0.429 | 0.429 | 0.519 | 0.600 | 0.600 | 0.615 |
| doc_019_antitrust_complaint_en | 0.963 | 0.926 | 0.926 | 0.781 | 0.791 | 0.680 | 0.267 | 0.618 | 0.667 | 0.696 | 0.612 | 0.486 | 0.486 | 0.743 |
| doc_020_insolvency_update_en | 0.963 | 0.945 | 0.906 | 0.909 | 0.762 | 0.792 | 0.267 | 0.711 | 0.723 | 0.723 | 0.756 | 0.556 | 0.556 | 0.679 |
| doc_021_board_minutes_en | 0.837 | 0.828 | 0.855 | 0.765 | 0.816 | 0.727 | 0.131 | 0.718 | 0.804 | 0.807 | 0.709 | 0.564 | 0.564 | 0.431 |
| doc_022_nda_fr | 0.564 | 0.527 | 0.486 | 0.534 | 0.742 | 0.380 | 0.238 | 0.494 | 0.649 | 0.649 | 0.559 | 0.655 | 0.655 | 0.516 |
| doc_023_form_co_excerpt_en | 0.764 | 0.757 | 0.757 | 0.667 | 0.789 | 0.553 | 0.308 | 0.578 | 0.619 | 0.605 | 0.543 | 0.603 | 0.603 | 0.583 |
| doc_024_dawn_raid_memo_fr | 0.745 | 0.733 | 0.702 | 0.652 | 0.698 | 0.479 | 0.277 | 0.469 | 0.738 | 0.710 | 0.495 | 0.635 | 0.651 | 0.456 |
| doc_025_leniency_marker_en | 0.807 | 0.772 | 0.761 | 0.614 | 0.756 | 0.602 | 0.218 | 0.564 | 0.558 | 0.552 | 0.505 | 0.571 | 0.571 | 0.703 |
| doc_026_rfi_response_fr | 0.597 | 0.582 | 0.582 | 0.557 | 0.843 | 0.400 | 0.157 | 0.606 | 0.644 | 0.710 | 0.506 | 0.351 | 0.351 | 0.522 |
| doc_027_spa_excerpt_en | 0.733 | 0.739 | 0.717 | 0.672 | 0.744 | 0.647 | 0.246 | 0.538 | 0.695 | 0.722 | 0.602 | 0.709 | 0.709 | 0.659 |
| doc_028_client_email_thread_en | 0.855 | 0.793 | 0.793 | 0.813 | 0.514 | 0.595 | 0.267 | 0.596 | 0.722 | 0.734 | 0.679 | 0.809 | 0.809 | 0.660 |
| doc_029_cepani_request_en | 0.768 | 0.774 | 0.706 | 0.726 | 0.641 | 0.609 | 0.207 | 0.519 | 0.550 | 0.550 | 0.540 | 0.633 | 0.633 | 0.472 |
| doc_030_dpia_memo_fr | 0.716 | 0.620 | 0.600 | 0.629 | 0.781 | 0.383 | 0.261 | 0.562 | 0.610 | 0.619 | 0.548 | 0.600 | 0.600 | 0.585 |
| doc_031_dd_redflag_report_en | 0.722 | 0.698 | 0.704 | 0.652 | 0.767 | 0.708 | 0.111 | 0.642 | 0.571 | 0.566 | 0.642 | 0.556 | 0.556 | 0.000 |
| doc_032_conclusions_tribunal_fr | 0.673 | 0.615 | 0.490 | 0.532 | 0.557 | 0.327 | 0.128 | 0.614 | 0.535 | 0.539 | 0.614 | 0.557 | 0.557 | 0.526 |
| doc_033_transaction_fr | 0.580 | 0.574 | 0.488 | 0.571 | 0.730 | 0.314 | 0.298 | 0.559 | 0.545 | 0.557 | 0.500 | 0.697 | 0.697 | 0.557 |
| doc_034_state_aid_complaint_en | 0.598 | 0.596 | 0.596 | 0.561 | 0.700 | 0.583 | 0.190 | 0.535 | 0.548 | 0.558 | 0.444 | 0.593 | 0.593 | 0.483 |
| doc_035_data_room_index_en | 0.778 | 0.785 | 0.808 | 0.737 | 0.868 | 0.644 | 0.275 | 0.642 | 0.675 | 0.667 | 0.592 | 0.581 | 0.581 | 0.753 |
| doc_036_licenciement_motif_grave_fr | 0.678 | 0.701 | 0.619 | 0.661 | 0.754 | 0.442 | 0.377 | 0.602 | 0.659 | 0.674 | 0.649 | 0.712 | 0.712 | 0.496 |
| doc_037_merger_thresholds_memo_en | 0.775 | 0.766 | 0.791 | 0.536 | 0.753 | 0.517 | 0.277 | 0.424 | 0.419 | 0.422 | 0.333 | 0.578 | 0.578 | 0.509 |
| doc_038_reponse_apd_plainte_fr | 0.580 | 0.602 | 0.543 | 0.500 | 0.780 | 0.274 | 0.326 | 0.480 | 0.743 | 0.761 | 0.618 | 0.632 | 0.655 | 0.623 |
| doc_039_contrat_franchise_extrait_fr | 0.517 | 0.510 | 0.514 | 0.503 | 0.865 | 0.414 | 0.286 | 0.553 | 0.531 | 0.535 | 0.471 | 0.706 | 0.706 | 0.658 |
| doc_040_interview_notes_en | 0.720 | 0.756 | 0.634 | 0.398 | 0.455 | 0.590 | 0.050 | 0.567 | 0.681 | 0.667 | 0.551 | 0.700 | 0.700 | 0.416 |
| doc_041_shareholders_agreement_excerpt_en | 0.715 | 0.623 | 0.708 | 0.538 | 0.737 | 0.768 | 0.208 | 0.657 | 0.724 | 0.733 | 0.645 | 0.654 | 0.654 | 0.494 |
| doc_042_settlement_submission_en | 0.791 | 0.767 | 0.757 | 0.678 | 0.661 | 0.725 | 0.128 | 0.649 | 0.586 | 0.625 | 0.571 | 0.438 | 0.438 | 0.492 |
| doc_043_mise_en_demeure_fr | 0.541 | 0.604 | 0.604 | 0.541 | 0.738 | 0.370 | 0.327 | 0.452 | 0.615 | 0.608 | 0.611 | 0.667 | 0.667 | 0.651 |
| doc_044_fil_emails_budget_fr | 0.667 | 0.663 | 0.634 | 0.659 | 0.500 | 0.496 | 0.317 | 0.523 | 0.587 | 0.574 | 0.630 | 0.726 | 0.726 | 0.600 |
| doc_045_escrow_agreement_excerpt_en | 0.762 | 0.734 | 0.713 | 0.753 | 0.732 | 0.662 | 0.225 | 0.614 | 0.692 | 0.701 | 0.632 | 0.679 | 0.679 | 0.742 |

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

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.718 | 0.333 | 0.455 | 28 | 11 | 56 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.318 | 0.883 | 0.468 | 128 | 274 | 17 |
| ORG | 0.576 | 0.711 | 0.636 | 468 | 345 | 190 |
| PERSON | 0.858 | 0.656 | 0.743 | 307 | 51 | 161 |
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
| CASE_REF | 0.851 | 0.679 | 0.755 | 57 | 10 | 27 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 99 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 60 |
| LOC | 0.289 | 0.903 | 0.437 | 131 | 323 | 14 |
| ORG | 0.693 | 0.552 | 0.614 | 363 | 161 | 295 |
| PERSON | 0.948 | 0.697 | 0.803 | 326 | 18 | 142 |
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
- **`ollama-qwen3-4b`** — model `qwen3:4b`; device ollama; load 11.2 s.
  - Generative extraction via Ollama (local); thinking disabled, temperature 0.
  - Surfaces are located by exact string search — every occurrence counts.

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
| `ollama-qwen3-4b` (generative, 4 B) | 0.731 (0.65 / 0.84) | 0.555 (0.53 / 0.58) | −0.18 |
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
