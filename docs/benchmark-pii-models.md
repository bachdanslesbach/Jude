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

* **Corpus.** 58 gold-annotated documents in `benchmark/corpus/`
  (2,351 spans), English and French, in three splits. `dev` (19
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
  13 October 2026 under the annotation rulings of that day. Both splits
  are synthetic: professional secrecy rules out real files. `public`
  (14 documents, 8 EN / 6 FR) answers "it is all synthetic" with
  450–900-word excerpts of real published judgments and decisions —
  Commercial Court, Chancery and Court of Appeal of England and Wales
  (Find Case Law), US courts of appeals (govinfo), Cour de cassation de
  Belgique (JUPORTAL), Autorité belge de la concurrence — annotated
  *as if they were a client's file* (parties, counsel, judges, the
  document's own case number and registry numbers are gold; courts,
  statutes and cited precedents are public), each by two agents blind
  and then adjudicated; provenance and licences in
  `benchmark/public/README.md`. Annotation policy: redact anything
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

Span-level F1 across the 58-document gold corpus in `benchmark/corpus/`. Lenient overlap matching, type-strict (the *any type* column drops the type constraint). *Public-body over-redaction*: share of whitelisted institution / statute mentions (not covered by gold) that the runner redacted — lower is better. *Sentence F1*: every runner projected onto a sentence grid (positive iff it flags any character of the sentence), the only level at which message classifiers can be compared. Throughput and peak RSS measured on this machine, one runner per process.

## Aggregate

| Runner | Precision | Recall | **F1** | F1 (any type) | Public-body over-redaction | Misses surfaced by review | Review items / doc | Sentence F1 | chars/s | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| `gliner-large-v2.1-jude-labels-cpu` | 0.686 | 0.548 | **0.609** | 0.639 | 365/1466 (25%) | 733/1062 | 27 | 0.732 | 2,082 | 3,435 MB |
| `gliner-large-v2.1-jude-labels` | 0.686 | 0.548 | **0.609** | 0.639 | 365/1466 (25%) | 733/1062 | 27 | 0.732 | 2,099 | 2,792 MB |
| `gliner-small-v2.1-jude-labels` | 0.728 | 0.524 | **0.610** | 0.621 | 277/1466 (19%) | 772/1118 | 29 | 0.717 | 5,387 | 1,466 MB |
| `jude-full-gliner-small` | 0.684 | 0.872 | **0.767** | 0.803 | 350/1466 (24%) | 115/300 | 16 | 0.847 | 1,601 | 1,834 MB |
| `jude-full-no-gliner` | 0.689 | 0.837 | **0.756** | 0.802 | 311/1466 (21%) | 168/384 | 18 | 0.848 | 2,677 | 1,300 MB |
| `jude-full` | 0.688 | 0.900 | **0.780** | 0.811 | 347/1466 (24%) | 73/234 | 16 | 0.854 | 550 | 2,494 MB |
| `jude-no-public-filter` | 0.612 | 0.859 | **0.715** | 0.778 | 574/1466 (39%) | 83/331 | 16 | 0.836 | 525 | 3,334 MB |
| `nvidia-gliner-pii-jude-labels` | 0.809 | 0.507 | **0.624** | 0.632 | 236/1466 (16%) | 808/1158 | 28 | 0.743 | 2,692 | 3,540 MB |
| `nvidia-gliner-pii-native-t03` | 0.641 | 0.599 | **0.619** | 0.721 | 252/1466 (17%) | 592/942 | 24 | 0.828 | 2,358 | 3,502 MB |
| `nvidia-gliner-pii-native` | 0.649 | 0.573 | **0.609** | 0.703 | 233/1466 (16%) | 661/1004 | 24 | 0.812 | 2,380 | 1,865 MB |
| `ollama-qwen3-4b` | 0.520 | 0.652 | **0.579** | 0.640 | 280/613 (46%) | 390/566 | 19 | 0.745 | 26 | 281 MB |
| `pplx-pii-masking-cpu` | 0.905 | 0.373 | **0.529** | 0.569 | 31/1466 (2%) | 1252/1473 | 33 | 0.647 | 130 | 1,363 MB |
| `pplx-pii-masking` | 0.906 | 0.373 | **0.528** | 0.568 | 30/1466 (2%) | 1254/1475 | 33 | 0.646 | 1,903 | 361 MB |
| `regex-only` | 0.949 | 0.111 | **0.198** | 0.198 | 3/1466 (0%) | 1981/2091 | 44 | 0.221 | 3,465,718 | 289 MB |
| `roblox-pii-classifier` | — | — | — | — | — | — | — | 0.674 | 3,275 | 750 MB |
| `rules-only` | 0.950 | 0.473 | **0.632** | 0.633 | 36/1466 (2%) | 1096/1239 | 32 | 0.672 | 346,220 | 290 MB |
| `spacy-only` | 0.672 | 0.652 | **0.661** | 0.718 | 391/1466 (27%) | 406/819 | 23 | 0.799 | 4,930 | 1,234 MB |

## By corpus split

`dev`: the documents Jude's whitelist and stop-lists were tuned on. `heldout`: added later, never consulted while tuning — the honest number.

