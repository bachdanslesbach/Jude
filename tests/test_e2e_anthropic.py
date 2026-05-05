"""End-to-end regression test against the real Anthropic API.

Skipped by default. Runs only when an `ANTHROPIC_API_KEY` is present in
the environment (or, on macOS, in `launchctl getenv`). Costs a few US
cents per invocation.

Run it manually with:

    pytest tests/test_e2e_anthropic.py -v
        # if ANTHROPIC_API_KEY is exported in your shell

It exercises the *full* loop:

    redact (real spaCy NER + bundled context)
        → real Anthropic API call
        → rehydrate

…on the same fictional memo we used for the earlier manual smoke test,
and asserts the rehydrated response mentions the real party names
(Amazon, Microsoft, European Commission) — proving the round-trip
works end-to-end against the production API.

This is the test that, if it goes red, tells us the integration is
genuinely broken — not just a mock or a unit boundary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _resolve_api_key() -> str | None:
    val = os.environ.get("ANTHROPIC_API_KEY")
    if val:
        return val
    if shutil.which("launchctl") is None:
        return None
    try:
        result = subprocess.run(
            ["launchctl", "getenv", "ANTHROPIC_API_KEY"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


_KEY = _resolve_api_key()


@pytest.mark.skipif(
    _KEY is None,
    reason="ANTHROPIC_API_KEY not available in env or launchctl; "
    "manual integration test only",
)
def test_full_redact_send_rehydrate_loop_against_real_api(tmp_path: Path):
    """Real API call. Verifies the round-trip preserves entity identity:
    you put Amazon in, Claude reasons about Org1, you get Amazon back."""

    os.environ["ANTHROPIC_API_KEY"] = _KEY  # noqa: SIM112 — we just resolved it

    from jude.adapters import TextAdapter
    from jude.chat import send_turn
    from jude.llm import AnthropicClient
    from jude.paths import jude_home
    from jude.store import Store
    from jude.types import Mode

    os.environ["JUDE_HOME"] = str(tmp_path)
    db_path = jude_home() / "jude.db"

    memo = (
        "MEMO — Project Aurora.\n\n"
        "Amazon is acquiring Lumen Reality SARL for €450 million. The "
        "European Commission is reviewing under the Digital Markets Act. "
        "Microsoft, as a partner via Azure, may be called as a witness."
    )
    memo_path = tmp_path / "memo.txt"
    TextAdapter.write(memo_path, memo)

    with Store(db_path) as store:
        # Use STRICT mode for the e2e assertion — no public-knowledge context
        # tags leak into the redacted text, so we can assert party names are
        # fully absent.
        matter = store.create_matter(
            "e2e-test",
            mode=Mode.STRICT,
            zero_retention_attested=True,
        )
        conv = store.create_conversation(matter.id, title="e2e")

        client = AnthropicClient(model="claude-sonnet-4-5")
        user_msg, assistant_msg = send_turn(
            conversation=conv,
            user_text=(
                memo
                + "\n\n---\n\nQUESTION: List the three parties involved "
                "and what role each plays. One short bullet per party."
            ),
            attachments=[],
            store=store,
            mode=Mode.STRICT,
            llm=client,
        )

    # The user message stored what Claude actually saw — pseudonymised.
    assert "Amazon" not in user_msg.redacted_text
    assert "Microsoft" not in user_msg.redacted_text
    # …and what we keep on disk for ourselves.
    assert "Amazon" in user_msg.display_text

    # The assistant message: Claude's raw response uses pseudonyms, the
    # rehydrated copy puts the real names back. We don't pin which entities
    # Claude chose to mention (it might decide a peripheral party isn't
    # worth bullet-pointing); we assert that at least two of the three
    # primary parties round-trip cleanly, which is the regression we care
    # about.
    rehydrated = assistant_msg.display_text.lower()
    parties_seen = sum(
        1 for name in ("amazon", "microsoft", "lumen reality", "european commission")
        if name in rehydrated
    )
    assert parties_seen >= 2, (
        f"rehydration only produced {parties_seen} of the named parties; "
        f"got {assistant_msg.display_text!r}"
    )
    # Pseudonyms should NOT appear in the rehydrated form — that would mean
    # rehydration missed at least one mapping.
    assert "Org1" not in assistant_msg.display_text
    assert "Org2" not in assistant_msg.display_text
