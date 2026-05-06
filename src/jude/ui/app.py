"""Jude — chat-first Streamlit UI.

Sidebar holds matter and mode controls plus the conversation list. The main
panel is a single chat: paste text or attach a file in the input, get a
rehydrated response. Every input is redacted before it leaves the machine;
every output is rehydrated before it's shown to the user. The user is
always the last filter — they can inspect the redacted form of any turn.
"""

from __future__ import annotations

import streamlit as st

from jude.chat import (
    FileAttachment,
    preview_detection,
    send_turn,
    send_turn_streaming,
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
    return store.get_conversation(st.session_state[active_key])


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

    payload = st.chat_input(
        "Ask Jude — paste text or attach a file…",
        accept_file="multiple",
        file_type=["txt", "docx", "pdf", "xlsx"],
    )

    if not payload:
        if not messages:
            st.info(
                "Type your question or paste a document to begin. Anything you "
                "send is redacted on this machine before being sent to the LLM."
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

    # Optimistic echo of the user's input so they see their bubble
    # immediately, before the assistant streams.
    with st.chat_message("user"):
        st.markdown(user_text or "_(file attached)_")

    with st.chat_message("assistant"):
        try:
            stream = send_turn_streaming(
                conversation=conv,
                user_text=user_text,
                attachments=attachments,
                store=store,
                mode=matter.mode,
                llm=_llm_for(matter),
                use_privacy_filter=use_pf,
                use_wikipedia=use_wiki,
            )
            st.write_stream(stream)
        except PermissionError as e:
            st.error(str(e))
            return
        except Exception as e:  # noqa: BLE001
            st.error(f"Turn failed: {e}")
            return
    st.rerun()


def main() -> None:
    matter, conv = sidebar()
    if matter is None:
        st.info("Create a matter in the sidebar to begin.")
        return
    if conv is None:
        st.info("No conversations yet. Click **+ New conversation** in the sidebar.")
        return
    render_conversation(matter, conv)


main()