| Runner | dev — F1 (P / R, docs) | heldout — F1 (P / R, docs) | public — F1 (P / R, docs) |
|---|---|---|---|
| `gliner-large-v2.1-jude-labels-cpu` | **0.624** (0.71 / 0.56, 19) | **0.600** (0.67 / 0.55, 25) | **0.619** (0.71 / 0.55, 14) |
| `gliner-large-v2.1-jude-labels` | **0.624** (0.71 / 0.56, 19) | **0.600** (0.67 / 0.55, 25) | **0.619** (0.71 / 0.55, 14) |
| `gliner-small-v2.1-jude-labels` | **0.670** (0.78 / 0.59, 19) | **0.541** (0.69 / 0.45, 25) | **0.691** (0.76 / 0.63, 14) |
| `jude-full-gliner-small` | **0.941** (0.90 / 0.98, 19) | **0.732** (0.64 / 0.86, 25) | **0.751** (0.67 / 0.85, 14) |
| `jude-full-no-gliner` | **0.946** (0.92 / 0.97, 19) | **0.714** (0.64 / 0.81, 25) | **0.744** (0.69 / 0.81, 14) |
| `jude-full` | **0.952** (0.92 / 0.99, 19) | **0.745** (0.64 / 0.89, 25) | **0.768** (0.68 / 0.88, 14) |
| `jude-no-public-filter` | **0.879** (0.80 / 0.98, 19) | **0.667** (0.56 / 0.83, 25) | **0.730** (0.64 / 0.85, 14) |
| `nvidia-gliner-pii-jude-labels` | **0.654** (0.82 / 0.55, 19) | **0.619** (0.79 / 0.51, 25) | **0.617** (0.84 / 0.49, 14) |
| `nvidia-gliner-pii-native-t03` | **0.670** (0.67 / 0.67, 19) | **0.634** (0.63 / 0.64, 25) | **0.563** (0.65 / 0.49, 14) |
| `nvidia-gliner-pii-native` | **0.662** (0.68 / 0.65, 19) | **0.628** (0.64 / 0.62, 25) | **0.539** (0.66 / 0.46, 14) |
| `ollama-qwen3-4b` | **0.694** (0.59 / 0.85, 19) | **0.544** (0.50 / 0.60, 25) | — |
| `pplx-pii-masking-cpu` | **0.570** (0.89 / 0.42, 19) | **0.634** (0.92 / 0.48, 25) | **0.267** (0.84 / 0.16, 14) |
| `pplx-pii-masking` | **0.570** (0.89 / 0.42, 19) | **0.632** (0.92 / 0.48, 25) | **0.267** (0.85 / 0.16, 14) |
| `regex-only` | **0.349** (0.92 / 0.22, 19) | **0.229** (0.98 / 0.13, 25) | **0.051** (0.86 / 0.03, 14) |
| `rules-only` | **0.836** (0.99 / 0.72, 19) | **0.714** (0.95 / 0.57, 25) | **0.296** (0.87 / 0.18, 14) |
| `spacy-only` | **0.726** (0.78 / 0.68, 19) | **0.593** (0.61 / 0.58, 25) | **0.749** (0.74 / 0.76, 14) |

## Sentence level

| Runner | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| `gliner-large-v2.1-jude-labels-cpu` | 0.768 | 0.699 | **0.732** | 1073 | 325 | 461 |
| `gliner-large-v2.1-jude-labels` | 0.768 | 0.699 | **0.732** | 1073 | 325 | 461 |
| `gliner-small-v2.1-jude-labels` | 0.796 | 0.653 | **0.717** | 1001 | 257 | 533 |
| `jude-full-gliner-small` | 0.783 | 0.923 | **0.847** | 1416 | 393 | 118 |
| `jude-full-no-gliner` | 0.795 | 0.909 | **0.848** | 1394 | 359 | 140 |
| `jude-full` | 0.782 | 0.940 | **0.854** | 1442 | 401 | 92 |
| `jude-no-public-filter` | 0.752 | 0.942 | **0.836** | 1445 | 477 | 89 |
| `nvidia-gliner-pii-jude-labels` | 0.862 | 0.653 | **0.743** | 1002 | 160 | 532 |
| `nvidia-gliner-pii-native-t03` | 0.871 | 0.788 | **0.828** | 1209 | 179 | 325 |
| `nvidia-gliner-pii-native` | 0.880 | 0.754 | **0.812** | 1156 | 158 | 378 |
| `ollama-qwen3-4b` | 0.726 | 0.765 | **0.745** | 784 | 296 | 241 |
| `pplx-pii-masking-cpu` | 0.905 | 0.504 | **0.647** | 773 | 81 | 761 |
| `pplx-pii-masking` | 0.906 | 0.502 | **0.646** | 770 | 80 | 764 |
| `regex-only` | 0.974 | 0.125 | **0.221** | 191 | 5 | 1343 |
| `roblox-pii-classifier` | 0.845 | 0.560 | **0.674** | 859 | 157 | 675 |
| `rules-only` | 0.936 | 0.524 | **0.672** | 804 | 55 | 730 |
| `spacy-only` | 0.807 | 0.790 | **0.799** | 1212 | 289 | 322 |

## Per document (F1)

