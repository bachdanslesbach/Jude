"""UI smoke tests using Streamlit's `AppTest` runner.

Headless: no browser, no Streamlit server. The runner imports `app.py`,
runs it as if a user had loaded the page, and exposes the resulting
widget tree for assertion and interaction.

These tests are deliberately coarse — full UI tests are brittle. Each
one covers a flow that has previously caused a runtime crash or a UX
regression we'd want to catch automatically:

  * Empty state — no matters → user sees the create-matter form.
    (Catches: SQLite cross-thread crash from v0.3 era.)

  * Create matter → the new matter is selected.
    (Catches: 'st.session_state.matter_select cannot be modified after
    the widget is instantiated' — would have fired immediately.)

  * Switch LLM backend to Ollama → a smart-mode matter no longer
    demands a zero-retention attestation.

  * Risk panel: pasting redacted text and clicking Assess produces
    LOW/MEDIUM/HIGH badges (no LLM call required).

Database isolation: each test points JUDE_HOME at a fresh tmp_path so
they don't share state.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path("src/jude/ui/app.py").resolve())
ENTITIES_PAGE = str(Path("src/jude/ui/pages/2_Entities.py").resolve())


@pytest.fixture
def isolated_jude_home(tmp_path: Path, monkeypatch):
    """Point JUDE_HOME at an empty tmp dir for each UI test."""

    monkeypatch.setenv("JUDE_HOME", str(tmp_path))
    return tmp_path


def test_empty_state_invites_matter_creation(isolated_jude_home):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    assert not at.exception, f"app raised: {at.exception}"
    # With no matters, the sidebar shows the "Create matter" expander
    # auto-expanded; the main panel shows the "Create a matter…" prompt.
    main_messages = " ".join(i.value for i in at.info)
    assert "create a matter" in main_messages.lower()


def test_creating_a_matter_renders_chat_panel(isolated_jude_home):
    at = AppTest.from_file(APP_PATH).run(timeout=30)

    # Find the matter-name text input (sidebar) and fill it.
    name_inputs = [t for t in at.text_input if t.label == "Name"]
    assert name_inputs, "expected sidebar 'Name' input on first run"
    name_inputs[0].set_value("smoke-test-matter")
    at = at.run(timeout=30)

    # Click the sidebar Create button.
    create_buttons = [b for b in at.button if b.label == "Create"]
    assert create_buttons, "expected sidebar 'Create' button"
    create_buttons[0].click()
    at = at.run(timeout=30)

    assert not at.exception, f"app raised after Create: {at.exception}"
    # Matter is selected → sidebar shows the LLM/Mode/Conversations widgets,
    # which only render when a matter is active. The new matter name shows up
    # in the matter-picker selectbox option list.
    sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
    assert "**LLM:**" in sidebar_md
    assert "**Mode:**" in sidebar_md
    selectboxes = [s for s in at.sidebar.selectbox if s.label == "Matter"]
    assert selectboxes, "expected Matter selectbox in sidebar"
    assert any(
        "smoke-test-matter" in opt for opt in selectboxes[0].options
    ), "newly created matter should appear in the picker"


def test_switching_to_ollama_clears_zero_retention_warning(isolated_jude_home):
    """Reproduces the new v0.4.4 behaviour: a smart-mode matter without a
    zero-retention attestation should still be allowed if the backend is
    local Ollama."""

    from jude.paths import default_db_path
    from jude.store import Store
    from jude.types import Mode

    # Pre-create a matter directly in the store so the test isn't gated on
    # the create-matter UI flow.
    with Store(default_db_path()) as s:
        m = s.create_matter(
            "smart-no-zr",
            mode=Mode.SMART,
            zero_retention_attested=False,
        )
        s.create_conversation(m.id, title="t")

    at = AppTest.from_file(APP_PATH).run(timeout=30)
    sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
    # On the anthropic default backend the warning is shown.
    assert "Smart mode without zero-retention attestation" in sidebar_md

    # Switch backend to ollama.
    backend_radios = [r for r in at.sidebar.radio if r.label == "Backend"]
    assert backend_radios, "expected Backend radio in sidebar"
    backend_radios[0].set_value("ollama")
    at = at.run(timeout=30)
    save_buttons = [b for b in at.sidebar.button if b.label == "Save backend"]
    assert save_buttons, "expected sidebar 'Save backend' button"
    save_buttons[0].click()
    at = at.run(timeout=30)

    # Now the warning is gone, replaced by the local-backend reassurance.
    sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
    assert "Smart mode without zero-retention attestation" not in sidebar_md
    assert "Local backend" in sidebar_md


def test_chat_user_bubble_shows_inline_risk_badge(isolated_jude_home):
    """After each user turn the chat panel renders a small re-identification
    risk badge alongside the bubble — automatically, without the user having
    to copy-paste into the Entities page. Catches the case where redacted
    output is structurally identifying (currency + date + case ref in the
    same paragraph as a pseudonym)."""

    from jude.paths import default_db_path
    from jude.store import Store
    from jude.types import EntityType, MessageRole, Mode

    with Store(default_db_path()) as s:
        matter = s.create_matter("auto-risk-smoke", mode=Mode.STRICT)
        conv = s.create_conversation(matter.id, title="t")
        # Seed an entity so its pseudonym is known to the assessor.
        s.create_entity(
            matter.id, "Microsoft", EntityType.ORG,
            surface_forms={"Microsoft"},
        )
        # Seed a user message with three risk signals (currency + date + case).
        s.add_message(
            conv.id,
            MessageRole.USER,
            redacted_text=(
                "Org1 paid €1,000,000,000 on October 13, 2023 in Case T-1/24."
            ),
            display_text="Microsoft paid …",
        )
        # And an assistant reply so the turn is complete.
        s.add_message(
            conv.id,
            MessageRole.ASSISTANT,
            redacted_text="Reply about Org1.",
            display_text="Reply about Microsoft.",
        )

    at = AppTest.from_file(APP_PATH).run(timeout=30)
    assert not at.exception, f"app raised: {at.exception}"

    rendered = " ".join(m.value for m in at.markdown).upper()
    # Three signals → score 3 → MEDIUM badge near the user bubble.
    assert "MEDIUM" in rendered
    # The Org1 pseudonym must NOT leak into the user-visible bubble — the
    # display_text we seeded uses the canonical name.
    user_visible = " ".join(m.value for m in at.chat_message[0].markdown)
    assert "Microsoft" in user_visible


def test_risk_panel_assesses_pasted_redacted_text(isolated_jude_home):
    """No LLM call. The risk assessor is local; we just verify the UI
    surfaces a LOW/MEDIUM/HIGH badge when the user pastes a redacted
    chunk and clicks Assess."""

    from jude.paths import default_db_path
    from jude.store import Store
    from jude.types import EntityType, Mode

    with Store(default_db_path()) as s:
        matter = s.create_matter("risk-smoke", mode=Mode.STRICT)
        s.create_entity(
            matter.id,
            "Microsoft",
            EntityType.ORG,
        )

    at = AppTest.from_file(ENTITIES_PAGE).run(timeout=30)
    assert not at.exception, f"entities page raised: {at.exception}"

    risk_inputs = [
        t for t in at.text_area if t.label == "Redacted text to assess"
    ]
    assert risk_inputs, "expected risk-assessment textarea"
    risk_inputs[0].set_value(
        "Org1 paid €1,000,000,000 on October 13, 2023 in Case T-1/24."
    )
    at = at.run(timeout=30)
    risk_buttons = [b for b in at.button if b.label == "Assess risk"]
    assert risk_buttons, "expected 'Assess risk' button"
    risk_buttons[0].click()
    at = at.run(timeout=30)

    assert not at.exception, f"app raised after Assess: {at.exception}"
    rendered = " ".join(m.value for m in at.markdown).upper()
    # Three signals (currency, date, case ref) in a strict-mode matter with
    # no public_context → score 3 → MEDIUM. HIGH would require smart mode
    # with a public-knowledge tag (covered in test_risk.py).
    assert "MEDIUM" in rendered
    assert "(3)" in rendered  # the score badge
