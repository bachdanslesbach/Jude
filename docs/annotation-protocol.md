---
title: Annotating in Word
layout: default
---

# Annotating a document in Word

The benchmark corpus grows one reviewed document at a time, and the
annotation tool is Word's highlighter: one colour per entity type,
nothing to install. Jude pre-highlights its own detections so the work
is correcting, not annotating from scratch.

## Legend

| Word highlight | Type | Examples |
|---|---|---|
| **Yellow** | PERSON | Sophie Martin · Mr. Tan · Dr. Krishnamurthy |
| **Bright green** | ORG | Acme Solutions SA · UBS · Project Helios (a deal codename) |
| **Turquoise** | LOC | Brussels · 22 rue de Rivoli · Cayman (as a place of incorporation) |
| **Pink** | CASE_REF | Case T-203/24 · 1:26-cv-00489-RGA · M-2026-PIO-001 |
| **Blue** | EMAIL | |
| **Red** | PHONE | |
| **Violet** | IBAN | IBANs, VAT / SIREN / national-register numbers, account numbers |
| **Teal** | URL | |
| **Dark red** | SECRET | API keys, tokens, passwords pasted by mistake |
| **Gray 25 %** | PUBLIC | European Commission · DMA · Commercial Court of London — what must *stay* |

Any other colour is reported as a warning at ingest and ignored.

## Rules

* **Highlight the identifier, not its label.** `Sophie Martin`, not
  `Maître Sophie Martin`; `Acme Solutions SA` including its legal-form
  suffix. Include an honorific only when the name is a bare surname
  (`Mr. Tan`).
* **Every occurrence**, not just the first. The gold must catch repeats
  as strictly as the pipeline is expected to.
* **Not identifiers**: dates, amounts, job titles, roles (`the Buyer`,
  `the Claimant`), generic section labels.
* **Grey out what must stay** whenever you notice it — courts,
  regulators, statutes, jurisdictions used as law (`Delaware law`) —
  and especially anything Jude highlighted wrongly. Grey feeds the
  *public-body over-redaction* metric; it is never scored as gold.
* Word splits highlights across runs and leaves spaces bare when you
  highlight word by word — both are fine, adjacent highlights of the
  same colour merge.
* **No real matter content, ever.** Rewrite: invented parties, invented
  figures, invented dates. The *genre* is what the corpus needs.

## Workflow

```bash
python -m benchmark.docx_gold prefill matter.docx matter.review.docx
```

Jude's detections become highlights; whitelisted public bodies turn
grey. Open `matter.review.docx` in Word and fix: add missing
highlights, clear wrong ones, change colours where the type is wrong.

```bash
python -m benchmark.docx_gold ingest matter.review.docx --id doc_021_share_purchase_en \
    --title "Share purchase agreement" --notes "SHOULD redact: …; SHOULD NOT: …"
```

Writes `benchmark/corpus/doc_021_share_purchase_en.json` (language is
auto-detected; `--language fr` to force) and prints the span count per
type plus any legend warnings. Document ids follow
`doc_NNN_<slug>_<lang>`.

```bash
python -m benchmark.run --runners jude-full
```

scores the corpus with the new document included.

## Reviewing the existing corpus

The twenty documents shipped so far were drafted and annotated by an
agent. A lawyer's review of every one of them is what turns the
benchmark from indicative into trustworthy.

```bash
python -m benchmark.docx_gold export --all --out review/
```

writes `review/doc_001_term_sheet_en.docx` … `doc_020_….docx`, each
with the current gold as highlights and every public mention in grey.
For each document:

1. **Read it as the recipient would.** Is it a plausible term sheet /
   pleading / memo? Rewrite freely — invented parties, figures, dates;
   the text may change, offsets are recomputed at ingest.
2. **Every highlight**: right colour, right extent? Clear the wrong
   ones (Ctrl+Alt+H / "No colour"), fix the colour where the type is
   wrong.
3. **Every identifier without a highlight**: add it. Read for the
   long tail — a codename, a vessel, a bank acronym, a bare domain,
   a surname after first mention.
4. **Grey out what must stay** and is not grey yet — courts,
   regulators, statutes, jurisdictions as law. Grey is how the
   whitelist learns.
5. Save, then:

```bash
python -m benchmark.docx_gold ingest review/doc_001_term_sheet_en.docx --id doc_001_term_sheet_en --force
```

prints what the review changed (`+ LOC 'Brussels'`, `- ORG 'Zeta NV'`,
`~ PERSON→ORG 'Sophie Martin'`) and keeps the document's title and
notes. Then

```bash
python -m benchmark.run --render benchmark/results/*.json --report docs/benchmark-pii-models.md \
    --prelude benchmark/report_prelude.md --postlude benchmark/report_postlude.md
```

re-scores every system's *stored predictions* against the corrected
gold — no model needs to run again. Only a document that did not
exist at run time needs the runners re-run (`--render` says which).

Commit the JSON, not the `.docx`: the corpus is the JSON.

## Notes

* The extracted text is byte-for-byte what Jude's DOCX adapter
  produces (body paragraphs, then tables, then headers and footers;
  empty paragraphs dropped; paragraphs joined by a blank line), so gold
  offsets line up with what the pipeline sees.
* `prefill` rebuilds each paragraph as plain runs: bold and italics are
  lost and hyperlinks become text. Annotate the review copy, keep the
  original.
* Comments and tracked changes are not read. Accept changes and delete
  comments before `ingest`.
