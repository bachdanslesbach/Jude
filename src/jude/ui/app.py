"""Jude — chat-first Streamlit UI.

Sidebar holds matter and mode controls plus the conversation list. The main
panel is a single chat: paste text or attach a file in the input, get a
rehydrated response. Every input is redacted before it leaves the machine;
every output is rehydrated before it's shown to the user. The user is
always the last filter — they can inspect the redacted form of any turn,
and crucially they must explicitly **approve & send** before any data
reaches the LLM.
"""

from __future__ import annotations

import os

import streamlit as st

from jude.chat import (
    FileAttachment,
    PreparedTurn,
    commit_streaming_turn,
    prepare_turn,
    preview_detection,
    send_turn,
)
from jude.llm import AnthropicClient, LLMClient, OllamaClient
from jude.paths import default_db_path
from jude.risk import RiskAssessment, RiskLevel, assess_risks
from jude.store import Store
from jude.types import Conversation, Matter, Message, MessageRole, Mode

st.set_page_config(page_title="Jude", layout="wide", initial_sidebar_state="expanded")


# ----- session-state helpers -----


def _store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store(default_db_path())
    return st.session_state.store


_DEFAULT_OLLAMA_MODEL = "llama3.3"


def _llm_for(matter: Matter) -> LLMClient:
    """Build (and cache) the LLMClient configured on this matter."""

    cache_key = f"llm_{matter.id}_{matter.llm_endpoint}_{matter.llm_model or ''}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    if matter.llm_endpoint == "ollama":
        client: LLMClient = OllamaClient(
            model=matter.llm_model or _DEFAULT_OLLAMA_MODEL,
        )
    else:
        client = AnthropicClient(
            model=matter.llm_model or "claude-sonnet-4-5",
        )
    st.session_state[cache_key] = client
    return client


# ----- sidebar -----


def sidebar() -> tuple[Matter | None, Conversation | None]:
    st.sidebar.title("Jude")
    st.sidebar.caption("Local-first anonymization for legal LLM use.")

    store = _store()
    matter = _matter_picker(store)
    if matter is None:
        return None, None

    _backend_controls(store, matter)
    _mode_controls(store, matter)
    _detector_controls(matter)
    _redaction_preview(matter)
    conv = _conversation_picker(store, matter)
    _entities_link()
    return matter, conv


def _matter_picker(store: Store) -> Matter | None:
    # Honour pending programmatic selection from a previous rerun. We can't
    # write to a widget's session_state key after the widget renders in the
    # same run, so create-matter stashes its target here and we apply it on
    # the next run before the widget is instantiated.
    pending = st.session_state.pop("_pending_matter_select", None)
    if pending is not None:
        st.session_state["matter_select"] = pending

    matters = store.list_matters()
    options: dict[str, str] = {f"{m.name} · {m.mode.value}": m.id for m in matters}
    options["+ New matter"] = ""

    label = st.sidebar.selectbox(
        "Matter", list(options.keys()), key="matter_select"
    )
    if options[label] == "":
        return _matter_create(store)
    return store.get_matter(options[label])


def _matter_create(store: Store) -> Matter | None:
    with st.sidebar.expander("Create new matter", expanded=True):
        name = st.text_input("Name", key="new_matter_name")
        mode_label = st.radio(
            "Mode",
            options=["strict", "smart"],
            help=(
                "Strict: pseudonyms only. "
                "Smart: pseudonyms + public-knowledge tags. "
                "Smart requires a zero-retention LLM endpoint."
            ),
            horizontal=True,
            key="new_matter_mode",
        )
        zr = st.checkbox(
            "I attest the LLM endpoint is zero-retention",
            key="new_matter_zr",
            disabled=(mode_label == "strict"),
        )
        if st.button("Create", disabled=not name, type="primary"):
            try:
                m = store.create_matter(
                    name=name,
                    mode=Mode(mode_label),
                    zero_retention_attested=zr,
                )
                st.session_state["_pending_matter_select"] = (
                    f"{m.name} · {m.mode.value}"
                )
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    return None


