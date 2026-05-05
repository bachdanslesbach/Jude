---
title: Threat model
layout: default
---

# Threat model

This page is the honest version of *what Jude does and does not
protect against*. It exists so you can read it before deciding
whether Jude is appropriate for a given client matter.

## Who Jude is for

Lawyers bound by professional-secrecy rules — Belgian Article 458
*Code pénal*, French RIN *secret professionnel*, Swiss Article 13
LLCA, similar standards in other jurisdictions — who want to use
frontier LLMs (Claude, GPT, Gemini) for legal analysis without
breaching those rules.

The Belgian and French standards in particular treat secret
professionnel as **absolute** and **of public order**. Pasting client
text into ChatGPT.com without anonymization is not a defensible
position. Jude's job is to make pasting into ChatGPT (or equivalent)
a defensible position — by ensuring the only thing that travels is
text the user has reviewed and that contains no client identifier.

## What Jude protects against

### Routine LLM-provider data retention and training on prompts

The mapping table never leaves your machine. Even if the LLM provider
trained their next model on your prompt verbatim, the prompt would
contain `Org1`, `Person2`, `Loc3` — strings with no extrinsic
meaning.

### Sub-processor / human-reviewer exposure at the LLM provider

Your LLM provider may have employees or sub-processors who can read
prompts (for trust-and-safety review, model evaluation, etc.). What
they would see is pseudonymized.

The caveat: smart-mode public-knowledge tags can identify well-known
entities by reading the tag itself. If your matter is in smart mode
and you opt into a context tag *"DMA-designated gatekeeper for
marketplace and cloud"*, anyone reading your prompt can recognize
Amazon. Smart mode is a deliberate privacy/quality trade-off and is
opt-in per matter for exactly this reason.

### Hypothetical breach of the LLM provider

Same logic as above. With a proper strict-mode redaction, a breach
of the LLM provider would expose pseudonymized text and the
jurisdiction-defining context (you are a competition lawyer asking
about Article 102 TFEU). It would not expose your client's identity.

### Accidentally pasting a secret

If you paste the test PDF, the chat input also redacts via regex
(emails, IBANs, phones, EU case refs) and via spaCy NER. Enabling
the `[privacy-filter]` extra adds the `secret` category which catches
API keys, JWTs, AWS credentials and similar. We added this after
exactly this happened during early testing.

## What Jude does NOT protect against

### Re-identification from context

A pseudonymized prompt that says *"Org1 announced the closing of the
$68,700,000,000 acquisition on October 13, 2023"* identifies
Microsoft–Activision regardless of the pseudonym. Jude includes a
heuristic [re-identification risk score](architecture.html) that
flags entities co-located with specific currency figures, dates and
case references. **The score is a checklist, not a proof.** Subtler
unique combinations — phrasing, sectors, narrow market positions —
can still re-identify even when the score reads LOW.

You are the last filter. Read the redacted text before clicking send.

### Compromise of your local machine

If your laptop is exfiltrated or compromised, the `~/.jude/jude.db`
file contains the real names and their pseudonyms. Standard endpoint
hygiene applies: full-disk encryption, strong screen lock, automatic
session lock, regular backups.

### Subpoena of the LLM provider

A "zero-retention" contract is a contractual promise about routine
storage. It is not a legal shield against a court order. If you are
working a matter where the existence of the matter itself must remain
unknown to a third party, even a contractually-zero-retention API
may not be enough. Switch the matter's backend to local Ollama, which
is structurally zero-retention (the prompt never leaves localhost).

### Subpoena of you

Jude does not enable any privilege you wouldn't otherwise have. Your
local logs, the SQLite file, and the conversation history are all
your records.

### NER false negatives

If spaCy fails to detect "Société Civile Immobilière du Bois Joli" as
an organization, that string is sent in the clear. Jude defaults to
fail-closed (when uncertain, redact) but cannot guarantee 100%
recall. Optional detectors (`openai/privacy-filter`, GLiNER) reduce
the false-negative rate in exchange for compute and disk cost.

The merge UI in the Entities page lets you correct mistakes after
the fact, and the dictionary detector ensures any term you have
flagged once is caught from then on for the same matter.

## What "smart mode" really means

Smart mode trades absolute confidentiality for analytical quality.
The bundled public-knowledge dataset includes facts about each entity
that are already in the public domain — you can find them on the
entity's Wikipedia page or its own corporate website.

When smart mode is on for a matter:

- The LLM learns that `Org1` is *some* DMA-designated gatekeeper
  with a marketplace business — i.e. probably Amazon.
- A reader of the prompt who knows the field can recover the
  identity in seconds.
- The LLM, in exchange, can ground its reasoning in the right
  regulatory framework and produce more useful output.

Use smart mode when the underlying party identity is itself public
(e.g. a public M&A target, a publicly-known regulator, a listed
company). Don't use smart mode for private clients whose identity
is itself confidential.

## Open questions

We don't claim to have answered:

- **GDPR effectiveness of pseudonymization.** Whether Jude's
  pseudonymization meets the GDPR's high bar for "anonymization"
  (CJEU *SRB v EDPS*, 2024) is a fact-specific legal question. In
  practice the data exiting your machine is at minimum
  *pseudonymized* under Article 4(5) GDPR.
- **Bar association approval.** Jude has not been formally reviewed
  or endorsed by any bar.
- **Adequacy under Article 458 Code pénal (Belgian).** The absolute
  reading of secret professionnel may treat any LLM use, even
  pseudonymized, as a breach. This is an unsettled question; using
  Jude with the local-Ollama backend is the most conservative path
  available today.
