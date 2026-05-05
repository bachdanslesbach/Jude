# Contributing to Jude

Jude is open-source legal-tech. Contributions are welcome — bug
reports, feature requests, code, documentation, translations.

## Ground rules

1. **Test-driven development.** From v0.4.2 onwards, every feature
   ships as a red-green commit pair: failing tests first, then the
   implementation that turns them green. PRs that don't follow this
   pattern will be asked to split. The discipline is visible in
   `git log`.

2. **Privacy first.** Jude exists because lawyers can't trust their
   client data to third-party services. Don't add features that
   weaken that posture without an explicit per-matter opt-in. New
   network calls require a one-line privacy notice in the UI.

3. **Public-knowledge only in the bundled context dataset.** Every
   `context` field in `src/jude/data/known_entities.json` must be
   verifiable from public primary sources (the entity's own
   materials, the Commission's decisions database, government
   websites). PRs adding entities should cite the source in the
   commit message.

## Development setup

```bash
git clone https://github.com/bachdanslesbach/Jude.git
cd Jude
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_lg
python -m spacy download fr_core_news_md
pytest        # 132 tests should pass; 2 skipped is normal
```

## Running the test suite

```bash
pytest                            # default: skip integration tests
pytest tests/test_xlsx_adapter.py # one file
pytest -k "wikipedia"             # one keyword
pytest -v                         # verbose
```

The two skipped tests need optional setup:

- `tests/test_pdf_adapter.py::test_ocr_extracts_text_from_image_pdf`
  needs `tesseract` (`brew install tesseract tesseract-lang`).
- `tests/test_privacy_filter.py::test_privacy_filter_detects_email_and_address`
  needs the 1.5 GB `openai/privacy-filter` model download. Enable by
  removing the `@pytest.mark.skipif(True, ...)` decorator and
  installing `pip install -e ".[privacy-filter]"`.

The real-LLM e2e test (`tests/test_e2e_anthropic.py`) runs only when
`ANTHROPIC_API_KEY` is set; it costs a few US cents per run.

## Adding a new feature

1. **Open an issue** describing the behavior.
2. **Write failing tests** in `tests/test_<feature>.py` that capture
   the user-facing contract. Run pytest, confirm RED.
3. **Commit the failing tests.** The convention is a commit message
   prefixed `<feature> (red): …`.
4. **Implement.** Run pytest until all the new tests are GREEN.
5. **Commit the implementation.** Convention: `<feature> (green): …`.
6. **Open a PR.**

Code style: ruff handles formatting and linting. Run `ruff check src
tests` before pushing.

## Adding a new entity to the bundled context dataset

Edit `src/jude/data/known_entities.json`. Each entry needs:

```json
{
  "canonical": "Authority's official name in its working language",
  "aliases": ["common short forms", "English version if non-English canonical"],
  "type": "ORG",
  "context": "One short factual sentence, ~20 words max, verifiable from public sources"
}
```

Hard rules:

- `type` must be `"ORG"`, `"PERSON"` or `"LOC"`. Almost everything
  bundled is ORG.
- No alias may appear under two different canonicals. The existing
  file is collision-free; the test suite (`test_context.py::test_no_alias_collisions`)
  enforces this.
- `context` must contain only facts that are publicly verifiable from
  primary sources. Cite the source in the PR description.

## Reporting a bug

Open an issue with:

1. The minimal input that reproduces the problem.
2. The expected behavior.
3. The actual behavior (full traceback if any).
4. Your environment (`python --version`, `jude --help`, OS).

If the bug touches client data, redact aggressively before pasting.
We don't need a real document to fix a bug.

## Security disclosure

For vulnerabilities, please email <etienne.m.perrin@protonmail.com>
rather than opening a public issue. Standard responsible-disclosure
window applies.