| Document | gliner-large-v2.1-jude-labels-cpu | gliner-large-v2.1-jude-labels | gliner-small-v2.1-jude-labels | jude-full-gliner-small | jude-full-no-gliner | jude-full | jude-no-public-filter | nvidia-gliner-pii-jude-labels | nvidia-gliner-pii-native-t03 | nvidia-gliner-pii-native | ollama-qwen3-4b | pplx-pii-masking-cpu | pplx-pii-masking | regex-only | rules-only | spacy-only |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| doc_001_term_sheet_en | 0.632 | 0.632 | 0.600 | 0.960 | 1.000 | 1.000 | 0.960 | 0.632 | 0.593 | 0.593 | 0.686 | 0.632 | 0.632 | 0.588 | 1.000 | 0.632 |
| doc_002_credit_facility_en | 0.400 | 0.400 | 0.609 | 0.963 | 0.963 | 0.963 | 0.867 | 0.455 | 0.692 | 0.692 | 0.545 | 0.783 | 0.783 | 0.526 | 0.783 | 0.667 |
| doc_003_solaris_jv_fr | 0.571 | 0.571 | 0.759 | 0.941 | 0.970 | 0.970 | 0.842 | 0.615 | 0.667 | 0.629 | 0.718 | 0.640 | 0.640 | 0.400 | 0.720 | 0.647 |
| doc_005_supply_agreement_en | 0.632 | 0.632 | 0.667 | 1.000 | 1.000 | 1.000 | 0.759 | 0.737 | 0.667 | 0.667 | 0.629 | 0.588 | 0.588 | 0.533 | 0.952 | 0.609 |
| doc_006_employment_dispute_en | 0.625 | 0.625 | 0.621 | 1.000 | 0.973 | 1.000 | 0.974 | 0.562 | 0.842 | 0.842 | 0.727 | 0.848 | 0.848 | 0.348 | 0.848 | 0.788 |
| doc_007_patent_litigation_en | 0.636 | 0.636 | 0.622 | 0.830 | 0.863 | 0.846 | 0.917 | 0.579 | 0.735 | 0.652 | 0.581 | 0.563 | 0.563 | 0.296 | 0.829 | 0.829 |
| doc_008_regulatory_submission_en | 0.634 | 0.634 | 0.700 | 0.979 | 0.979 | 0.979 | 0.885 | 0.667 | 0.750 | 0.750 | 0.880 | 0.345 | 0.345 | 0.286 | 0.769 | 0.766 |
| doc_009_witness_statement_en | 0.600 | 0.600 | 0.529 | 0.958 | 0.979 | 0.958 | 0.958 | 0.629 | 0.739 | 0.756 | 0.727 | 0.595 | 0.595 | 0.296 | 0.930 | 0.857 |
| doc_010_expert_economist_en | 0.500 | 0.500 | 0.649 | 0.919 | 0.919 | 0.973 | 0.766 | 0.467 | 0.645 | 0.600 | 0.600 | 0.261 | 0.261 | 0.200 | 0.615 | 0.714 |
| doc_011_sanctions_memo_en | 0.581 | 0.581 | 0.710 | 0.968 | 0.968 | 1.000 | 0.769 | 0.714 | 0.688 | 0.645 | 0.757 | 0.545 | 0.545 | 0.400 | 0.929 | 0.667 |
| doc_012_engagement_letter_en | 0.828 | 0.828 | 0.571 | 0.919 | 0.971 | 0.971 | 0.944 | 0.741 | 0.579 | 0.579 | 0.636 | 0.643 | 0.643 | 0.381 | 0.828 | 0.690 |
| doc_013_settlement_offer_en | 0.778 | 0.778 | 0.811 | 0.955 | 0.955 | 0.955 | 0.933 | 0.811 | 0.683 | 0.700 | 0.780 | 0.500 | 0.500 | 0.370 | 0.765 | 0.737 |
| doc_014_compliance_investigation_en | 0.600 | 0.600 | 0.774 | 0.970 | 0.970 | 0.970 | 0.914 | 0.741 | 0.629 | 0.667 | 0.780 | 0.720 | 0.720 | 0.381 | 0.897 | 0.710 |
| doc_015_corporate_restructuring_en | 0.667 | 0.667 | 0.780 | 0.980 | 0.960 | 0.980 | 0.980 | 0.718 | 0.622 | 0.636 | 0.706 | 0.485 | 0.485 | 0.276 | 0.837 | 0.800 |
| doc_016_tax_memo_en | 0.649 | 0.649 | 0.737 | 0.977 | 1.000 | 0.955 | 0.955 | 0.765 | 0.619 | 0.600 | 0.679 | 0.444 | 0.444 | 0.320 | 0.923 | 0.811 |
| doc_017_data_breach_notification_en | 0.552 | 0.552 | 0.636 | 0.963 | 0.963 | 0.897 | 0.788 | 0.696 | 0.581 | 0.621 | 0.686 | 0.667 | 0.667 | 0.444 | 0.960 | 0.583 |
| doc_018_cease_and_desist_en | 0.692 | 0.692 | 0.560 | 0.875 | 0.875 | 0.875 | 0.848 | 0.636 | 0.429 | 0.429 | 0.615 | 0.600 | 0.600 | 0.333 | 0.783 | 0.692 |
| doc_019_antitrust_complaint_en | 0.630 | 0.630 | 0.652 | 0.926 | 0.926 | 0.963 | 0.794 | 0.625 | 0.696 | 0.667 | 0.743 | 0.486 | 0.486 | 0.267 | 0.791 | 0.694 |
| doc_020_insolvency_update_en | 0.585 | 0.585 | 0.634 | 0.885 | 0.840 | 0.902 | 0.846 | 0.619 | 0.723 | 0.723 | 0.679 | 0.556 | 0.556 | 0.267 | 0.762 | 0.682 |
| doc_021_board_minutes_en | 0.757 | 0.757 | 0.660 | 0.891 | 0.898 | 0.893 | 0.819 | 0.776 | 0.807 | 0.804 | 0.431 | 0.564 | 0.564 | 0.131 | 0.816 | 0.786 |
| doc_022_nda_fr | 0.519 | 0.519 | 0.542 | 0.611 | 0.578 | 0.629 | 0.574 | 0.603 | 0.649 | 0.649 | 0.516 | 0.655 | 0.655 | 0.238 | 0.742 | 0.423 |
| doc_023_form_co_excerpt_en | 0.587 | 0.587 | 0.587 | 0.736 | 0.724 | 0.748 | 0.672 | 0.507 | 0.605 | 0.619 | 0.583 | 0.603 | 0.603 | 0.308 | 0.789 | 0.524 |
| doc_024_dawn_raid_memo_fr | 0.540 | 0.540 | 0.475 | 0.756 | 0.736 | 0.767 | 0.676 | 0.523 | 0.710 | 0.738 | 0.456 | 0.651 | 0.635 | 0.277 | 0.698 | 0.509 |
| doc_025_leniency_marker_en | 0.612 | 0.612 | 0.527 | 0.857 | 0.846 | 0.876 | 0.667 | 0.585 | 0.552 | 0.558 | 0.703 | 0.571 | 0.571 | 0.218 | 0.756 | 0.660 |
| doc_026_rfi_response_fr | 0.659 | 0.659 | 0.613 | 0.696 | 0.690 | 0.689 | 0.656 | 0.597 | 0.710 | 0.644 | 0.522 | 0.351 | 0.351 | 0.157 | 0.843 | 0.476 |
| doc_027_spa_excerpt_en | 0.532 | 0.532 | 0.578 | 0.708 | 0.667 | 0.708 | 0.661 | 0.565 | 0.722 | 0.695 | 0.659 | 0.709 | 0.709 | 0.246 | 0.744 | 0.593 |
| doc_028_client_email_thread_en | 0.612 | 0.612 | 0.506 | 0.832 | 0.839 | 0.877 | 0.839 | 0.742 | 0.734 | 0.722 | 0.660 | 0.809 | 0.809 | 0.267 | 0.514 | 0.653 |
| doc_029_cepani_request_en | 0.566 | 0.566 | 0.542 | 0.839 | 0.759 | 0.842 | 0.845 | 0.610 | 0.550 | 0.550 | 0.472 | 0.633 | 0.633 | 0.207 | 0.641 | 0.680 |
| doc_030_dpia_memo_fr | 0.642 | 0.642 | 0.571 | 0.690 | 0.706 | 0.830 | 0.724 | 0.618 | 0.619 | 0.610 | 0.585 | 0.600 | 0.600 | 0.261 | 0.781 | 0.462 |
| doc_031_dd_redflag_report_en | 0.673 | 0.673 | 0.630 | 0.715 | 0.733 | 0.744 | 0.672 | 0.731 | 0.566 | 0.571 | 0.000 | 0.556 | 0.556 | 0.111 | 0.767 | 0.734 |
| doc_032_conclusions_tribunal_fr | 0.691 | 0.691 | 0.592 | 0.731 | 0.562 | 0.817 | 0.653 | 0.753 | 0.539 | 0.535 | 0.526 | 0.557 | 0.557 | 0.128 | 0.557 | 0.400 |
| doc_033_transaction_fr | 0.617 | 0.617 | 0.378 | 0.622 | 0.606 | 0.633 | 0.628 | 0.600 | 0.557 | 0.545 | 0.557 | 0.697 | 0.697 | 0.298 | 0.730 | 0.421 |
| doc_034_state_aid_complaint_en | 0.587 | 0.587 | 0.560 | 0.636 | 0.642 | 0.642 | 0.617 | 0.571 | 0.558 | 0.548 | 0.483 | 0.593 | 0.593 | 0.190 | 0.700 | 0.674 |
| doc_035_data_room_index_en | 0.579 | 0.579 | 0.462 | 0.777 | 0.800 | 0.769 | 0.741 | 0.545 | 0.667 | 0.675 | 0.753 | 0.581 | 0.581 | 0.275 | 0.868 | 0.667 |
| doc_036_licenciement_motif_grave_fr | 0.608 | 0.608 | 0.618 | 0.759 | 0.680 | 0.734 | 0.716 | 0.704 | 0.674 | 0.659 | 0.496 | 0.712 | 0.712 | 0.377 | 0.754 | 0.494 |
| doc_037_merger_thresholds_memo_en | 0.490 | 0.490 | 0.489 | 0.784 | 0.816 | 0.810 | 0.690 | 0.424 | 0.422 | 0.419 | 0.509 | 0.578 | 0.578 | 0.277 | 0.753 | 0.592 |
| doc_038_reponse_apd_plainte_fr | 0.545 | 0.545 | 0.520 | 0.682 | 0.595 | 0.660 | 0.549 | 0.677 | 0.761 | 0.743 | 0.623 | 0.655 | 0.632 | 0.326 | 0.780 | 0.317 |
| doc_039_contrat_franchise_extrait_fr | 0.642 | 0.642 | 0.406 | 0.583 | 0.592 | 0.592 | 0.578 | 0.600 | 0.535 | 0.531 | 0.658 | 0.706 | 0.706 | 0.286 | 0.865 | 0.527 |
| doc_040_interview_notes_en | 0.578 | 0.578 | 0.652 | 0.775 | 0.637 | 0.730 | 0.398 | 0.605 | 0.667 | 0.681 | 0.416 | 0.700 | 0.700 | 0.050 | 0.455 | 0.600 |
| doc_041_shareholders_agreement_excerpt_en | 0.661 | 0.661 | 0.488 | 0.637 | 0.724 | 0.727 | 0.562 | 0.691 | 0.733 | 0.724 | 0.494 | 0.654 | 0.654 | 0.208 | 0.737 | 0.779 |
| doc_042_settlement_submission_en | 0.725 | 0.725 | 0.569 | 0.800 | 0.805 | 0.840 | 0.717 | 0.574 | 0.625 | 0.586 | 0.492 | 0.438 | 0.438 | 0.128 | 0.661 | 0.760 |
| doc_043_mise_en_demeure_fr | 0.456 | 0.456 | 0.414 | 0.644 | 0.682 | 0.574 | 0.594 | 0.625 | 0.608 | 0.615 | 0.651 | 0.667 | 0.667 | 0.327 | 0.738 | 0.417 |
| doc_044_fil_emails_budget_fr | 0.490 | 0.490 | 0.447 | 0.761 | 0.721 | 0.752 | 0.759 | 0.608 | 0.574 | 0.587 | 0.600 | 0.726 | 0.726 | 0.317 | 0.500 | 0.536 |
| doc_045_escrow_agreement_excerpt_en | 0.538 | 0.538 | 0.561 | 0.740 | 0.698 | 0.719 | 0.719 | 0.585 | 0.701 | 0.692 | 0.742 | 0.679 | 0.679 | 0.225 | 0.732 | 0.645 |
| doc_101_commercial_2026_central_termica_v_santan_en | 0.773 | 0.773 | 0.791 | 0.807 | 0.815 | 0.829 | 0.807 | 0.692 | 0.390 | 0.364 | — | 0.231 | 0.231 | 0.043 | 0.537 | 0.828 |
| doc_102_commercial_2026_intralinks_v_nexans_en | 0.747 | 0.747 | 0.780 | 0.699 | 0.706 | 0.712 | 0.685 | 0.753 | 0.587 | 0.593 | — | 0.340 | 0.340 | 0.050 | 0.386 | 0.810 |
| doc_103_chancery_2026_glencore_v_prax_lindsey_en | 0.714 | 0.714 | 0.682 | 0.759 | 0.748 | 0.771 | 0.778 | 0.687 | 0.579 | 0.605 | — | 0.333 | 0.333 | 0.045 | 0.545 | 0.848 |
| doc_104_chancery_2026_nocopyrightsounds_v_aei_mu_en | 0.874 | 0.874 | 0.815 | 0.920 | 0.916 | 0.943 | 0.932 | 0.708 | 0.685 | 0.562 | — | 0.360 | 0.360 | 0.048 | 0.292 | 0.892 |
| doc_105_coa_2026_rasmala_v_trafigura_en | 0.745 | 0.745 | 0.829 | 0.918 | 0.949 | 0.967 | 0.952 | 0.674 | 0.648 | 0.648 | — | 0.290 | 0.290 | 0.033 | 0.356 | 0.914 |
| doc_106_ca3_2026_sandoz_v_united_therapeutics_en | 0.718 | 0.718 | 0.765 | 0.841 | 0.785 | 0.827 | 0.822 | 0.621 | 0.563 | 0.532 | — | 0.352 | 0.352 | 0.022 | 0.240 | 0.850 |
| doc_107_ca6_2026_trustees_main_v_appliancesmart_en | 0.512 | 0.512 | 0.890 | 0.895 | 0.906 | 0.939 | 0.939 | 0.743 | 0.740 | 0.686 | — | 0.067 | 0.067 | 0.000 | 0.089 | 0.921 |
| doc_108_cafc_2026_alexsam_v_simon_property_group_en | 0.474 | 0.474 | 0.613 | 0.768 | 0.768 | 0.738 | 0.556 | 0.504 | 0.425 | 0.410 | — | 0.260 | 0.260 | 0.023 | 0.129 | 0.744 |
| doc_109_cass_2023_international_tools_service_v__fr | 0.353 | 0.353 | 0.400 | 0.500 | 0.541 | 0.465 | 0.465 | 0.462 | 0.615 | 0.615 | — | 0.387 | 0.387 | 0.133 | 0.250 | 0.533 |
| doc_110_cass_2025_ville_de_virton_v_trema_archit_fr | 0.464 | 0.464 | 0.486 | 0.642 | 0.739 | 0.642 | 0.642 | 0.634 | 0.650 | 0.650 | — | 0.320 | 0.320 | 0.095 | 0.182 | 0.762 |
| doc_111_cass_2025_g_v_etat_belge_fr | 0.632 | 0.632 | 0.343 | 0.698 | 0.811 | 0.732 | 0.732 | 0.743 | 0.778 | 0.800 | — | 0.765 | 0.765 | 0.111 | 0.300 | 0.757 |
| doc_112_cc_2026_rossel_ipm_fr | 0.552 | 0.552 | 0.652 | 0.739 | 0.670 | 0.731 | 0.660 | 0.496 | 0.552 | 0.554 | — | 0.224 | 0.224 | 0.149 | 0.418 | 0.551 |
| doc_113_rpr_2026_rfb_v_urbsfa_fr | 0.374 | 0.374 | 0.366 | 0.561 | 0.507 | 0.638 | 0.623 | 0.418 | 0.481 | 0.396 | — | 0.031 | 0.031 | 0.031 | 0.061 | 0.477 |
| doc_114_ccs_2026_rmga_pierre_joel_aag_fr | 0.646 | 0.646 | 0.565 | 0.500 | 0.509 | 0.532 | 0.496 | 0.549 | 0.371 | 0.358 | — | 0.154 | 0.158 | 0.054 | 0.364 | 0.510 |

