---
title: Decision models
layout: default
---

# Typed-decision models (Jev, Laya) — can they serve Jude?

Evaluated 2026-09-22. Short answer: not as they ship. Longer answer
below, with the numbers.

## What they are

A *typed-decision model* does not generate text. It reads a "state"
(a sentence, an e-mail, a JSON record) and answers **typed questions**
— a choice among named options, a score on a rubric, a yes/no — with
calibrated probabilities, in one forward pass of an encoder. Nothing
to parse, nothing to hallucinate, tens of milliseconds per question.

* **Jev** (TypeSafe AI, released 15 September 2026): the original.
  **Hosted only** — API or gateway, early-access waitlist, zero data
  retention reserved for enterprise plans. Sending a candidate span
  and its sentence to a third-party API *before* redaction is
  disclosure; Jev is therefore out for the redaction path on
  principle, whatever its quality.
* **Laya** (`convaiinnovations/laya`, Apache 2.0): open-weights
  equivalent — ModernBERT-large 421 M (English, 512 tokens) and
  mmBERT-base 322 M (100+ languages, 1,024 tokens), plus a
  `typed-decisions` fine-tune. `pip install laya`, runs locally.
* **laya-mlx** (`aac6fef/laya-mlx`): Apple Silicon port, no PyTorch.

None of the three finds *where* an identifier is. They judge.

## Where a judge could help Jude

Jude's held-out losses are almost all **decisions about candidates it
already found**: is *Auditorat* a public body or a party? is *the
Firm* a role or a name? is `C-311/18` a published citation or a live
reference? is a bare *Valdoire* a company or a person? That is 23
points of precision (`benchmark-pii-models.html`). A calibrated
redact/keep judge on every candidate would be the "model that learns
the rule" instead of a whitelist.

## The experiment

1,401 decisions from the held-out split: 763 gold spans (expected
*redact*), 320 annotator-marked public mentions, 76 whitelisted
mentions and 242 of Jude's false positives (expected *keep*); 835
English, 566 French. Each candidate in its sentence; three question
formulations; Laya via its Router (English → 421 M, French → 322 M),
on an Apple M2, 8 GB. Script: `benchmark/experiments/laya_judge.py`.

| Formulation | Balanced accuracy | AUC | Redact recall @ 0.5 | Keep accuracy @ 0.5 |
|---|---|---|---|---|
| A — two-way choice, long criteria | 0.51 | 0.45 | 0.13 | 0.89 |
| B — yes/no ("is this private?") | 0.50 | — | 0.00 | 1.00 |
| C — three-way (party / public body / role) | **0.62** | **0.64** | 0.56 | 0.66 |

The sanity checks pass — the card's own ticket-routing example
returns *billing* at 0.99; *European Commission* → public 0.89, *Acme
Solutions SA* → private 0.95 — so the pipeline is right. But
*tribunal de l'entreprise de Bruxelles* → private 0.74, *the Buyer* →
private 0.94, *KBC* → private 0.63: the model has no notion of the
legal distinction, and on the real candidates in context the best
formulation separates the classes with AUC 0.64. Read as a precision
layer at the threshold that keeps 89 % of true identifiers (0.3), it
removes 30 % of the false positives — and loses 11 % of the
identifiers a lawyer must not lose. Latency: 150 ms per question
(torch on MPS), 213 ms with laya-mlx on the M2 (the port's 13 ms
figure is an M3 Max); at fifty candidates a page that is 7–10 s per
page for the judge alone.

Laya's own card says the base checkpoint scores 0.36 zero-shot on
typed decisions and "ships over-confident": it is built to be
fine-tuned, not used cold.

## Conclusion

* **Jev: no.** Hosted; the redaction path cannot leave the machine.
* **Laya zero-shot: no** — neither as a detector (it does not locate
  spans) nor as a judge (AUC 0.64; it would trade recall for
  precision, the wrong direction for professional secrecy).
* **Laya fine-tuned on our decisions: possible but a detour.** The
  1,401 labelled decisions (and the same from the dev split) are
  exactly the training set it would need — but they are also what a
  GLiNER-class encoder needs to learn `party_organisation` vs
  `public_body` vs `role` in a single pass over the text, with no
  per-candidate cost. The same data, one model, no second stage:
  that is the plan in `training-data.html`.
* **One niche worth keeping in mind:** document-level questions —
  "does this document still contain something that identifies a
  party?" (a re-identification self-check after redaction), "how
  sensitive is this document?" (the risk badge) — one question per
  document, cheap, and a genuine fit for a calibrated yes/no. Not
  measured here.

`laya` and `laya-mlx` are installed in the development environment
for the experiment; they are not dependencies of Jude.
