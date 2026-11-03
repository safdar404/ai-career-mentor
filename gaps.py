import streamlit as st

import db
from topics import TOPIC_GROUPS
from components import (chips, esc, interview_runner, page_header, prefs, run_safely, runner_active, start_runner,
                          topic_label)

CATEGORY_TITLES = {"technical": "Technical gaps", "communication": "Communication gaps",
                   "professional": "Professional gaps"}


def render(user, orch_getter) -> None:
    page_header("🎯 Weakness & Gap Analysis",
                "Every weakness found in your answers, grouped and ranked. A weakness seen twice becomes a priority.")

    prefix = "rev"
    if runner_active(prefix):
        orch = orch_getter()
        if orch:
            st.markdown("### Revision session")
            interview_runner(prefix, user.id, orch)
        return

    gaps = db.list_gaps(user.id)
    priority = [g for g in gaps if g.priority]
    c1, c2, c3 = st.columns(3)
    c1.metric("Open weaknesses", len(gaps))
    c2.metric("Priorities", len(priority))
    c3.metric("Resolved", len(db.list_gaps(user.id, status="resolved")))

    if priority:
        st.markdown("### Revision")
        st.markdown("Practise your priority weaknesses with fresh questions.")
        n = st.slider("Questions", 3, 10, 5, key="rev-n")
        if st.button("🔁 Start revision session", type="primary"):
            orch = orch_getter()
            if orch:
                topics = orch.revision_topics(user.id)
                out = run_safely("Building your revision session...", lambda: orch.start_session(
                    user.id, "revision", user.target_role, "Intermediate", "Revision", n,
                    prefs(user.id)["accent"], "Neutral", focus_topics=topics))
                if out:
                    start_runner(prefix, *out)
                    st.rerun()

    if not gaps:
        st.info("No weaknesses recorded yet. They are extracted automatically from every answer you submit.")
    tabs = st.tabs([f"{CATEGORY_TITLES[c]} ({sum(1 for g in gaps if g.category == c)})" for c in CATEGORY_TITLES])
    for tab, cat in zip(tabs, CATEGORY_TITLES):
        with tab:
            rows = [g for g in gaps if g.category == cat]
            if not rows:
                st.caption("Nothing recorded in this category.")
            for g in rows:
                with st.container(border=True):
                    chips((topic_label(g.topic), "volt"), (f"Seen {g.occurrences}x", ""),
                          (["", "Minor", "Moderate", "Serious"][g.severity], "violet"),
                          ("Priority" if g.priority else "", "warn"))
                    st.markdown(esc(g.description))
                    if g.recommended_exercise:
                        st.caption(f"Exercise: {g.recommended_exercise}")
                    if g.examples:
                        with st.expander("Evidence from your answers"):
                            st.markdown("\n".join(f"- {esc(e)}" for e in g.examples))
                    if st.button("✅ Mark as resolved", key=f"res-{g.id}"):
                        db.set_gap_status(g.id, user.id, "resolved")
                        st.rerun()
            st.caption("A resolved weakness reopens automatically if it appears again.")

    assessed = {s.topic for s in db.technical_skills(user.id)}
    missing = [t for t in TOPIC_GROUPS["industry"] | TOPIC_GROUPS["deployment"] if t not in assessed]
    if missing:
        st.markdown("### Not assessed yet")
        st.markdown("Industry topics that international interviewers often ask about, with no answers from you yet:")
        chips(*[(topic_label(t), "") for t in missing])
        st.caption("Test them in Technical Assessment under 'Engineering practice' or 'Docker & deployment'.")
