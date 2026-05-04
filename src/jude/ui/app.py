from __future__ import annotations

from pathlib import Path

import streamlit as st

from jude.adapters import DocxAdapter, PdfAdapter, TextAdapter
from jude.adapters.docx import PARAGRAPH_SEP, DocxExtraction
from jude.adapters.pdf import PdfExtraction
from jude.context import fill_missing_context
from jude.detect import DetectionPipeline
from jude.llm import AnthropicClient
from jude.paths import default_db_path
from jude.redact import redact
from jude.rehydrate import rehydrate
from jude.store import Store
from jude.types import Mode

st.set_page_config(page_title="Jude", layout="wide")


def _store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store(default_db_path())
    return st.session_state.store


def _selected_matter():
    store = _store()
    matters = store.list_matters()
    if not matters:
        return None
    options = {f"{m.name} ({m.mode.value})": m.id for m in matters}
    label = st.sidebar.selectbox("Matter", list(options.keys()))
    return store.get_matter(options[label])


def sidebar() -> None:
    st.sidebar.title("Jude")
    st.sidebar.caption("Local-first anonymization for legal LLM use.")

    store = _store()

    with st.sidebar.expander("Create matter", expanded=not store.list_matters()):
        new_name = st.text_input("Matter name", key="new_matter_name")
        new_mode_label = st.radio(
            "Mode",
            options=["strict", "smart"],
            help=(
                "Strict: pseudonyms only. "
                "Smart: pseudonyms + public-knowledge tags; requires zero-retention LLM."
            ),
            horizontal=True,
            key="new_matter_mode",
        )
        zr = st.checkbox(
            "I attest the LLM endpoint is zero-retention",
            key="new_matter_zr",
            disabled=(new_mode_label == "strict"),
        )
        if st.button("Create matter", disabled=not new_name):
            try:
                store.create_matter(
                    name=new_name,
                    mode=Mode(new_mode_label),
                    zero_retention_attested=zr,
                )
                st.success(f"Created matter “{new_name}”")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def main() -> None:
    sidebar()
    matter = _selected_matter()
    if matter is None:
        st.info("Create a matter in the sidebar to begin.")
        return

    st.title(matter.name)
    st.caption(
        f"Mode: **{matter.mode.value}** · Zero-retention attested: "
        f"**{'yes' if matter.zero_retention_attested else 'no'}** · "
        f"id `{matter.id}`"
    )

    tab_input, tab_review, tab_llm, tab_entities = st.tabs(
        ["Input", "Review redaction", "Send to LLM", "Entities"]
    )

    with tab_input:
        _tab_input(matter)
    with tab_review:
        _tab_review(matter)
    with tab_llm:
        _tab_llm(matter)
    with tab_entities:
        _tab_entities(matter)


def _tab_input(matter) -> None:
    st.subheader("Step 1 — Input text")
    st.caption(
        "Paste text, or upload a .txt / .docx file. The text never leaves your "
        "machine in this step."
    )

    user_context = st.text_area(
        "Optional matter context (sent to the LLM along with the redacted text)",
        key="user_context",
        height=100,
        help=(
            "Background facts about the matter that you want the LLM to know. "
            "Do NOT include client identifiers here unless you have decided this "
            "context is acceptable to share."
        ),
    )
    st.session_state.user_context = user_context

    paste = st.text_area("Paste text", height=300, key="paste_text")
    upload = st.file_uploader("…or upload a file", type=["txt", "docx", "pdf"])

    if st.button("Detect & redact", type="primary"):
        text, extraction = _load_input(paste, upload)
        if not text.strip():
            st.warning("No text provided.")
            return
        if extraction is not None:
            for w in extraction.warnings:
                st.warning(w)
        pipeline = DetectionPipeline(store=_store(), matter_id=matter.id)
        detections = pipeline.detect(text)
        result = redact(text, detections, _store(), matter.id, matter.mode)
        st.session_state.original_text = text
        st.session_state.redacted_text = result.redacted_text
        st.session_state.extraction = extraction
        st.session_state.last_n_entities = len(result.entities_used)
        st.success(
            f"Detected and redacted {len(result.entities_used)} entities "
            f"({len(detections)} spans)."
        )


def _load_input(
    paste: str, upload
) -> tuple[str, DocxExtraction | PdfExtraction | None]:
    if upload is not None:
        name = upload.name.lower()
        tmp = Path("/tmp") / f"jude_{upload.name}"
        if name.endswith(".docx"):
            tmp.write_bytes(upload.read())
            extraction = DocxAdapter.read(tmp)
            return extraction.text, extraction
        if name.endswith(".pdf"):
            tmp.write_bytes(upload.read())
            extraction_pdf = PdfAdapter.read(tmp)
            return extraction_pdf.text, extraction_pdf
        return upload.read().decode("utf-8"), None
    return paste, None


