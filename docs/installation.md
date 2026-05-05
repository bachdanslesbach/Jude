---
title: Installation
layout: default
---

# Installation

Jude runs on macOS and Linux. Windows is untested but should work; open
an issue if it doesn't.

## Prerequisites

- **Python 3.11 or 3.12.** Python 3.13/3.14 may work but spaCy's wheel
  availability lags. If you use `pyenv` or `asdf`, pin to 3.12 for now.
- **Git.**
- **An LLM endpoint** — either an API key for one of the cloud
  providers Jude ships a client for (Anthropic today; OpenAI / Azure /
  others are a small subclass away) or [Ollama](https://ollama.ai/)
  running locally for the no-network path.

Optional, for the additional features:

- **Tesseract** for OCR of scanned PDFs (`brew install tesseract tesseract-lang` on macOS).
- **~3 GB of disk** if you enable the `openai/privacy-filter` detector.

## Standard install

```bash
git clone https://github.com/bachdanslesbach/Jude.git
cd Jude
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg
python -m spacy download fr_core_news_md
```

## Optional extras

Each extra is independent. Install only what you need.

```bash
pip install -e ".[ocr]"             # scanned-PDF OCR (needs tesseract too)
pip install -e ".[privacy-filter]"  # OpenAI privacy filter as 5th detector
pip install -e ".[gliner]"          # GLiNER multilingual NER
```

## Setting your LLM provider's API key

Each cloud provider has its own environment variable name — Jude reads
whichever one its configured client expects:

| Provider | Variable |
|---|---|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` (when an OpenAI client is added) |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` (similarly) |

The recommended path on macOS is **`launchctl`** — it makes the key
available to GUI apps without storing it in plaintext config files.
The key persists until your next reboot.

```bash
launchctl setenv ANTHROPIC_API_KEY "sk-..."   # or whichever variable
```

If you want it to survive reboots, also add it to `~/.zshrc`:

```bash
echo 'export ANTHROPIC_API_KEY="sk-..."' >> ~/.zshrc
```

Or skip cloud entirely and use a local model — see *Using Ollama*
below.

## First run

```bash
jude init                # creates ~/.jude/jude.db, verifies spaCy models
jude ui                  # launches the chat UI on http://localhost:8501
```

Workflow on first launch:

1. Sidebar → **Create matter** → name it (e.g. `Acme v BigCorp`),
   choose strict or smart mode, attest zero-retention if you want
   smart mode.
2. **+ New conversation** in the sidebar.
3. Drag a `.txt` / `.docx` / `.pdf` / `.xlsx` onto the chat input
   (or click the paperclip), type your question, send.
4. The response appears as a chat bubble with real names rehydrated.
   Click **View what the LLM actually saw** on any bubble to inspect
   the redacted form.

## Using Ollama (no-network mode)

```bash
brew install ollama        # macOS
ollama serve &             # starts the daemon
ollama pull llama3.3       # ~40 GB; or `qwen3:32b` (~20 GB) for less RAM
```

Then in Jude's sidebar: **Change LLM backend → ollama → llama3.3 → Save**.
Smart mode no longer demands the zero-retention attestation when the
backend is local — you'll see *"Local backend — zero retention by
construction ✓"* instead.

Local model quality is below frontier cloud (Llama 3.3 70B is roughly
GPT-4-class on legal reasoning tasks; Qwen3 32B is similar). Choose
this backend when the privacy gain outweighs the analytical loss.

## Troubleshooting

**spaCy model not installed.** Run the `python -m spacy download` lines above.

**`jude ui` shows a Streamlit email prompt.** This is suppressed by
recent versions; if you see it, just press Enter to skip and update
to the latest commit.

**`SQLite objects created in a thread can only be used in that same thread`.**
You're on an old version. `git pull` and restart Streamlit.

**LLM API key not picked up by the UI.** macOS GUI apps don't inherit
shell env. Use `launchctl setenv` (see above) and restart Streamlit
fully.

**`ollama: connection refused`.** Run `ollama serve &` in a terminal
first.

**OCR fails with "tesseract not installed".** `brew install tesseract
tesseract-lang` on macOS, or `apt install tesseract-ocr
tesseract-ocr-eng tesseract-ocr-fra` on Debian.

For anything else: open an issue at <https://github.com/bachdanslesbach/Jude/issues>.
