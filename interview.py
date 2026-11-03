import streamlit as st

import db
from wellbeing import checkin
from orchestrator import CATEGORIES, DIFFICULTIES, JOB_ROLES
from topics import GROUP_LABELS, TOPIC_GROUPS
from components import (ACCENTS, STYLES, conversation_mode, interview_runner, page_header, prefs, run_safely,
                        runner_active, start_runner, topic_label)

DURATIONS = {"10 minutes (4 questions)": 4, "20 minutes (7 questions)": 7, "30 minutes (10 questions)": 10,
             "45 minutes (15 questions)": 15}


def _role_index(user) -> int:
    return JOB_ROLES.index(user.target_role) if user.target_role in JOB_ROLES else 1


def render_live(user, orch_getter) -> None:
    page_header("🎤 Live AI Interview",
                "A realistic interview: one question at a time, follow-ups on weak answers, and a full scorecard "
                "after every response.")
    prefix = "live"
    orch = orch_getter()
    if orch is None:
        return
    if not runner_active(prefix):
        st.markdown("##### How do you want to talk?")
        conversation_mode(prefix, user.id)
        with st.expander("💛 Quick check-in: how are you feeling before we start?"):
            checkin(user.id, f"{prefix}-pre")
        p = prefs(user.id)
        projects = db.list_projects(user.id)
        with st.form("live-setup"):
            c1, c2 = st.columns(2)
            role = c1.selectbox("Job position", JOB_ROLES, index=_role_index(user))
            category = c2.selectbox("Interview category", CATEGORIES)
            c1, c2 = st.columns(2)
            difficulty = c1.selectbox("Difficulty", DIFFICULTIES)
            duration = c2.selectbox("Duration", list(DURATIONS), index=1)
            c1, c2 = st.columns(2)
            region = c1.selectbox("Company location / English variety", ACCENTS,
                                  index=ACCENTS.index(p["accent"]) if p["accent"] in ACCENTS else 0)
            style = c2.selectbox("Interviewer style", STYLES, index=STYLES.index(p["style"]) if p["style"] in STYLES else 1)
            project_title = None
            if projects:
                project_title = st.selectbox("Project to discuss (used for Project Discussion)",
                                             ["None"] + [x.title for x in projects])
            start = st.form_submit_button("🚀 Start interview", type="primary")
        if start:
            project = None
            if category == "Project Discussion":
                chosen = next((x for x in projects if x.title == project_title), None)
                if chosen is None:
                    st.warning("Add a project in the Project Presentation Trainer first, then choose it here.")
                    return
                project = {k: getattr(chosen, k) for k in ("title", "description", "technologies", "architecture",
                                                           "challenges", "results")}
            out = run_safely("The interviewer is preparing your first question...",
                             lambda: orch.start_session(user.id, "interview", role, difficulty, category,
                                                        DURATIONS[duration], region, style, project=project))
            if out:
                start_runner(prefix, *out)
                st.rerun()
        st.caption("Difficulty adapts during the interview: two strong answers move it up, two weak answers move it down.")
        return
    interview_runner(prefix, user.id, orch)


def render_assessment(user, orch_getter) -> None:
    page_header("🧪 Technical Assessment",
                "Test what you actually understand, area by area. Questions are generated for your level and "
                "every answer updates your topic scores.")
    prefix = "assess"
    orch = orch_getter()
    if orch is None:
        return
    if not runner_active(prefix):
        with st.form("assess-setup"):
            groups = [g for g in TOPIC_GROUPS if g not in {"communication", "professional"}]
            area = st.selectbox("Area", groups, format_func=lambda g: GROUP_LABELS[g])
            topics = st.multiselect("Specific topics (optional)", list(TOPIC_GROUPS[area]), format_func=topic_label,
                                    help="Leave empty to cover the whole area.")
            c1, c2 = st.columns(2)
            difficulty = c1.selectbox("Difficulty", DIFFICULTIES)
            n = c2.slider("Number of questions", 3, 15, 5)
            start = st.form_submit_button("🚀 Start assessment", type="primary")
        if start:
            focus = topics or list(TOPIC_GROUPS[area])
            out = run_safely("Generating your first question...",
                             lambda: orch.start_session(user.id, "assessment", user.target_role, difficulty, "Technical",
                                                        n, prefs(user.id)["accent"], "Neutral", focus_topics=focus))
            if out:
                start_runner(prefix, *out)
                st.rerun()
        st.caption("The checklist also covers Git, SQL, testing and security, which many junior candidates are "
                   "asked about. Choose 'Engineering practice' to test them.")
        return
    interview_runner(prefix, user.id, orch)


def render_hr(user, orch_getter) -> None:
    page_header("🤝 HR Interview Simulator",
                "Recruiter and hiring-manager questions, coached with the STAR method. Improved answers use "
                "placeholders for your real details and never invent achievements.")
    prefix = "hr"
    orch = orch_getter()
    if orch is None:
        return
    if not runner_active(prefix):
        st.markdown("##### How do you want to talk?")
        conversation_mode(prefix, user.id)
        with st.expander("💛 Quick check-in: how are you feeling before we start?"):
            checkin(user.id, f"{prefix}-pre")
        p = prefs(user.id)
        with st.form("hr-setup"):
            c1, c2 = st.columns(2)
            role = c1.selectbox("Job position", JOB_ROLES, index=_role_index(user))
            region = c2.selectbox("Company location", ACCENTS,
                                  index=ACCENTS.index(p["accent"]) if p["accent"] in ACCENTS else 0)
            c1, c2 = st.columns(2)
            style = c1.selectbox("Interviewer style", STYLES, index=1)
            n = c2.slider("Number of questions", 3, 12, 6)
            start = st.form_submit_button("🚀 Start HR interview", type="primary")
        if start:
            out = run_safely("The recruiter is joining...",
                             lambda: orch.start_session(user.id, "hr", role, "Intermediate", "Behavioral", n, region, style))
            if out:
                start_runner(prefix, *out)
                st.rerun()
        with st.expander("What is the STAR method?"):
            st.markdown("**Situation**: the context, briefly.  \n**Task**: what you were responsible for.  \n"
                        "**Action**: what *you* did, step by step. This should be the longest part.  \n"
                        "**Result**: the outcome, with a number if you have one, and what you learned.")
        return
    interview_runner(prefix, user.id, orch)