## Per entity type

### gliner-large-v2.1-jude-labels-cpu — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.733 | 0.390 | 0.509 | 55 | 20 | 86 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 101 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| LOC | 0.615 | 0.766 | 0.683 | 128 | 80 | 39 |
| ORG | 0.636 | 0.606 | 0.621 | 686 | 393 | 446 |
| PERSON | 0.811 | 0.685 | 0.743 | 420 | 98 | 193 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 88 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### gliner-large-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.733 | 0.390 | 0.509 | 55 | 20 | 86 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 101 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| LOC | 0.615 | 0.766 | 0.683 | 128 | 80 | 39 |
| ORG | 0.636 | 0.606 | 0.621 | 686 | 393 | 446 |
| PERSON | 0.811 | 0.685 | 0.743 | 420 | 98 | 193 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 88 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### gliner-small-v2.1-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.947 | 0.128 | 0.225 | 18 | 1 | 123 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 101 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| LOC | 0.589 | 0.617 | 0.602 | 103 | 72 | 64 |
| ORG | 0.721 | 0.689 | 0.705 | 780 | 302 | 352 |
| PERSON | 0.794 | 0.542 | 0.644 | 332 | 86 | 281 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 88 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

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

### nvidia-gliner-pii-jude-labels — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.862 | 0.532 | 0.658 | 75 | 12 | 66 |
| EMAIL | 0.000 | 0.000 | 0.000 | 0 | 0 | 101 |
| IBAN | 0.000 | 0.000 | 0.000 | 0 | 0 | 80 |
| LOC | 0.864 | 0.725 | 0.788 | 121 | 19 | 46 |
| ORG | 0.723 | 0.498 | 0.590 | 564 | 216 | 568 |
| PERSON | 0.927 | 0.706 | 0.802 | 433 | 34 | 180 |
| PHONE | 0.000 | 0.000 | 0.000 | 0 | 0 | 88 |
| URL | 0.000 | 0.000 | 0.000 | 0 | 0 | 29 |

