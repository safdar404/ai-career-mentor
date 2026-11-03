"""AI Career Mentor: Streamlit entry point.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from mentor import db
from mentor.config import get_logger, settings
from mentor.orchestrator import JOB_ROLES
from mentor.ui import components
from mentor.ui.pages import (academy, coding, dashboard, english, gaps, interview, projects, reports, roadmap,
                             settings_page)
from mentor.ui.theme import CSS

log = get_logger("app")

st.set_page_config(page_title="AI Career Mentor", page_icon="🎙️", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def _init() -> bool:
    db.init_db()
    return True


try:
    _init()
except Exception:  # noqa: BLE001
    log.exception("Database initialisation failed")
    st.error("Could not open the database. Check DATABASE_URL in your .env file.")
    st.stop()

PAGES = {
    "Dashboard": dashboard.render,
    "Live AI Interview": interview.render_live,
    "English Communication Lab": english.render,
    "Technical Assessment": interview.render_assessment,
    "Python Coding Lab": coding.render,
    "Generative AI Academy": lambda u, o: academy.render(u, o, "genai"),
    "Agentic AI Academy": lambda u, o: academy.render(u, o, "agentic"),
    "Project Presentation Trainer": projects.render,
    "HR Interview Simulator": interview.render_hr,
    "Weakness & Gap Analysis": gaps.render,
    "Learning Roadmap": roadmap.render,
    "Performance Reports": reports.render,
    "Settings": settings_page.render,
}


def onboarding() -> None:
    components.page_header("AI CAREER MENTOR",
                           "Your Personal AI Interviewer, Communication Coach & Career Development Partner.")
    users = db.list_users()
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Create your profile")
        with st.form("onboard"):
            name = st.text_input("Your name", value="" if users else "Muhammad Safdar", max_chars=120)
            role = st.selectbox("Target role", JOB_ROLES, index=1)
            background = st.text_area(
                "Your background", height=110, max_chars=3000,
                placeholder="e.g. GIS professional, completed AI Full Stack Development training, built Streamlit "
                            "and RAG projects. Interviewers use this as context.")
            go = st.form_submit_button("Start training", type="primary")
        if go:
            try:
                u = db.get_or_create_user(name, role, background.strip())
                st.session_state["user_id"] = u.id
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
    with right:
        if users:
            st.markdown("#### Continue as")
            for u in users:
                if st.button(u.name, key=f"user-{u.id}", width="stretch"):
                    st.session_state["user_id"] = u.id
                    st.rerun()
        st.markdown("#### What happens here")
        st.markdown("Every answer is scored on ten categories by separate technical and English coaches. "
                    "Weaknesses are recorded, repeated ones become priorities, and your roadmap adapts to them.")
        if not settings.any_llm:
            st.warning("No AI key configured yet. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env to enable coaching.")


def main() -> None:
    uid = st.session_state.get("user_id")
    user = db.get_user(uid) if uid else None
    if user is None:
        st.session_state.pop("user_id", None)
        onboarding()
        return

    with st.sidebar:
        st.markdown('<div class="am-brand">AI CAREER MENTOR<span>Your Personal AI Interviewer, Communication '
                    'Coach & Career Development Partner.</span></div>', unsafe_allow_html=True)
        st.markdown("")
        page = st.radio("Navigate", list(PAGES), key="nav", label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"Signed in as **{user.name}**  \nTarget: {user.target_role}")
        if not settings.any_llm:
            st.caption("AI coaching is off: no API key configured.")
        if st.button("Switch user"):
            st.session_state.clear()
            st.rerun()

    PAGES[page](user, lambda: components.get_orchestrator(user.id))


main()
