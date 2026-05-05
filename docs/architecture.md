---
title: Architecture
layout: default
---

# Architecture

Jude is a small Python package designed to be auditable end-to-end.
This page describes how the pieces fit together. If you're reviewing
Jude before adopting it for client work, read this and the
[threat model](threat-model.html).

## Module layout

```
src/jude/
├── types.py                    # Pydantic models: Detection, Entity,
│                               # Matter, Mode, Conversation, Message,
│                               # RiskAssessment, RiskLevel
├── store.py                    # SQLite store (one file at ~/.jude/jude.db)
├── paths.py                    # JUDE_HOME resolution
│
├── detect/                     # Detection pipeline
│   ├── __init__.py             # DetectionPipeline + overlap resolution
│   ├── language.py             # Per-paragraph language detection
│   ├── regex_rules.py          # Email, IBAN, phone, URL, EU case ref, ECLI
│   ├── spacy_detector.py       # PERSON / ORG / LOC via lang-routed spaCy
│   ├── dictionary_detector.py  # Per-matter learned terms
│   ├── gliner_detector.py      # Optional GLiNER multilingual NER
│   └── privacy_filter_detector.py  # Optional openai/privacy-filter
│
├── redact.py                   # apply detections → pseudonymized text
├── rehydrate.py                # reverse-mapping for LLM output
├── risk.py                     # heuristic re-identification risk score
│
├── context.py                  # BundledContextProvider + ContextRouter
├── context_wikipedia.py        # Optional Wikipedia fallback
│
├── chat.py                     # Per-turn orchestrator
│
├── adapters/                   # File format readers/writers
│   ├── text.py
│   ├── docx.py                 # body + tables + headers/footers
│   ├── pdf.py                  # native-text + optional OCR
│   └── xlsx.py                 # every cell, every sheet
│
├── llm/                        # Pluggable LLM clients
│   ├── base.py                 # LLMClient ABC + JUDE_SYSTEM_PROMPT
│   ├── anthropic_client.py     # Cloud client #1 (shipped)
│   └── ollama_client.py        # Local-only; inherently_zero_retention=True
│   # Adding OpenAI/Azure/Google etc.: subclass LLMClient, implement
│   # complete_chat(), and register in llm/__init__.py.
│
├── cli.py                      # Typer-backed `jude` command
├── data/known_entities.json    # 147-entry curated public-knowledge dataset
└── ui/
    ├── app.py                  # Chat-first Streamlit UI
    └── pages/
        └── 2_Entities.py       # Per-matter dictionary management page
```

## The detection pipeline

Five detectors run over the input text. Each contributes `Detection`
spans. The pipeline then resolves overlaps according to a fixed
priority:

1. **USER** — manual span the user marked in the UI.
2. **DICTIONARY** — a surface form already learned for this matter.
3. **REGEX** — emails, IBANs, phones, URLs, EU case refs, ECLI.
4. **PRIVACY_FILTER** *(optional)* — `openai/privacy-filter` 1.5B model.
5. **GLINER** *(optional)* — multilingual transformer NER.
6. **SPACY** — `en_core_web_lg` and `fr_core_news_md`, language-routed.

Within the same priority, the longer span wins; ties are broken by
leftmost start position.

The pipeline is **fail-closed**: when in doubt, redact. Lawyers can
tolerate over-redaction; under-redaction is a bar complaint.

## Per-matter store

Everything that touches client data lives in one SQLite file at
`~/.jude/jude.db`. The schema:

```
matters       (id, name, mode, llm_endpoint, llm_model,
               zero_retention_attested, created_at)
entities      (id, matter_id, canonical, entity_type, pseudonym,
               public_context, user_marked, created_at)
surface_forms (id, entity_id, form, normalized)
conversations (id, matter_id, title, created_at)
messages      (id, conversation_id, role, redacted_text,
               display_text, created_at)
audit_log     (id, matter_id, action, detail, ts)
pseudonym_counters (matter_id, entity_type, next_n)
```

Pseudonym counters are monotonic per `(matter, entity_type)` —
deleted or merged-away pseudonyms are never recycled, so a document
redacted last week using `Org_002` won't conflict with a different
entity getting `Org_002` today.

## The chat orchestrator

`jude.chat.send_turn()` owns one full chat turn:

1. Concatenate the user's text and any attached files into a single
   payload.
2. Run the detection pipeline.
3. Apply redaction; new entities get a pseudonym, existing entities
   reuse theirs.
4. Persist the user message (redacted + display copies side-by-side).
5. Build the full conversation history in redacted form for the LLM.
6. Call the LLM (whichever `LLMClient` the matter is configured to use).
7. Rehydrate the response by reverse-mapping pseudonyms.
8. Persist the assistant message.

The same entity always gets the same pseudonym across turns of the
same matter, because the dictionary detector hits on the second
mention.

## Smart-mode context tags

Smart mode is opt-in per matter and requires either:

- a user attestation that the LLM endpoint is zero-retention, or
- the matter's backend is `OllamaClient` (where zero retention is
  structural, not contractual).

When smart mode is active, on the *first* mention of an entity in a
turn the redacted output gets a parenthetical from the entity's
`public_context` — which comes from:

1. `BundledContextProvider` (147-entry curated JSON: DMA gatekeepers,
   EU institutions, NCAs, top courts, etc.), then
2. *(optional)* `WikipediaContextProvider` — fetches the Wikipedia
   summary's first sentence (≤280 chars).

The rule for what's allowed in `public_context`: only facts that
are publicly verifiable elsewhere about that entity. Never anything
from the user's own corpus.

## Two-mode privacy posture

| | **Strict** | **Smart** |
|---|---|---|
| Pseudonyms | yes | yes |
| Context tags | none | public-knowledge tags allowed |
| LLM endpoint requirement | any | zero-retention or local |
| Use case | maximum confidentiality | better analytical depth |

The mode is recorded per matter and visible at every step. The chat
input refuses to send when the mode and backend combination is
inconsistent (e.g. smart mode, a cloud backend, no attestation).

## What never leaves your machine

- The SQLite store at `~/.jude/jude.db` — contains canonical real names.
- The original document content — only its redacted form is sent.
- Conversation history in display form (rehydrated names).

## What does leave your machine (when applicable)

- The redacted text and the Jude system prompt go to the configured
  LLM endpoint (a cloud provider, or localhost via Ollama).
- Entity names go to Wikipedia if the user opts into Wikipedia
  enrichment for a matter (privacy notice in the sidebar).

## Test posture

Strict TDD from v0.4.2 onwards: every feature commit is a red-green
pair (failing tests committed first, implementation in a follow-up).
Coverage as of the latest tag:

- **132 unit & integration tests** passing.
- 4 UI smoke tests via Streamlit's `AppTest` runner.
- 1 real-LLM end-to-end regression test against the shipped Anthropic
  client (gated on its API key being present; trivially adaptable to
  any other provider once a client is added).
- 2 tests skipped by default (OCR full-loop without `tesseract`,
  privacy-filter full-loop without the 1.5 GB model download).