### nvidia-gliner-pii-native-t03 — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 141 |
| EMAIL | 0.769 | 0.297 | 0.429 | 30 | 9 | 71 |
| IBAN | 0.465 | 0.500 | 0.482 | 40 | 46 | 40 |
| LOC | 0.239 | 0.940 | 0.382 | 157 | 499 | 10 |
| ORG | 0.942 | 0.458 | 0.617 | 519 | 32 | 613 |
| PERSON | 0.749 | 0.940 | 0.834 | 576 | 193 | 37 |
| PHONE | 0.897 | 0.886 | 0.891 | 78 | 9 | 10 |
| URL | 0.900 | 0.310 | 0.462 | 9 | 1 | 20 |

### nvidia-gliner-pii-native — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 141 |
| EMAIL | 0.853 | 0.287 | 0.430 | 29 | 5 | 72 |
| IBAN | 0.521 | 0.463 | 0.490 | 37 | 34 | 43 |
| LOC | 0.252 | 0.934 | 0.396 | 156 | 464 | 11 |
| ORG | 0.944 | 0.417 | 0.578 | 472 | 28 | 660 |
| PERSON | 0.754 | 0.938 | 0.836 | 575 | 188 | 38 |
| PHONE | 0.909 | 0.795 | 0.848 | 70 | 7 | 18 |
| URL | 0.889 | 0.276 | 0.421 | 8 | 1 | 21 |

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

