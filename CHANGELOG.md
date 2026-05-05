# Changelog

All notable changes to Jude. The project follows TDD discipline from
v0.4.2 onwards: each feature ships as a red-green commit pair, visible
in the git log.

## [Unreleased]

- Plans: EUR-Lex enrichment for case references, auto-running risk
  score per chat turn, persistent Wikipedia cache, native PDF
  write-back.

## [0.4.7] — Documentation & landing site

Polished `README.md`, new `docs/` directory served by GitHub Pages
(installation, architecture, threat model, FAQ), `CONTRIBUTING.md`,
this `CHANGELOG.md`.

## [0.4.6] — XLSX adapter

Read every cell across every sheet for the redaction pipeline; write
a redacted copy preserving sheet names, cell positions and numeric
values verbatim. Available in the chat UI alongside .txt/.docx/.pdf
and on the CLI as `jude redact file.xlsx --matter <id>`.

8 new tests.

## [0.4.5] — Coverage backfill

Four UI smoke tests via Streamlit's `AppTest` runner (covering empty
state, matter creation, backend switching, risk panel rendering).
One real-LLM end-to-end regression test against the Anthropic API
(gated on `ANTHROPIC_API_KEY` so it only runs when explicitly
requested).

## [0.4.4] — Ollama backend

Per-matter LLM picker in the sidebar. Choose Anthropic (cloud,
contractual zero-retention) or Ollama (local, structural zero-
retention). When the backend is local, smart mode works without a
zero-retention attestation since prompts never leave the machine.
Adds `OllamaClient`, `LLMClient.inherently_zero_retention`, and an
idempotent `ALTER TABLE matters ADD COLUMN llm_model` migration.

15 new tests.

## [0.4.3] — Re-identification risk score

For each entity, flag whether the surrounding context (specific
currency figures, dates, EU case refs in the same paragraph as the
pseudonym; public-knowledge tags; canonical name leaking inside its
own context tag) is structurally identifying. Surfaced as a LOW /
MEDIUM / HIGH badge in the Entities page with a "why?" expander
listing the contributing signals.

13 new tests.

## [0.4.2] — Wikipedia fallback for smart-mode context

When the bundled dataset doesn't cover an entity, fall back to
Wikipedia for a one-line public-knowledge tag. Opt-in per matter
(entity names get sent to Wikipedia's REST API). Strict TDD from
this version on — failing tests committed first, implementation in
a follow-up commit.

13 new tests.

## [0.4.1] — Optional fifth detector: openai/privacy-filter

Adds coverage for postal addresses, accidentally-pasted secrets
(API keys, tokens) and non-IBAN account numbers. 1.5B params with
50M active (MoE), Apache 2.0. Enable via `pip install -e ".[privacy-filter]"`
and toggle in the sidebar.

6 new tests; 1 integration test gated on the model download.

## [0.4] — Chat-first UI with multi-turn redaction

Replaced the four-tab Streamlit layout with a single chat surface.
Each turn is incrementally redacted; the same entity always reuses
its pseudonym across turns. Conversations are persisted per matter.
The Entities page lives at its own URL.

Bug fixes that shipped alongside: SQLite cross-thread crash, matter-
creation crash from setting a widget's session_state after render,
Streamlit's first-run email prompt now suppressed.

10 new tests.

## [0.3.1] — Scanned PDF support via ocrmypdf

Image-only PDFs can be OCR'd locally via `--ocr` (CLI) or a checkbox
(UI). Requires the `tesseract` system binary. Output is plain text;
PDF write-back is deferred.

5 new tests; 1 gated on tesseract being installed.

## [0.3] — NER hygiene

Per-paragraph language routing (no more French-model-on-English
hallucinations), span shape filter that rejects all-stopword spans,
dates, single lowercase words, and runaway 6+-token spans. The
test memo went from 32 noisy entities to 16 mostly-clean ones.

End-to-end test on a sanitized 20-page legal memo verified the loop
works: redact → Claude → rehydrate.

7 new tests.

Also: pseudonym format shortened from `Org_001` to `Org1`, bundled
known-entities dataset expanded from 13 to 147 entries (27 EU NCAs,
27 EU DPAs, 23 EU bodies, 17 non-EU competition authorities, 13
international bodies, 24 top national courts).

## [0.2] — PDF, entity merge, bundled context

Native-text PDF support via PyMuPDF. Entity merge in the UI for the
common case where the same real entity is detected under two surface
forms (`Amazon` and `Amazon.com Inc.`). Bundled public-knowledge
dataset for auto-filling smart-mode context (DMA gatekeepers, EU
institutions, NCAs).

12 new tests.

## [0.1] — Initial release

Plain text + DOCX, strict / smart modes, Streamlit UI, Anthropic
backend, French + English NER. SQLite per-matter store. CLI for
`init`, `matter create/list`, `redact`, `entities`, `rehydrate`,
`enrich`, `ui`. MIT license.

24 tests.