def _backend_controls(store: Store, matter: Matter) -> None:
    backend_label = (
        "Anthropic (cloud)"
        if matter.llm_endpoint == "anthropic"
        else f"Ollama (local · {matter.llm_model or _DEFAULT_OLLAMA_MODEL})"
    )
    st.sidebar.markdown(f"**LLM:** `{backend_label}`")
    with st.sidebar.expander("Change LLM backend"):
        backend = st.radio(
            "Backend",
            options=["anthropic", "ollama"],
            index=0 if matter.llm_endpoint == "anthropic" else 1,
            horizontal=True,
            key=f"backend_{matter.id}",
            help=(
                "Anthropic (cloud) requires an API key; smart mode requires "
                "your zero-retention attestation. Ollama (local) runs entirely "
                "on this machine — smart mode works without attestation. "
                "Local model quality is below frontier cloud."
            ),
        )
        default_model = (
            matter.llm_model
            or ("claude-sonnet-4-5" if backend == "anthropic" else _DEFAULT_OLLAMA_MODEL)
        )
        model = st.text_input(
            "Model",
            value=default_model,
            key=f"model_{matter.id}",
            help=(
                "For Anthropic: e.g. `claude-sonnet-4-5`, `claude-opus-4-5`. "
                "For Ollama: any tag you've pulled, e.g. `llama3.3`, "
                "`qwen3:32b`, `mistral-large`."
            ),
        )
        if st.button("Save backend", key=f"save_backend_{matter.id}"):
            store.set_llm_endpoint(matter.id, backend, model=model or None)
            st.rerun()


def _mode_controls(store: Store, matter: Matter) -> None:
    st.sidebar.markdown(f"**Mode:** `{matter.mode.value}`")
    if matter.mode == Mode.SMART:
        if matter.zero_retention_attested:
            st.sidebar.markdown(":green[Zero-retention attested ✓]")
        elif matter.llm_endpoint == "ollama":
            st.sidebar.markdown(
                ":green[Local backend — zero retention by construction ✓]"
            )
        else:
            st.sidebar.markdown(":red[Smart mode without zero-retention attestation]")
    with st.sidebar.expander("Change mode"):
        new_mode = st.radio(
            "Mode",
            options=["strict", "smart"],
            index=0 if matter.mode == Mode.STRICT else 1,
            horizontal=True,
            key=f"mode_{matter.id}",
        )
        zr = st.checkbox(
            "Zero-retention attested",
            value=matter.zero_retention_attested,
            disabled=(new_mode == "strict"),
            key=f"zr_{matter.id}",
        )
        if st.button("Save mode", key=f"save_mode_{matter.id}"):
            try:
                store.set_mode(matter.id, Mode(new_mode), zero_retention_attested=zr)
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _detector_controls(matter: Matter) -> None:
    with st.sidebar.expander("Advanced detectors"):
        st.checkbox(
            "OpenAI Privacy Filter (addresses, secrets) — heavy, ~3 GB",
            key=f"use_pf_{matter.id}",
            value=False,
            help=(
                "Adds a 5th detector backed by openai/privacy-filter for "
                "private addresses, API keys, account numbers and other PII "
                "that spaCy misses. First use downloads ~1.5 GB of weights. "
                "Requires `pip install jude[privacy-filter]`."
            ),
        )
    with st.sidebar.expander("Smart-mode enrichment"):
        st.checkbox(
            "Enrich smart-mode context from Wikipedia",
            key=f"use_wiki_{matter.id}",
            value=False,
            help=(
                "When the bundled known-entities dataset doesn't cover an "
                "entity, fall back to Wikipedia for a one-line public-"
                "knowledge tag. Privacy note: this sends the entity's "
                "canonical name to Wikipedia's REST API, which logs the IP "
                "and query. Only enable for matters where the parties' "
                "names are themselves public."
            ),
        )


def _conversation_picker(store: Store, matter: Matter) -> Conversation | None:
    st.sidebar.divider()
    st.sidebar.markdown("**Conversations**")

    if st.sidebar.button("+ New conversation", use_container_width=True):
        conv = store.create_conversation(matter.id)
        st.session_state[f"active_conv_{matter.id}"] = conv.id
        st.rerun()

    conversations = store.list_conversations(matter.id)
    if not conversations:
        st.sidebar.caption("None yet.")
        return None

    active_key = f"active_conv_{matter.id}"
    if active_key not in st.session_state:
        st.session_state[active_key] = conversations[0].id

    for conv in conversations:
        is_active = st.session_state[active_key] == conv.id
        label = ("▸ " if is_active else "  ") + conv.title
        if st.sidebar.button(
            label,
            key=f"pick_{conv.id}",
            use_container_width=True,
            type=("primary" if is_active else "secondary"),
        ):
            st.session_state[active_key] = conv.id
            st.rerun()

    _conversation_management(store, matter, conversations)
    return store.get_conversation(st.session_state[active_key])


