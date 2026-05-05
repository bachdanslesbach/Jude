---
title: Jude — anonymize legal documents before sending them to an LLM
layout: default
---

# Jude

**Anonymize legal documents on your machine before sending them to an LLM.**

Jude is an open-source tool for lawyers who want to use frontier LLMs
(Claude, GPT, etc.) for legal analysis without breaching the
professional-secrecy obligations they owe their clients. It runs
locally, redacts identifying information from text, Word, PDF and
Excel documents, and rehydrates the LLM's response so you read real
names. The mapping table never leaves your disk.

> Jude is alpha software. It is not legal advice. It does not certify
> compliance with any bar rule. Always verify the redacted output
> before sending.

[Install →](installation.html) · [Architecture →](architecture.html) ·
[Threat model →](threat-model.html) · [FAQ →](faq.html) ·
[Source on GitHub →](https://github.com/bachdanslesbach/Jude)

---

## Why this exists

A Belgian *avocat* bound by Article 458 of the Code pénal — or a French
*avocat* under the RIN — cannot paste a client memo into ChatGPT. The
absolute interpretation of professional secrecy treats the client's
identity, the existence of a mandate, and any case detail as
confidential. Pasting that text into a third-party LLM, even one
contractually committed to "zero retention", is at best a
case-by-case judgment call and at worst a disciplinary problem.

Jude is the missing piece between *want to use an LLM* and *can't
share client data*. It sits on the user's machine. It detects the
identifying spans — names, organizations, addresses, emails, IBANs,
case references — and replaces them with stable pseudonyms (`Org1`,
`Person2`, `Loc3`) before any text is sent over the network. The LLM
sees only pseudonyms; the user reads only real names.

## How it works

```
                    ┌────────────────┐
   Your document →  │ Local NER      │
                    │ (spaCy + regex │
                    │  + dictionary  │
                    │  + optional    │
                    │  privacy-      │
                    │  filter model) │
                    └───────┬────────┘
                            │ entities + spans
                            ▼
                    ┌────────────────┐       ┌────────────────┐
                    │ Pseudonymize   │ ────► │ LLM            │
                    │ (per-matter    │       │ (Anthropic OR  │
                    │  SQLite store) │       │  local Ollama) │
                    └───────┬────────┘       └───────┬────────┘
                            │                        │
                            │ ◄──────────────────────┘
                            ▼
                    ┌────────────────┐
                    │ Rehydrate the  │ →  Plain-language answer
                    │ response       │    you actually read
                    └────────────────┘
```

The pseudonym mapping is per-matter and lives in a single SQLite file
on your disk. The LLM never sees a real name. When the LLM responds
using `Org1`, Jude maps `Org1` back to `Acme Solutions SA` before
showing you the answer.

## Two modes per matter

| | **Strict** | **Smart** |
|---|---|---|
| Pseudonyms | yes | yes |
| Public-knowledge tags | none | yes — first mention of `Org1` gets *(DMA-designated gatekeeper, marketplace + cloud)* |
| LLM endpoint requirement | any | zero-retention attestation OR a local backend (Ollama) |
| Use case | maximum confidentiality, less analytical depth | better LLM reasoning when the parties are well-known |

## What Jude reads

- Plain text (`.txt`)
- Microsoft Word (`.docx`) — body, headers, footers, table cells. Comments and tracked changes are flagged but not redacted.
- PDF — native-text directly; image-only / scanned PDFs via the `[ocr]` extra (`ocrmypdf` + Tesseract).
- Excel (`.xlsx`) — every cell on every sheet, with redacted output preserving structure.

## Install

See the [installation guide](installation.html).

```bash
git clone https://github.com/bachdanslesbach/Jude.git
cd Jude
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg
python -m spacy download fr_core_news_md
export ANTHROPIC_API_KEY=...   # or use launchctl on macOS
jude ui
```

## Honest limitations

- **NER misses things.** Jude defaults to fail-closed (when uncertain,
  redact) but cannot guarantee 100% recall. Read the redacted output
  before sending.
- **Re-identification from context is real.** "The largest gaming
  acquisition in history at $68.7bn" identifies Microsoft–Activision
  no matter what pseudonym you put in front. Jude includes a heuristic
  re-identification risk score (LOW / MEDIUM / HIGH) so you notice
  these cases, but the heuristic is not a privacy proof.
- **"Zero-retention" is contractual, not technical.** A subpoena, a
  sub-processor incident, or a misconfigured logging pipeline can
  still leak. For matters where this matters more than analytical
  quality, switch the matter's LLM backend to local Ollama.
- **Open-source ≠ certified.** Jude is not approved by any bar
  association. Treat it as a tool that helps you discharge your
  professional obligations, not as a substitute for them.

## License

[MIT](https://github.com/bachdanslesbach/Jude/blob/main/LICENSE).