### pplx-pii-masking-cpu — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 141 |
| EMAIL | 0.902 | 1.000 | 0.948 | 101 | 11 | 0 |
| IBAN | 0.552 | 0.662 | 0.602 | 53 | 43 | 27 |
| LOC | 0.983 | 0.677 | 0.801 | 113 | 2 | 54 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 1132 |
| PERSON | 0.944 | 0.847 | 0.893 | 519 | 31 | 94 |
| PHONE | 0.940 | 0.898 | 0.919 | 79 | 5 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

### pplx-pii-masking — per type
| Type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| CASE_REF | 0.000 | 0.000 | 0.000 | 0 | 0 | 141 |
| EMAIL | 0.902 | 1.000 | 0.948 | 101 | 11 | 0 |
| IBAN | 0.552 | 0.662 | 0.602 | 53 | 43 | 27 |
| LOC | 0.982 | 0.671 | 0.797 | 112 | 2 | 55 |
| ORG | 0.000 | 0.000 | 0.000 | 0 | 0 | 1132 |
| PERSON | 0.944 | 0.845 | 0.892 | 518 | 31 | 95 |
| PHONE | 0.952 | 0.898 | 0.924 | 79 | 4 | 9 |
| URL | 1.000 | 0.448 | 0.619 | 13 | 0 | 16 |

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

## Runner notes