def _conversation_management(
    store: Store,
    matter: Matter,
    conversations: list[Conversation],
) -> None:
    """Inline rename / delete actions for conversations.

    Each row is a (title-input, delete-button) pair so the sidebar
    stays compact. Renames fire when the input loses focus (Streamlit
    default text_input rerun behaviour); deletions show a one-click
    button styled as `:red[🗑]` and clear the active selection if the
    deleted conversation was the active one.
    """

    if not conversations:
        return
    with st.sidebar.expander("Manage conversations"):
        for conv in conversations:
            cols = st.columns([5, 1])
            new_title = cols[0].text_input(
                "title",
                value=conv.title,
                key=f"rename_{conv.id}",
                label_visibility="collapsed",
            )
            new_title = (new_title or "").strip()
            if new_title and new_title != conv.title:
                store.rename_conversation(conv.id, new_title)
                st.rerun()
            if cols[1].button("🗑", key=f"del_{conv.id}", help="Delete this conversation"):
                store.delete_conversation(conv.id)
                active_key = f"active_conv_{matter.id}"
                if st.session_state.get(active_key) == conv.id:
                    st.session_state.pop(active_key, None)
                st.rerun()


def _redaction_preview(matter: Matter) -> None:
    with st.sidebar.expander("Preview detection (scratch)"):
        st.caption(
            "Paste text to see what Jude would detect — no chat turn is "
            "sent and nothing is added to the per-matter dictionary."
        )
        sample = st.text_area(
            "Scratch text",
            key=f"preview_input_{matter.id}",
            label_visibility="collapsed",
            height=110,
            placeholder="Paste a draft sentence or paragraph…",
        )
        if sample.strip():
            counts = preview_detection(sample, _store(), matter.id)
            if counts:
                total = sum(counts.values())
                st.markdown(f"**{total} entities** detected:")
                for type_name, n in sorted(
                    counts.items(), key=lambda kv: -kv[1]
                ):
                    st.markdown(f"- {n} × `{type_name}`")
            else:
                st.markdown("_no entities detected._")


def _entities_link() -> None:
    st.sidebar.divider()
    st.sidebar.page_link(
        "pages/2_Entities.py",
        label="🔍 Manage entities",
        help="Per-matter dictionary of detected entities and their pseudonyms.",
    )


# ----- main panel -----


def _render_turn_risk_badge(
    message: Message, entities: list, mode: Mode
) -> None:
    """Render a re-identification risk badge alongside a user message.

    Surfaces the worst-case risk for any entity actually mentioned in this
    turn's redacted text. Silent when no risk signals are present.
    """

    risks = [
        r for r in assess_risks(message.redacted_text, entities, mode)
        if r.score > 0
    ]
    if not risks:
        return
    worst = risks[0]
    badge = {
        RiskLevel.HIGH: ":red[**HIGH** re-identification risk]",
        RiskLevel.MEDIUM: ":orange[**MEDIUM** re-identification risk]",
        RiskLevel.LOW: ":blue[low re-identification risk]",
    }[worst.level]
    st.caption(badge)
    if worst.reasons:
        with st.expander(f"why? · top entity: {worst.pseudonym}"):
            for r in risks[:3]:
                st.markdown(f"**{r.pseudonym}** — {r.level.value} ({r.score})")
                for reason in r.reasons:
                    st.write(f"• {reason}")


def _pending_key(conv: Conversation) -> str:
    return f"pending_review_{conv.id}"


