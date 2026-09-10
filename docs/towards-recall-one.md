---
title: Towards zero misses
layout: default
---

# Towards zero misses

A lawyer bound by professional secrecy cannot afford a single leaked
identifier. That sentence sets the target, and it is not F1.

## The right target

Two kinds of error, wildly different costs:

* **A miss** (false negative) — a party's name reaches a third-party
  model. A breach of Article 458 of the Belgian Criminal Code, of the
  bar's rules, of the client's trust. One is too many.
* **An over-redaction** (false positive) — *European Commission*
  becomes `Org7`, and the model's answer is a little worse. Annoying;
  reversible; visible.

So the objective is **recall on identifiers → 1**, with precision
merely good enough to keep the output readable and the review short.
And since no model reaches 1, the second half of the objective is a
**review step that is cheap, exhaustive and fail-closed** — the
guarantee is the process, the model is what makes the process cheap.
That is how conflict checks and KYC work; anonymisation is no
different.

## Where the misses are today

Jude v0.7.9 on the 20-document corpus: recall 0.970, twelve misses
out of 401 identifiers. Every one belongs to a class, and every class
has a remedy:

| Miss | Class | Remedy |
|---|---|---|
| `Helios` ×6 | deal codename, deliberately dropped by a stop-list entry | policy decision: codenames are confidential → redact; `Project X` rule |
| `BCEE` | bank known by acronym | public-knowledge list of banks and their acronyms (redactable) |
| `M/V Aurelia` | vessel | deterministic rule on `M/V`, `MV`, `MT`, `SS` prefixes |
| `Henkel-Vorwerk` | hyphenated two-party label | split on the hyphen when both halves are known entities |
| `Luxembourg` | city annotated as place of business, whitelist says jurisdiction | annotation policy, then context rule (after *in* / *at* / *registered in*) |
| `10 Old Bailey` | street address | address pattern: number + street word (EN/FR/NL) |
| `pinegrove-coffee.example.com` | bare domain | URL regex without scheme |

None of these is a modelling problem. They are long-tail rules, list
entries and one policy call.

## Levers, in order of expected yield

1. **Deterministic long-tail rules.** Legal-form suffix (any capitalised
   phrase followed by `SA`, `NV`, `SARL`, `BV`, `GmbH`, `Ltd`, `plc`,
   `Inc.` … is an organisation); `Project <Name>` and bare codenames
   in a defined-terms clause; honorific + capitalised token (`Mr.
   Tan`, `Maître Peeters`, `Dr. Krishnamurthy`); vessel prefixes;
   `the <Name> Group`; street addresses; bare domains; acronyms
   introduced in parentheses after a name (`Lumen Optical Systems
   Corp. ("LOS")`). Cheap, transparent, high recall; precision is
   protected by the whitelist.
2. **Propagation.** The first mention is the risk; the second never is.
   Every detected entity already spreads to its surface forms within
   a matter; extend to surname-only, initials, possessives (`Martin's`),
   acronyms, and the pseudonym dictionary across all documents of the
   matter.
3. **The unverified-token report.** After redaction, list every
   capitalised token or phrase that was *not* redacted and is *not*
   whitelisted, in context, for a single confirmation pass. On a
   20-page brief that is a few dozen items, seconds each. This is the
   step that turns 0.97 into a process guarantee: the model finds what
   it can, the report shows the lawyer exactly what it did not decide.
4. **Adversarial re-identification check, locally.** Feed the redacted
   text to a local model (Ollama, nothing leaves the machine) with one
   question: *who are the parties, and what in this text would let you
   identify them?* This catches what no entity detector sees —
   the only listed brewer in a small country, a deal value that was in
   the press, a hearing date. Its answer feeds the existing
   re-identification risk score.
5. **A legal fine-tune of the NER model.** The benchmark shows PII
   fine-tuning transfers; a GLiNER trained on synthetic *legal* data
   with `party_organisation` / `public_body` / `case_reference` labels
   would lift ORG recall and precision together. Detectors stay in
   union: recall first.
6. **A gold corpus a lawyer has read.** Recall by type is the KPI, and
   it is only as good as the gold. The Word review protocol, then real
   public documents (Commission decisions, US opinions, UK judgments).
   A release gate: no version ships if recall on any type drops.
7. **Paranoid mode.** Lower GLiNER's threshold, keep every detector's
   output, widen the address and codename rules — and measure what it
   costs in precision. Default for matters flagged sensitive.
8. **Precision, for readability.** Grey highlights from reviews grow
   the whitelist; the role stop-list grows from false positives. The
   over-redaction column stays in every report so precision cannot
   quietly rot.

## What "one" will look like

Honestly: the detectors at 0.98–0.99 recall on identifiers; the
residual caught by the unverified-token report and the local
re-identification check; a lawyer's sign-off on a list, not on a
document. The number in the benchmark measures the model; the
guarantee lives in the process, and the process is what Jude has to
make cheap.
