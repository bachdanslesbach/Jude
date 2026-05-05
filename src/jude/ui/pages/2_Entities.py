"""Entity-management page: per-matter dictionary review and merge."""

from __future__ import annotations

import streamlit as st

from jude.context import fill_missing_context
from jude.paths import default_db_path
from jude.risk import RiskLevel, assess_risks
from jude.store import Store
from jude.types import Mode

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

    col_a, col_b = st.columns([2, 3])
    with col_a:
        if st.button("Auto-fill missing public context (bundled known entities)"):
            n = fill_missing_context(store, matter.id)
            st.success(f"Filled public context for {n} entities.")
            st.rerun()

    ents = store.list_entities(matter.id)
    if not ents:
        st.info("No entities yet for this matter. Run a chat turn first.")
        return

    risk_by_id: dict[int, "object"] = {}
    with col_b:
        st.caption(
            "**Re-identification risk** — paste any redacted text below to "
            "score how identifiable each entity remains given the surrounding "
            "specific markers (currency figures, dates, case refs) and the "
            "public-knowledge tag."
        )
        sample = st.text_area(
            "Redacted text to assess",
            key=f"risk_input_{matter.id}",
            height=140,
            placeholder="(paste a recent chat turn's redacted form here)",
        )
        if st.button("Assess risk", key=f"risk_btn_{matter.id}"):
            assessments = assess_risks(sample or "", ents, matter.mode)
            risk_by_id = {a.entity_id: a for a in assessments}
            st.session_state[f"risk_{matter.id}"] = risk_by_id
        risk_by_id = st.session_state.get(f"risk_{matter.id}", risk_by_id)

    st.divider()

    for e in ents:
        with st.container(border=True):
            cols = st.columns([1.2, 1.8, 2.5, 3, 2])
            label = f"**{e.pseudonym}**  \n_{e.entity_type.value}_"
            risk = risk_by_id.get(e.id)
            if risk is not None:
                badge = {
                    RiskLevel.HIGH: ":red[HIGH]",
                    RiskLevel.MEDIUM: ":orange[MEDIUM]",
                    RiskLevel.LOW: ":green[low]",
                }[risk.level]
                label += f"  \n{badge} ({risk.score})"
            cols[0].markdown(label)
            if risk is not None and risk.reasons:
                with cols[0].expander("why?"):
                    for reason in risk.reasons:
                        st.write(f"• {reason}")
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