- **`gliner-large-v2.1-jude-labels-cpu`** — model `urchade/gliner_large-v2.1`; device cpu; load 14.7 s; threshold 0.5.
- **`gliner-large-v2.1-jude-labels`** — model `urchade/gliner_large-v2.1`; device mps; load 16.3 s; threshold 0.5.
- **`gliner-small-v2.1-jude-labels`** — model `urchade/gliner_small-v2.1`; device mps; load 9.7 s; threshold 0.5.
- **`jude-full-gliner-small`** — device cpu; load 0.0 s.
- **`jude-full-no-gliner`** — device cpu; load 0.0 s.
- **`jude-full`** — device cpu; load 0.0 s.
- **`jude-no-public-filter`** — device cpu; load 0.0 s.
- **`nvidia-gliner-pii-jude-labels`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.5 s; threshold 0.5.
- **`nvidia-gliner-pii-native-t03`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 12.6 s; threshold 0.3.
- **`nvidia-gliner-pii-native`** — model `nvidia/gliner-PII` @ `bd23e8ef`; device mps; load 14.3 s; threshold 0.5.
- **`ollama-qwen3-4b`** — model `qwen3:4b`; device ollama; load 11.2 s; **not run on 14 corpus document(s)**: doc_101_commercial_2026_central_termica_v_santan_en, doc_102_commercial_2026_intralinks_v_nexans_en, doc_103_chancery_2026_glencore_v_prax_lindsey_en, doc_104_chancery_2026_nocopyrightsounds_v_aei_mu_en, doc_105_coa_2026_rasmala_v_trafigura_en, doc_106_ca3_2026_sandoz_v_united_therapeutics_en, doc_107_ca6_2026_trustees_main_v_appliancesmart_en, doc_108_cafc_2026_alexsam_v_simon_property_group_en, doc_109_cass_2023_international_tools_service_v__fr, doc_110_cass_2025_ville_de_virton_v_trema_archit_fr, doc_111_cass_2025_g_v_etat_belge_fr, doc_112_cc_2026_rossel_ipm_fr, doc_113_rpr_2026_rfb_v_urbsfa_fr, doc_114_ccs_2026_rmga_pierre_joel_aag_fr.
  - Generative extraction via Ollama (local); thinking disabled, temperature 0.
  - Surfaces are located by exact string search — every occurrence counts.
- **`pplx-pii-masking-cpu`** — model `perplexity-ai/pplx-pii-masking` @ `f1f90a53`; device cpu; load 5.7 s; out-of-schema predictions dropped: other_pii×9, private_date×175; mean document sensitivity 0.18.
  - No organisation label: ORG recall is 0 by construction.
  - `private_date` / `other_pii` predictions dropped as out-of-schema (counted, not scored as FP).
  - Input truncated at 4096 tokens; corpus documents are far shorter.
- **`pplx-pii-masking`** — model `perplexity-ai/pplx-pii-masking` @ `f1f90a53`; device mps; load 8.1 s; out-of-schema predictions dropped: other_pii×9, private_date×175; mean document sensitivity 0.18.
  - No organisation label: ORG recall is 0 by construction.
  - `private_date` / `other_pii` predictions dropped as out-of-schema (counted, not scored as FP).
  - Input truncated at 4096 tokens; corpus documents are far shorter.
- **`regex-only`** — device cpu; load 0.1 s.
- **`roblox-pii-classifier`** — model `roblox/roblox-pii-classifier` @ `253c2057`; device mps; load 21.0 s; threshold 0.2691.
  - Message-level classifier (asking-for / giving PII); no spans. Scored on the sentence grid only.
  - Trained on chat; the model card itself reports 45.5% F1 on the Kaggle PII essay dataset.
- **`rules-only`** — device cpu; load 0.1 s.
  - Deterministic layers only: regex + patterns + known entities + whitelist.
- **`spacy-only`** — device cpu; load 0.1 s.

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

## Real documents: the `public` split