def _tab_review(matter) -> None:
    st.subheader("Step 2 — Review the redaction before sending")
    if "redacted_text" not in st.session_state:
        st.info("Run detection on the Input tab first.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Original** (stays on your machine)")
        st.text_area(
            "original",
            st.session_state.original_text,
            height=500,
            label_visibility="collapsed",
            key="orig_view",
        )
    with col2:
        st.markdown("**Redacted** (this is what the LLM will see)")
        st.text_area(
            "redacted",
            st.session_state.redacted_text,
            height=500,
            label_visibility="collapsed",
            key="redacted_view",
        )
    st.caption(
        "**You** are the last filter. Read the redacted text. If you see anything "
        "that could re-identify a party, fix it on the Entities tab or rephrase."
    )


def _tab_llm(matter) -> None:
    st.subheader("Step 3 — Send to LLM")
    if "redacted_text" not in st.session_state:
        st.info("Run detection on the Input tab first.")
        return

    if matter.mode == Mode.SMART and not matter.zero_retention_attested:
        st.error(
            "This matter is in smart mode but no zero-retention attestation is on file. "
            "Edit the matter in the sidebar."
        )
        return

    instruction = st.text_area(
        "Question / instruction for the LLM",
        height=150,
        key="llm_instruction",
        placeholder="e.g. Identify the strongest counter-arguments to the position taken in §3.",
    )

    if st.button("Send", type="primary", disabled=not instruction.strip()):
        client = AnthropicClient()
        user_msg = (
            (st.session_state.get("user_context") or "")
            + "\n\n---\nDOCUMENT (anonymized):\n\n"
            + st.session_state.redacted_text
            + "\n\n---\nQUESTION:\n\n"
            + instruction
        )
        try:
            response = client.complete(
                system="",
                user_message=user_msg,
                mode=matter.mode,
                zero_retention_attested=matter.zero_retention_attested,
            )
        except Exception as e:
            st.error(f"LLM call failed: {e}")
            return
        st.session_state.llm_response_raw = response.text
        st.session_state.llm_response_rehydrated = rehydrate(
            response.text, _store(), matter.id
        )

    if "llm_response_rehydrated" in st.session_state:
        st.markdown("**Response (rehydrated for you)**")
        st.markdown(st.session_state.llm_response_rehydrated)
        with st.expander("Raw LLM response (with pseudonyms)"):
            st.text(st.session_state.llm_response_raw)


def _tab_entities(matter) -> None:
    st.subheader("Per-matter entity dictionary")
    st.caption(
        "These mappings live only on your machine. Edit `public context` to enable "
        "smart-mode tagging — only fill it with publicly known facts about the entity. "
        "Use the merge dropdown when the same real entity was detected under several "
        "surface forms (e.g. *Amazon* and *Amazon.com Inc.*)."
    )
    store = _store()
    ents = store.list_entities(matter.id)
    if not ents:
        st.info("No entities yet. Run a redaction first.")
        return

    if st.button(
        "Auto-fill missing public context (bundled known entities)",
        help=(
            "Looks up each entity in Jude's bundled dataset of well-known public "
            "entities (DMA gatekeepers, EU institutions, NCAs). Only fills entities "
            "that don't already have a public context. No network call."
        ),
    ):
        n = fill_missing_context(store, matter.id)
        st.success(f"Filled public context for {n} entities.")
        st.rerun()

    by_id = {e.id: e for e in ents}

    for e in ents:
        with st.container(border=True):
            cols = st.columns([1.4, 1.8, 2.5, 3, 2])
            cols[0].markdown(f"**{e.pseudonym}**  \n_{e.entity_type.value}_")
            cols[1].markdown(f"{e.canonical}")
            cols[2].markdown(", ".join(sorted(e.surface_forms)) or "—")
            new_ctx = cols[3].text_input(
                "public context",
                value=e.public_context or "",
                key=f"ctx_{e.id}",
                label_visibility="collapsed",
                placeholder="public-knowledge tag (smart mode only)",
            )
            if new_ctx != (e.public_context or ""):
                store.set_public_context(e.id, new_ctx or None)

            same_type = [
                o for o in ents if o.id != e.id and o.entity_type == e.entity_type
            ]
            if same_type:
                opts = ["— merge into —"] + [
                    f"{o.pseudonym} ({o.canonical})" for o in same_type
                ]
                pick = cols[4].selectbox(
                    "merge",
                    options=opts,
                    key=f"merge_{e.id}",
                    label_visibility="collapsed",
                )
                if pick != opts[0]:
                    target_idx = opts.index(pick) - 1
                    target = same_type[target_idx]
                    if cols[4].button("Confirm merge", key=f"merge_btn_{e.id}"):
                        try:
                            store.merge_entities(matter.id, target.id, e.id)
                            st.success(
                                f"Merged {e.pseudonym} ({e.canonical}) into "
                                f"{target.pseudonym} ({target.canonical})."
                            )
                            st.rerun()
                        except ValueError as err:
                            st.error(str(err))


main()
