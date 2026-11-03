import streamlit as st

from orchestrator import DIFFICULTIES
from topics import TOPIC_GROUPS
from components import (interview_runner, lesson_view, page_header, prefs, run_safely, runner_active, start_runner,
                          topic_label)

ACADEMIES = {
    "genai": ("🤖 Generative AI Academy",
              "Learn one concept at a time: a simple explanation, an analogy, an example. Then explain it back in "
              "your own words and get scored."),
    "agentic": ("🕸️ Agentic AI Academy",
                "Agents, tool calling, memory, orchestration and safety, taught simply and then checked with "
                "explain-it-back questions."),
}


def render(user, orch_getter, group: str) -> None:
    title, sub = ACADEMIES[group]
    page_header(title, sub)
    orch = orch_getter()
    if orch is None:
        return
    prefix = f"acad-{group}"
    if not runner_active(prefix):
        p = prefs(user.id)
        with st.form(f"{prefix}-setup"):
            topic = st.selectbox("Concept", list(TOPIC_GROUPS[group]), format_func=topic_label)
            c1, c2 = st.columns(2)
            level = c1.selectbox("Level", DIFFICULTIES[:3])
            urdu = c2.checkbox("Add a short Roman Urdu summary", value=p["urdu_support"] == "true",
                               help="Use only when a concept is hard to follow. The goal is English-only.")
            go = st.form_submit_button("📚 Teach me", type="primary")
        if go:
            out = run_safely("Your mentor is preparing the lesson...",
                             lambda: orch.start_lesson(user.id, topic, level, urdu))
            if out:
                sid, q = out
                start_runner(prefix, sid, q)
                st.session_state[f"{prefix}_lesson"] = q["lesson"]
                st.rerun()
        return

    lesson = st.session_state.get(f"{prefix}_lesson")
    if lesson:
        with st.expander("Lesson", expanded=not st.session_state.get(f"{prefix}_res")):
            lesson_view(lesson, user.id, key=prefix)
    st.markdown("### Explain it back")
    st.caption("Answer in your own words, as if explaining to a colleague. Don't copy the lesson.")
    interview_runner(prefix, user.id, orch)