Fourteen excerpts of real published judgments and decisions
(`benchmark/public/README.md`: Commercial Court, Chancery Division and
Court of Appeal of England and Wales; US courts of appeals; Cour de
cassation de Belgique; Autorité belge de la concurrence) were added on
15 October 2026, annotated *as if they were a client's file* by two
agents blind and adjudicated by a third. Nothing in Jude was tuned on
them, and unlike the held-out split they were not drafted by an agent —
so they test the drafting bias as well as the tuning bias. The lawyer's
Word pass on these fourteen is still to come; the policy questions they
raised (non-party companies, a party's brands, the matter's own earlier
decisions, counsel's addresses) are items 8–17 of
`benchmark/synth/POLICY_QUESTIONS.md`, with the defaults applied here.

| System | heldout F1 (P / R) | public F1 (P / R) | shift |
|---|---|---|---|
| `jude-full` | 0.745 (0.64 / 0.89) | **0.768** (0.68 / 0.88) | +0.02 |
| `jude-full-gliner-small` | 0.732 (0.64 / 0.86) | 0.751 (0.67 / 0.85) | +0.02 |
| `jude-full-no-gliner` | 0.714 (0.64 / 0.81) | 0.744 (0.69 / 0.81) | +0.03 |
| `spacy-only` | 0.593 (0.61 / 0.58) | 0.749 (0.74 / 0.76) | +0.16 |
| `gliner-small-v2.1-jude-labels` | 0.541 (0.69 / 0.45) | 0.691 (0.76 / 0.63) | +0.15 |
| `gliner-large-v2.1-jude-labels` | 0.600 (0.67 / 0.55) | 0.619 (0.71 / 0.55) | +0.02 |
| `nvidia-gliner-pii-jude-labels` | 0.619 (0.79 / 0.51) | 0.617 (0.84 / 0.49) | 0.00 |
| `nvidia-gliner-pii-native` | 0.628 (0.64 / 0.62) | 0.539 (0.66 / 0.46) | −0.09 |
| `pplx-pii-masking` | 0.632 (0.92 / 0.48) | 0.267 (0.85 / 0.16) | −0.37 |
| `rules-only` | 0.714 (0.95 / 0.57) | 0.296 (0.87 / 0.18) | −0.42 |
| `regex-only` | 0.229 (0.98 / 0.13) | 0.051 (0.86 / 0.03) | −0.18 |
| `roblox-pii-classifier` (sentence F1) | 0.751 | 0.674 | −0.08 |

Five things the real documents say.

1. **The synthetic held-out number was not optimistic.** Jude scores
   0.768 on real judgments, two points above its held-out score, with
   the same recall (0.88) and the same precision problem (0.68). The
   agent-drafted split predicted the real one.
2. **The rules collapse (0.71 → 0.30) and the neural layers carry the
   recall.** A judgment's identifiers are names, repeated on every
   page: 474 of the 724 gold spans are organisations and 145 are
   persons, and the closed-form identifiers the rules own are rare
   (20 registry numbers, 2 e-mails, 4 phone numbers). `rules-only`
   finds 17 % of the organisations and 17 % of the persons; spaCy alone
   reaches 0.749 and GLiNER lifts the pipeline's recall from 0.81 to
   0.88 at no cost in precision (0.69 → 0.68). The held-out picture (rules
   three F1 points behind the full pipeline, at precision 0.95) and the
   real-document picture are both true: synthetic files are dense in
   e-mails, IBANs and dockets, judgments are dense in names. A system
   needs both layers; a trained model needs both kinds of text.
3. **`pplx-pii-masking` collapses with the rules (0.27).** Its taxonomy
   has no organisation label — 0 of 474 organisation spans — and its
   *private person* class excludes counsel and judges, who are
   identifiers under the policy. The failure is the taxonomy, not the
   encoder: on the persons it does label it is precise (0.87).
   `nvidia/gliner-PII` keeps an organisation label and lands at
   0.54–0.62; GLiNER with Jude's legal labels at 0.62–0.69.
4. **What Jude misses on real documents (88 spans)** — the shapes it has
   never seen: every Belgian enterprise number written with dots
   (`0447.966.784`, 20 of 20 missed — the registry bucket is at recall
   0.00 on this split), Cour de cassation *numéros de rôle*
   (`C.22.0112.F`), the Belgian authority's file numbers
   (`CONC.C/C.25-0009`, `CONC-CCS-26/0017`), US docket numbers
   (`24-3067`, `26a0394n.06`) and a Westlaw citation; a party's bare
   short form repeated after its full name (`Simon` ×9, `Rossel` ×5,
   `AlexSam`, `Blackhawk`) — the surname-propagation gap of the
   held-out split, now on company names; a party's brands and titles
   (`Remodulin`, `La Libre`, `Moustique`); US counsel blocks of
   initialled names in capitals (`Edward J. Bennett`, `KELLY L.
   STEPHENS`); a name hyphenated across a line break.
5. **What Jude over-redacts on real documents (296 spans)** — the court's
   own address line in every English judgment (`Rolls Building`,
   `Fetter Lane`, `EC4A 1NL`: public under the policy, read as a party
   address); court names and the publisher (`Royal Courts of Justice`,
   `LONDON CIRCUIT COMMERCIAL COURT`, `The National Archives`);
   capitalised defined terms (`Contract`, `MSA`, `Disputed Sums`,
   `Refinery`, `Special Managers`); header labels and record cites
   (`Domaine`, `J.A. 1952`); a cited precedent's party (`Ralli
   Brothers`, public under ruling 2); and, in the two French
   competition decisions, 47 spans each, mostly the public sphere of
   Belgian sport and press. The public-body over-redaction rate is
   25 %, as on the synthetic splits.

Every item in 4 and 5 is listed under *What Jude takes from this* and
not applied in this version.

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
* From the real documents (15 October 2026): the dotted Belgian
  enterprise-number shape (`0447.966.784`), Cour de cassation *rôle*
  numbers (`C.22.0112.F`), authority file numbers (`CONC.C/C.25-0009`),
  US docket shapes (`24-3067`) and Westlaw citations in the rules;
  propagation of a company's bare short form after its full name
  (`Simon`, `Rossel`) in the dictionary, as for surnames; the court's
  own address line and the publisher's name in the whitelist; a
  defined-term filter (capitalised common noun that the document
  itself defines); the honorific-free, initialled US counsel block as
  a pattern.

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
  see `annotation-protocol.html`); fourteen excerpts of real published
  decisions, double-annotated by agents and adjudicated, not yet
  reviewed by the lawyer, with ten further policy questions open
  (items 8–17). The numbers are indicative; the ranking and the size
  of the generalisation gap are robust.
* The generative baseline (`ollama-qwen3-4b`) is being re-run on the
  real documents; until then its row is scored on the 44 synthetic
  documents only.
* Where a mapping choice was ambiguous it was made in the external
  model's favour: dates and demographic labels are dropped rather than
  counted as false positives; adjacent name fragments are merged.
* Thresholds are the model cards' defaults; lowering NVIDIA's to 0.3
  changes little.
* Roblox's own card reports 45.5 % F1 on the Kaggle PII essay dataset;
  that number is not comparable to anything here and is not used.
