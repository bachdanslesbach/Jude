---
title: FAQ
layout: default
---

# FAQ

### Is Jude legal advice?

No. Jude is a software tool. Whether it is appropriate for any
specific matter is a question for the practitioner, not the
software.

### Has Jude been approved by my bar?

No. As of writing no bar association has formally reviewed Jude.
The threat model is laid out [here](threat-model.html); read it
and form your own view.

### Does Jude support [language X]?

English and French in v0.4. The detection pipeline is language-aware
(per-paragraph language detection routes to the right spaCy model)
so adding more languages is mostly a question of installing the
relevant spaCy model and wiring it in. Open an issue if you need
Dutch, German, Italian, Spanish or others.

### Why doesn't Jude support reading PDFs into PDFs?

It does for input — see the PDF adapter — but the redacted output is
plain text, not a redacted PDF. Writing a redacted PDF that
preserves layout requires either span-level coordinate mapping
(complex) or a "burn-in" strategy that flattens the document. We
plan to add the latter in a future release.

### Does Jude work without an internet connection?

Almost — yes if you use the local Ollama backend; the only network
calls in the default pipeline are to the LLM endpoint. With Ollama
selected as the backend, Jude is fully offline. With Anthropic and
smart-mode Wikipedia enrichment enabled, Jude makes outbound calls
to api.anthropic.com and en.wikipedia.org.

### How big should my client's name be before Jude detects it?

Jude detects organizations down to single-token surface forms (e.g.
"Acme") if spaCy recognizes them as ORG. For unusual names the
detector may miss; the merge UI in the Entities page lets you
flag them, and from that point on the dictionary detector catches
them for the rest of the matter.

### Does Jude store my LLM responses?

Yes — the chat history (in both redacted and rehydrated form) is
persisted to the per-matter SQLite store so you can revisit
conversations later. If you want this gone, delete the matter from
the database.

### How do I get my data out of Jude?

The `~/.jude/jude.db` file is a standard SQLite database. Open it
with the `sqlite3` command-line tool, DB Browser for SQLite, or any
ORM. The schema is documented in the [architecture](architecture.html)
page.

### What's the difference between strict and smart mode?

Strict mode replaces every detected entity with a bare pseudonym
(`Org1`, `Person2`, etc.) and gives the LLM no further context.
Smart mode appends a one-line public-knowledge tag to the first
mention of each entity (e.g. `Org1 (DMA-designated gatekeeper,
marketplace + cloud)`). Smart mode produces better LLM reasoning
but partially identifies well-known entities to a careful reader.
Smart mode requires either an attested zero-retention LLM contract
or a local backend.

### My API key was compromised — what do I do?

Revoke it at the provider's console
([Anthropic](https://console.anthropic.com/settings/keys)),
generate a new one, and replace it via `launchctl setenv` (macOS)
or your shell's rc file. Jude itself does not store the key.

### How do I contribute?

See [CONTRIBUTING.md](https://github.com/bachdanslesbach/Jude/blob/main/CONTRIBUTING.md).
Test-driven development is the project convention; failing tests
go in their own commit before the implementation.

### What's the roadmap?

In rough priority order: EUR-Lex enrichment for case references,
auto-running the re-identification risk score per chat turn,
persistent Wikipedia cache, native PDF write-back, more language
support, a Tauri-based desktop app to replace Streamlit. Track
progress in the README's Roadmap section and on the
[issues](https://github.com/bachdanslesbach/Jude/issues) tab.

### Why "Jude"?

Patron saint of lost causes, and the four-letter brevity helps.
