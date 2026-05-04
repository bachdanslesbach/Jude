"""Entity-management page: per-matter dictionary review and merge."""

from __future__ import annotations

import streamlit as st

from jude.context import fill_missing_context
from jude.paths import default_db_path
from jude.store import Store

st.set_page_config(page_title="Entities · Jude", layout="wide")


def _store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store(default_db_path())
    return st.session_state.store


def main() -> None:
    st.title("Entity dictionary")
    store = _store()

    matters = store.list_matters()
    if not matters:
        st.info("No matters yet — create one in the chat page.")
        return

    options = {f"{m.name} · {m.mode.value}": m.id for m in matters}
    label = st.selectbox("Matter", list(options.keys()))
    matter = store.get_matter(options[label])
    assert matter is not None

    st.caption(
        "These mappings live only on your machine. Edit `public context` to "
        "enable smart-mode tagging — only fill it with publicly known facts. "
        "Use **merge** when the same real entity was detected under several "
        "surface forms."
    )

    if st.button("Auto-fill missing public context (bundled known entities)"):
        n = fill_missing_context(store, matter.id)
        st.success(f"Filled public context for {n} entities.")
        st.rerun()

    ents = store.list_entities(matter.id)
    if not ents:
        st.info("No entities yet for this matter. Run a chat turn first.")
        return

    for e in ents:
        with st.container(border=True):
            cols = st.columns([1.2, 1.8, 2.5, 3, 2])
            cols[0].markdown(f"**{e.pseudonym}**  \n_{e.entity_type.value}_")
            cols[1].markdown(e.canonical)
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
                    target = same_type[opts.index(pick) - 1]
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