def _render_review_panel(
    matter: Matter, conv: Conversation, pending: dict
) -> None:
    """Show the redacted text + entity diff for explicit human review,
    with Approve/Cancel buttons. This is THE filter step Jude exists for."""

    st.markdown("### 🔒 Review what will be sent")
    st.caption(
        "Nothing has been sent to the LLM yet. Read the redacted text "
        "carefully — anything that survives this step is what the LLM "
        "actually sees. You can cancel and edit."
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Original (stays on your machine)**")
        st.text_area(
            "Original",
            value=pending["raw_text"],
            height=320,
            label_visibility="collapsed",
            disabled=True,
            key=f"orig_review_{conv.id}",
        )
    with cols[1]:
        st.markdown("**Redacted (this is what the LLM will see)**")
        st.text_area(
            "Redacted",
            value=pending["redacted_text"],
            height=320,
            label_visibility="collapsed",
            disabled=True,
            key=f"red_review_{conv.id}",
        )

    entities = pending.get("entities") or []
    if entities:
        with st.expander(f"{len(entities)} entities mapped"):
            for ent in entities:
                pseudo = ent.get("pseudonym") if isinstance(ent, dict) else ent.pseudonym
                canonical = ent.get("canonical") if isinstance(ent, dict) else ent.canonical
                etype = ent.get("entity_type") if isinstance(ent, dict) else (
                    ent.entity_type.value if hasattr(ent.entity_type, "value") else ent.entity_type
                )
                st.markdown(f"- `{pseudo}` ← **{canonical}**  _{etype}_")

    risk_assess = assess_risks(
        pending["redacted_text"],
        _store().list_entities(matter.id),
        matter.mode,
    )
    risk_assess = [r for r in risk_assess if r.score > 0]
    if risk_assess:
        worst = risk_assess[0]
        badge = {
            RiskLevel.HIGH: ":red[**HIGH** re-identification risk — review carefully]",
            RiskLevel.MEDIUM: ":orange[**MEDIUM** re-identification risk]",
            RiskLevel.LOW: ":blue[low re-identification risk]",
        }[worst.level]
        st.markdown(badge)
        with st.expander(f"why? · top entity: {worst.pseudonym}"):
            for r in risk_assess[:5]:
                st.markdown(f"**{r.pseudonym}** — {r.level.value} ({r.score})")
                for reason in r.reasons:
                    st.write(f"• {reason}")

    cols = st.columns([1, 1, 4])
    approve = cols[0].button(
        "✓ Approve & send", type="primary", key=f"approve_{conv.id}"
    )
    cancel = cols[1].button("← Cancel", key=f"cancel_{conv.id}")
    if cancel:
        st.session_state.pop(_pending_key(conv), None)
        st.rerun()
    if approve:
        try:
            llm = _llm_for(matter)
            prepared_obj = PreparedTurn.model_validate(pending)
            with st.chat_message("assistant"):
                st.write_stream(commit_streaming_turn(
                    conversation=conv,
                    prepared=prepared_obj,
                    store=_store(),
                    mode=matter.mode,
                    llm=llm,
                ))
            st.session_state.pop(_pending_key(conv), None)
            st.rerun()
        except PermissionError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"Send failed: {e}")


def render_conversation(matter: Matter, conv: Conversation) -> None:
    st.markdown(f"#### {conv.title}")
    st.caption(
        f"Matter: `{matter.name}` · Mode: `{matter.mode.value}` · "
        f"Conv id: `{conv.id[:8]}…`"
    )

    store = _store()
    messages = store.list_messages(conv.id)
    entities = store.list_entities(matter.id)
    for m in messages:
        with st.chat_message(m.role.value):
            st.markdown(m.display_text)
            if m.role == MessageRole.USER:
                _render_turn_risk_badge(m, entities, matter.mode)
            if m.redacted_text != m.display_text:
                with st.expander("View what the LLM actually saw"):
                    st.code(m.redacted_text, language=None)

    # If there's a pending review for this conversation, render it instead
    # of the chat input — the user must approve or cancel before typing
    # anything new.
    pending = st.session_state.get(_pending_key(conv))
    if pending:
        _render_review_panel(matter, conv, pending)
        return

    payload = st.chat_input(
        "Ask Jude — paste text or attach a file…",
        accept_file="multiple",
        file_type=["txt", "docx", "pdf", "xlsx"],
    )

    if not payload:
        if not messages:
            st.info(
                "Type your question or paste a document to begin. Every turn "
                "is detected and redacted locally first; you'll review the "
                "redacted form before anything is sent to the LLM."
            )
        return

    user_text = (payload.text or "").strip()
    raw_files = list(payload.files or [])
    if not user_text and not raw_files:
        return

    attachments = [FileAttachment(f.name, f.getvalue()) for f in raw_files]

    if (
        matter.mode == Mode.SMART
        and not matter.zero_retention_attested
        and matter.llm_endpoint != "ollama"
    ):
        st.error(
            "This matter is in smart mode but no zero-retention attestation is "
            "on file and the backend is a remote API. Either attest in the "
            "sidebar, switch to a local backend, or change the mode."
        )
        return

    use_pf = bool(st.session_state.get(f"use_pf_{matter.id}", False))
    use_wiki = bool(st.session_state.get(f"use_wiki_{matter.id}", False))

    # NEW UX: don't send straight to the LLM. Prepare the turn (run
    # detection + redaction) and stash the result for explicit human
    # review on the next rerun. Approve & send is a separate click.
    try:
        prepared = prepare_turn(
            conversation=conv,
            user_text=user_text,
            attachments=attachments,
            store=store,
            mode=matter.mode,
            use_privacy_filter=use_pf,
            use_wikipedia=use_wiki,
        )
    except PermissionError as e:
        st.error(str(e))
        return
    except Exception as e:  # noqa: BLE001
        st.error(f"Preparation failed: {e}")
        return

    st.session_state[_pending_key(conv)] = prepared.model_dump()
    st.rerun()


