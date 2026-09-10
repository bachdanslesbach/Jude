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

* **Corpus.** The 20 gold-annotated documents in `benchmark/corpus/`
  (400 spans): term sheets, credit facilities, witness statements,
  regulatory submissions, sanctions memos, engagement letters, patent
  and antitrust pleadings, insolvency updates — 18 in English, one
  French, one Dutch. All synthetic: professional secrecy rules out
  real files. Annotation policy: redact anything that identifies a
  party, adviser, witness or matter; leave public institutions,
  statutes, courts and jurisdictions in place. New documents are
  annotated in Word with one highlight colour per type
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
