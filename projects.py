import streamlit as st

import db
from orchestrator import DIFFICULTIES, PITCH_LENGTHS
from components import (ACCENTS, STYLES, interview_runner, page_header, prefs, run_safely, runner_active,
                          start_runner)

FIELDS = [("title", "Project title", "e.g. GIS land-records assistant"),
          ("description", "What problem does it solve, and for whom?", ""),
          ("technologies", "Technologies", "e.g. Python, Streamlit, OpenAI API, ChromaDB, Docker"),
          ("architecture", "Architecture: main components and how they communicate", ""),
          ("challenges", "Challenges you faced and how you solved them", ""),
          ("results", "Results: what it achieved, who used it, any numbers", "")]


def _project_dict(p) -> dict:
    return {k: getattr(p, k) for k, _, _ in FIELDS}


def render(user, orch_getter) -> None:
    page_header("Project Presentation Trainer",
                "Describe your real projects once, then practise explaining them in 30 seconds to 5 minutes and "
                "defend them against a senior interviewer.")
    tab_projects, tab_pitch, tab_grill = st.tabs(["My projects", "Pitch practice", "Tough questions"])
    projects = db.list_projects(user.id)

    with tab_projects:
        options = ["Add a new project"] + [p.title for p in projects]
        choice = st.selectbox("Project", options, key="proj-choice")
        current = next((p for p in projects if p.title == choice), None)
        with st.form("proj-form", clear_on_submit=current is None):
            vals = {}
            for k, label, ph in FIELDS:
                default = getattr(current, k) if current else ""
                if k == "title":
                    vals[k] = st.text_input(label, value=default, placeholder=ph, max_chars=200)
                else:
                    vals[k] = st.text_area(label, value=default, placeholder=ph, height=90, max_chars=4000)
            saved = st.form_submit_button("Save project", type="primary")
        if saved:
            try:
                db.save_project(user.id, current.id if current else None, **vals)
                st.success("Project saved.")
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        if current and st.button("Delete this project"):
            db.delete_project(current.id, user.id)
            st.rerun()
        st.caption("Be accurate. The interviewer checks your answers against these details, and the coach will "
                   "not invent results you did not achieve.")

    orch = None
    with tab_pitch:
        if not projects:
            st.info("Add a project first.")
        else:
            orch = orch or orch_getter()
            if orch:
                prefix = "pitch"
                if not runner_active(prefix):
                    with st.form("pitch-setup"):
                        c1, c2 = st.columns(2)
                        title = c1.selectbox("Project", [p.title for p in projects])
                        length = c2.selectbox("Length", list(PITCH_LENGTHS))
                        go = st.form_submit_button("Start pitch", type="primary")
                    if go:
                        proj = next(p for p in projects if p.title == title)
                        out = run_safely("Setting up...", lambda: orch.start_pitch(
                            user.id, _project_dict(proj), length, prefs(user.id)["accent"]))
                        if out:
                            sid, q = out
                            q.update({"topic": "pro.project_explanation", "agent": "Senior Technical Interviewer",
                                      "position": 1, "kind": "new"})
                            start_runner(prefix, sid, q)
                            st.rerun()
                    st.caption("Length is estimated from your word count at about 130 words per minute. "
                               "Record yourself for real practice.")
                else:
                    interview_runner(prefix, user.id, orch)

    with tab_grill:
        if not projects:
            st.info("Add a project first.")
        else:
            orch = orch or orch_getter()
            if orch:
                prefix = "grill"
                if not runner_active(prefix):
                    with st.form("grill-setup"):
                        c1, c2 = st.columns(2)
                        title = c1.selectbox("Project", [p.title for p in projects], key="grill-proj")
                        style = c2.selectbox("Interviewer style", STYLES, index=2)
                        c1, c2 = st.columns(2)
                        difficulty = c1.selectbox("Difficulty", DIFFICULTIES, index=1)
                        n = c2.slider("Questions", 3, 12, 6)
                        go = st.form_submit_button("Start", type="primary")
                    if go:
                        proj = next(p for p in projects if p.title == title)
                        out = run_safely("The interviewer is reading your project...", lambda: orch.start_session(
                            user.id, "project", user.target_role, difficulty, "Project Discussion", n,
                            prefs(user.id)["accent"], style, project=_project_dict(proj)))
                        if out:
                            start_runner(prefix, *out)
                            st.rerun()
                    st.caption("Expect: problem, architecture, component communication, challenges, error "
                               "handling, scaling, security, and what you would improve.")
                else:
                    interview_runner(prefix, user.id, orch)
