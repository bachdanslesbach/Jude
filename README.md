# Jude

**Local-first anonymization for legal documents before LLM use.**

Jude redacts identifying information from legal documents on your machine before any data is sent to a Large Language Model. It is designed for lawyers bound by professional secrecy obligations (e.g. Belgian Art. 458 *Code pénal*, French RIN *secret professionnel*) who want to use frontier LLMs for legal analysis without breaching client confidentiality.

> **Status:** alpha (v0.1). Use with care, and verify every redacted output yourself before sending it to an LLM. Jude is a tool — it does not relieve you of your professional obligations.

---

## What it does

1. **Detects** named entities in your document — persons, organizations, locations, emails, phone numbers, IBANs, court / case references, etc. — using local NER (spaCy, optionally GLiNER) plus regex and a per-matter dictionary that learns over time.
2. **Redacts** them by replacing each with a stable pseudonym (`Org1`, `Person1`, …). The mapping is stored locally in SQLite, scoped per matter, never leaves your machine.
3. **Optionally adds public-knowledge context** to selected entities (e.g. *"Org1 — DMA-designated gatekeeper, marketplace + cloud business"*) so the LLM can reason competently without learning the actual identity. Only available in **smart mode**.
4. **Sends** the redacted text to your chosen LLM (Anthropic by default; pluggable).
5. **Rehydrates** the LLM response by mapping pseudonyms back to real names, so what you read is in plain language.

The mapping table lives only on your disk. The LLM only ever sees pseudonyms.

## Modes

Jude exposes two modes per matter, surfaced in the UI:

| | **Strict** | **Smart** |
|---|---|---|
| Pseudonyms | yes | yes |
| Context tags | categorical only ("a tech firm") | public-knowledge tags allowed ("a VLOP, marketplace business") |
| LLM endpoint requirement | any | must be declared zero-retention by the user |
| Use case | maximum confidentiality, lower analytical depth | better LLM reasoning, requires a contractually-trusted endpoint |

The mode is recorded per matter and visible at every step.

## Threat model

Jude protects against:

- **Routine LLM-provider data retention and training on prompts.** Mapping never leaves your machine.
- **Sub-processor / human-reviewer exposure** at the LLM provider, *to the extent that pseudonyms remain non-identifying.*
- **Hypothetical breach** of the LLM provider, with the same caveat.

Jude does **not** protect against:

- **Re-identification from context.** A pseudonym can be re-identified if the surrounding text uniquely fingerprints the entity (e.g. "the largest gaming acquisition in history" identifies Microsoft–Activision regardless of the name). Smart mode makes this risk explicit and is opt-in. *You* are the last filter.
- **Compromise of your local machine.**
- **Subpoena of the LLM provider.** A zero-retention contract is a contractual promise, not a legal shield.
- **NER false negatives.** If the model fails to detect an entity, it will be sent in clear. Jude defaults to fail-closed (redact on uncertainty) but cannot guarantee 100% recall.

**You must read the redacted text before sending it.** The UI presents the redacted version side-by-side with the original for exactly this reason.

## Numerical and date data

By default Jude **does not redact numbers, dates, or financial figures.** The reasoning: once the party they refer to is pseudonymized, the figure is no longer linked to a specific client. There are edge cases (e.g. a unique deal value that singles out a transaction) — for those, the user can manually mark a span for redaction in the UI.

## Architecture

```
src/jude/
├── types.py                # Pydantic models: Detection, Entity, Matter, Mode
├── store.py                # SQLite per-matter store (entities, surface forms, mode)
├── detect/                 # detection pipeline
│   ├── regex_rules.py      # emails, phones, IBANs, case numbers
│   ├── spacy_detector.py   # PERSON / ORG / LOC / DATE / MONEY in EN+FR
│   └── dictionary_detector.py  # learned per-matter terms
├── redact.py               # apply detections → pseudonymized text + mapping
├── rehydrate.py            # reverse mapping for LLM output
├── context.py              # smart-mode public-knowledge tag store
├── adapters/               # file format readers/writers
│   ├── text.py
│   └── docx.py
├── llm/                    # pluggable LLM clients
│   ├── base.py
│   └── anthropic_client.py
├── cli.py                  # `jude` command
└── ui/app.py               # Streamlit UI
```

## Quick start

```bash
git clone https://github.com/etienne/jude.git
cd jude
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg     # English (preferred)
python -m spacy download fr_core_news_md    # French
jude ui                    # launches the Streamlit UI
```

For the LLM call you need an `ANTHROPIC_API_KEY` in your environment (Anthropic's API is zero-retention by default for non-flagged content).

## CLI

```bash
jude redact path/to/file.docx --matter "matter-2026-001"
jude redact path/to/file.pdf  --matter "matter-2026-001"   # outputs .txt
jude entities --matter "matter-2026-001"
jude enrich   --matter "matter-2026-001"                   # auto-fill public context
jude rehydrate path/to/llm-output.txt --matter "matter-2026-001"
```

## Tests

```bash
pytest
```

## Roadmap

- v0.1: plain text + DOCX, strict / smart modes, Streamlit UI, Anthropic backend, French + English NER.
- v0.2: native-text PDF, entity merge in the UI, bundled public-knowledge dataset for auto-filling smart-mode context (DMA gatekeepers, EU institutions, NCAs).
- v0.3: per-paragraph language routing, span shape filter, `en_core_web_lg` preferred, expanded known-entities dataset to 147 entries.
- **v0.3.1 (now): scanned PDF support via `ocrmypdf` (`--ocr` CLI flag, checkbox in UI).**
- v0.4: chat-first UI with multi-turn redaction.
- v0.5: Wikipedia / EUR-Lex enrichment, OpenAI / Azure / Ollama backends.
- v0.6: re-identification risk score per entity.
- v0.7: Tauri + React desktop app replacing Streamlit.

## OCR for scanned PDFs

If you redact a PDF that's image-only (scanned), Jude can run `ocrmypdf`
locally to add a searchable text layer first, then extract from that.

Requires the `tesseract` system binary:

```bash
brew install tesseract tesseract-lang   # macOS
# or:
apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra   # Debian
```

Plus the Python wrapper:

```bash
pip install -e ".[ocr]"
```

Then:

```bash
jude redact some_scan.pdf --matter <id> --ocr
```

The OCR runs entirely on your machine; nothing is sent over the network.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

Jude is provided "as is" with no warranty. It is not legal advice, it does not certify GDPR or bar-rule compliance, and it does not replace your professional judgment. Always verify the redacted output before sending it to an LLM.
