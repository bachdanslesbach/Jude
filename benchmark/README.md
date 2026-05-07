# Jude redaction benchmark

A reproducible measure of Jude's redaction quality, designed so we can
iterate on the detection layers and see whether each change moves the
F1 needle.

## What it measures

For every document in `corpus/`, we compare predicted spans (from a
runner) against gold spans (annotated by hand). Matching is **lenient
overlap, type-strict**:

- A predicted span is a TP iff it overlaps a gold span by ≥1 character
  AND has the same `type`.
- Each gold span matches at most one prediction (greedy, by largest
  overlap).
- Aggregate metrics: Precision = TP / (TP + FP); Recall = TP / (TP +
  FN); F1 = 2PR / (P + R).
- Per-type breakdown shows which entity classes are weakest.

The lenient policy forgives one-off boundary differences (predicting
"Acme Solutions" when gold is "Acme Solutions SA" still counts as TP)
but penalises wrong types or wrong positions.

## Corpus

| Document | Lang | Spans | Topic |
|---|---|---|---|
| `doc_001_term_sheet_en.json` | en | 16 | Fictional M&A term sheet |
| `doc_002_credit_facility_en.json` | en | 13 | Counsel memo on a syndicated facility |
| `doc_003_solaris_jv_fr.json` | fr | 22 | Note interne on a JV in North Africa |
| `doc_004_brussels_letter_nl.json` | nl | 10 | Brussels-bar advice letter |
| `doc_005_supply_agreement_en.json` | en | 13 | Iron-ore supply agreement |

Each document carries a `notes` field documenting the annotation
policy: what the human believes should be redacted (parties, lawyer
names, contact info, IBANs, addresses) and what should NOT be
(regulators, statutes, treaty articles, role labels). Re-read the
notes when adjusting gold annotations — the policy choice matters
more than the F1 number.

## Runners

| Runner | Composition |
|---|---|
| `jude-full` | Two-pass redact: regex + spaCy + dictionary, with public-knowledge filter applied. The system Jude actually ships. |
| `jude-no-public-filter` | Same minus the whitelist that drops public institutions / treaties. |
| `spacy-only` | Just `SpacyDetector` with the shape filter. |
| `regex-only` | Just the regex rules (emails, IBANs, phones, case refs, ECLI). |

Add a runner: drop a class in `runners/` with `name: str` and
`predict(text) -> list[PredSpan]`, then register it in `run.py::_all_runners`.

## Running the benchmark

```bash
python -m benchmark.run                                 # summary table
python -m benchmark.run --report docs/benchmark.md      # full report
```

## Latest results

See [`docs/benchmark.md`](../docs/benchmark.md) for the most recent
auto-generated report.

## How to add a document

1. Edit `_build_corpus.py` and add a new `doc_*` function returning a
   `(text, [(surface, type), ...])` tuple via the `_spans` helper.
2. Run `python -m benchmark._build_corpus` to regenerate the JSON.
3. Re-run `python -m benchmark.run` to see how it scores.

Document the annotation policy in the `notes` field — future you (or
a contributor) needs to know *why* a particular span was or wasn't
flagged as gold.
