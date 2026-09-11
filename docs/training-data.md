---
title: Training data
layout: default
---

# Training data for a legal-anonymisation encoder

What it would take to train the model the benchmark says is missing: a
small encoder (50–450 M parameters) that reads a legal working document
and labels what identifies a party — and, just as important, what does
not. This page is the hand-off between the domain side (annotation
policy, genres, review) and the ML side (generation at scale,
training, publication).

## What the benchmark says the model must learn

* **The parties are organisations** — with legal-form suffixes, short
  forms, acronyms defined in parentheses, codenames. Generic PII models
  have no label for them (48 % of gold spans).
* **The public sphere must stay** — regulators, courts, statutes,
  jurisdictions, published judgments, officials in a public capacity.
  Not a post-hoc list: a label the model learns, `public_body`,
  opposite to `party_organisation`.
* **Case references and registry numbers are identifiers** — internal
  dockets, live case numbers, KBO/BCE, Companies House, VAT.
* **The long tail** — honorific-only and surname-only repeats, bare
  domains, vessels, banks by acronym, all-caps headers, addresses
  where the city is also a court's seat.
* **Two languages, one register** — English and French legal drafting,
  Belgian and EU formats first.

## Label schema (v1)

Finer than Jude's runtime types, so the policy can be flipped without
re-annotating; Jude maps them down at inference.

| Label | Redact? | Examples |
|---|---|---|
| `party_organisation` | yes | Kestrel Foods NV, KFN, the Target's subsidiaries, law firms, banks by acronym |
| `public_body` | no | European Commission, Autorité belge de la concurrence, tribunal de l'entreprise, SPF Finances |
| `codename` | policy | Project Ganymede, Projet Héron, bare "Ganymede" |
| `private_person` | yes | parties, employees, witnesses, counsel — full name, surname only, honorific + surname |
| `public_official` | policy | a Commission case handler, an *auditeur*, a judge, named in that capacity |
| `party_address` | yes | Avenue Louise 250, 1050 Brussels (a party's seat) |
| `public_address` | no | Place Madou 1, 1210 Brussels (the Commission's) |
| `case_reference_live` | yes | A/26/02371, M.12384 before notification, HV-2026-0655 |
| `case_reference_published` | no | C-746/21 P, ECLI:EU:C:2020:559 |
| `registry_number` | yes | 0712.445.303, HRB 71244, IT04182730269 |
| `email`, `phone`, `iban`, `url`, `secret` | yes | as today |
| `statute` | no | Article 102 TFEU, Regulation (EC) No 139/2004, Wetboek van economisch recht |
| `role` | no (negative) | the Buyer, our client, Counsel for the Claimant, the undersigned |

The "policy" rows are the open rulings in
`benchmark/synth/POLICY_QUESTIONS.md`; the model learns the
distinction, the deployment decides the action.

## How the data is made

The same pipeline that produced the held-out batch, run at scale:

1. **A spec per document**, written by a drafting agent from a brief:
   genre × language × jurisdiction × a random subset of the long-tail
   traps. Format: `benchmark/synth.py` (text + typed surfaces + public
   mentions + declared traps).
2. **The programmatic bar** (`validate`): length, identifier density and
   variety, public mentions present, traps present, language, no
   whitelist conflict, **no name / number / address shared with any
   other document** (the fingerprint lesson from batch one).
3. **A judge pass**: realism, consistency, language quality, sensitivity
   (no real private individual, no real matter); documents under 4/5
   are regenerated, not fixed.
4. **Every occurrence annotated** by the builder, nested surfaces
   longest-first; label mapping to the v1 schema above.
5. **Deterministic classes labelled by the rules** — e-mail, phone,
   IBAN, VAT, ECLI — so the model's training signal on those is
   perfectly consistent (weak supervision by the very rules the model
   is meant to internalise).
6. **Near-duplicate and fingerprint sweeps** across the whole set
   (surname counts, 4-digit runs, addresses, amounts, dates), then
   genre / language / trap balance.

Scale: a few thousand documents (≈ 100 k spans) is the usual order for
fine-tuning a GLiNER-class encoder; thirty parallel drafting agents
produce a hundred documents an hour. Cost is dominated by generation,
not training.

## What never goes in

* Anything from a real matter — Art. 458 Code pénal. Synthetic or
  public documents only; the review protocol says so on every page.
* The benchmark corpus. `benchmark/corpus/` is for measuring;
  training data comes from different briefs, different names,
  different reference schemes. The held-out split stays held out.
* Real private individuals as parties, witnesses or employees. Real
  companies only as banks by acronym or well-known groups in an
  incidental role; real public bodies freely.

## Genres to cover (EN and FR unless noted)

Term sheet · credit facility · supply agreement · SPA / SHA excerpts ·
NDA · escrow agreement · board minutes · shareholders' resolutions ·
Form CO / notification excerpts · RFI responses to the Commission and
the ABC · leniency and settlement submissions · dawn-raid memos ·
state-aid complaints · witness statements and interview notes · expert
reports · pleadings (conclusions, requests for arbitration, cease and
desist, mise en demeure) · settlement agreements · employment
terminations · DPIA / GDPR memos · data-breach notifications ·
due-diligence reports · data-room indexes · engagement letters · client
e-mail threads · litigation budgets · insolvency updates · tax memos.

## Licensing and publication

Data: CC BY 4.0. Model: Apache 2.0 (GLiNER's own). Nothing in either
depends on a particular LLM provider. Published on the Hub with the
benchmark harness as the evaluation script and the held-out split as
the leaderboard test set.

## Division of labour

| Domain side | ML side |
|---|---|
| Annotation policy and rulings | Generation pipeline at scale (agents, seeds, balance) |
| Genre list, traps, briefs | Judge and fingerprint sweeps at scale |
| Review of the benchmark corpus in Word | Fine-tuning small / medium / large, ablations |
| Held-out set, protocol, report | Hub dataset + model cards, leaderboard |

## On rules versus a model that "understands the spirit"

Half right. A good model should, in time, learn what the rules encode
— and it generalises where a regex cannot (*Opération Sirocco* is a
codename to a model that learned *Project Ganymede*; no pattern
covers it). That is why the training data is built so the model learns
the rules' *meaning*, and why the deterministic classes are labelled
by the rules themselves.

But three things stay outside the weights, deliberately:

* **Closed-form identifiers** (IBAN, e-mail, ECLI, VAT). A pattern is
  right every time; a model is right with some probability. When a
  miss is a breach of professional secrecy, the pattern is the floor,
  not a crutch.
* **Policy.** Whether codenames are redacted, whether a named
  Commission official is, which institutions must stay — these are the
  firm's decisions and can change per matter. Policy belongs in a
  configuration a lawyer can read and edit, not in weights nobody can
  audit.
* **Explanation.** "Redacted: matches the IBAN pattern" is an answer a
  bar's disciplinary body accepts; "the model scored it 0.71" is not.

So the target architecture is the model as the primary detector,
rules as floor and policy layer, and the benchmark measuring the gap —
*how often does a rule catch what the model missed* — which should
trend to zero as the model improves. When it does, the rule is a
free check, not a cost.