def _api_key_env_for_backend(backend: str) -> str | None:
    """Return the env var name an LLM backend needs, or None if it's
    keyless (e.g. Ollama)."""

    if backend == "anthropic":
        return "ANTHROPIC_API_KEY"
    return None


def _llm_key_available(matter: Matter) -> bool:
    """True iff the configured backend has a usable credential."""

    var = _api_key_env_for_backend(matter.llm_endpoint)
    if var is None:
        return True  # local backend / no auth needed
    if os.environ.get(var):
        return True
    # macOS bridge: read from launchctl getenv if shell env didn't have it.
    from jude.llm.anthropic_client import _resolve_api_key

    if matter.llm_endpoint == "anthropic":
        return bool(_resolve_api_key())
    return False


def _render_api_key_form(matter: Matter) -> None:
    """Block the chat behind a key-entry form when the configured backend
    needs a credential we can't find. The submitted value is set into
    os.environ for the lifetime of this Python process — not written to
    disk by Jude. For persistence across sessions, the user runs
    `launchctl setenv` (macOS) or adds an export to their shell config."""

    var = _api_key_env_for_backend(matter.llm_endpoint)
    assert var is not None
    st.markdown(f"### 🔑 {var} required")
    st.caption(
        "Jude couldn't find a credential for the configured LLM backend. "
        "Paste your key below to use it for the current session — the "
        "value lives in this Streamlit process's memory only and is not "
        "written to disk by Jude. For persistence across restarts, "
        "set it once via `launchctl setenv` (macOS) or `export` (Linux/"
        "WSL) in your shell config."
    )
    pasted = st.text_input(
        var, type="password", key=f"keypad_{var}",
        placeholder="sk-... or your provider's equivalent",
    )
    cols = st.columns([1, 1, 4])
    if cols[0].button("Use for this session", type="primary"):
        if pasted.strip():
            os.environ[var] = pasted.strip()
            # Drop the cached LLM client so it picks up the new key on
            # the next call.
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith(f"llm_{matter.id}_"):
                    del st.session_state[k]
            st.success("Key accepted. Returning to the chat…")
            st.rerun()
    if cols[1].button("Switch to local Ollama"):
        store = _store()
        store.set_llm_endpoint(matter.id, "ollama", model=_DEFAULT_OLLAMA_MODEL)
        st.rerun()
    st.markdown(
        "**Why bother?** "
        "Without a key, Jude can detect and rehydrate locally but can't "
        "send a turn to a cloud LLM. Switching to Ollama runs a model on "
        "your own machine instead — no key, no network."
    )


def main() -> None:
    matter, conv = sidebar()
    if matter is None:
        st.info("Create a matter in the sidebar to begin.")
        return
    if not _llm_key_available(matter):
        _render_api_key_form(matter)
        return
    if conv is None:
        st.info("No conversations yet. Click **+ New conversation** in the sidebar.")
        return
    render_conversation(matter, conv)


main()
