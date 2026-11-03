"""AI Career Mentor: Streamlit entry point.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import db
from config import get_logger
from orchestrator import JOB_ROLES
import components
import keys
import academy, coding, dashboard, english, gaps, history, interview, projects, reports, roadmap, settings_page, wellbeing
from avatar import brand_html
from robot3d import robot
from theme import CSS

log = get_logger("app")

st.set_page_config(page_title="AI Career Mentor", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")
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
    "📊 Dashboard": dashboard.render,
    "🎤 Live AI Interview": interview.render_live,
    "💛 Confidence Coach": wellbeing.render,
    "🗣️ English Communication Lab": english.render,
    "🧪 Technical Assessment": interview.render_assessment,
    "🐍 Python Coding Lab": coding.render,
    "🤖 Generative AI Academy": lambda u, o: academy.render(u, o, "genai"),
    "🕸️ Agentic AI Academy": lambda u, o: academy.render(u, o, "agentic"),
    "📽️ Project Presentation Trainer": projects.render,
    "🤝 HR Interview Simulator": interview.render_hr,
    "🎯 Weakness & Gap Analysis": gaps.render,
    "🗺️ Learning Roadmap": roadmap.render,
    "📈 Performance Reports": reports.render,
    "🗂️ Conversation History": history.render,
    "⚙️ Settings": settings_page.render,
}


def _sign_in(user_id: int) -> None:
    st.session_state["user_id"] = user_id
    st.rerun()


def onboarding() -> None:
    with st.container(key="hero"):
        c1, c2 = st.columns([2, 3], vertical_alignment="center")
        with c1:
            robot("hero-bot", height=300, wave=True, bust=True)
        with c2:
            st.markdown('<div class="am-hero-text"><span class="am-kicker">🤖 AI agent · online</span>'
                        '<h1>AI Career Mentor</h1><p>Your personal AI interviewer, communication coach and career '
                        'development partner. Practise by 💬 chat, 🎙️ voice call or 🎥 video call with a live 3D '
                        'AI agent that listens, speaks and coaches you.</p></div>', unsafe_allow_html=True)
    users = db.list_users()
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("#### ✨ Create your profile")
        with st.form("onboard"):
            name = st.text_input("Your name", max_chars=120, placeholder="e.g. Muhammad Safdar")
            role = st.selectbox("🎯 Target role", JOB_ROLES, index=1)
            background = st.text_area(
                "🧾 Your background", height=110, max_chars=3000,
                placeholder="e.g. GIS professional, completed AI Full Stack Development training, built Streamlit "
                            "and RAG projects. Interviewers use this as context.")
            pin = st.text_input("🔒 Profile PIN (optional, 4-8 digits)", type="password", max_chars=8,
                                help="Others using this app link can't open your profile and history without it.")
            go = st.form_submit_button("🚀 Start training", type="primary")
        if go:
            try:
                if not name.strip():
                    raise ValueError("Please enter your name.")
                if pin and not (pin.isdigit() and 4 <= len(pin) <= 8):
                    raise ValueError("The PIN must be 4 to 8 digits.")
                u = db.get_or_create_user(name, role, background.strip())
                if db.has_pin(u.id) and not db.check_pin(u.id, pin):
                    raise ValueError("A profile with this name already exists and is PIN-protected. Use "
                                     "'Continue as' with its PIN, or pick another name.")
                if pin and not db.has_pin(u.id):
                    db.set_pin(u.id, pin)
                _sign_in(u.id)
            except ValueError as exc:
                st.warning(str(exc))
    with right:
        if users:
            st.markdown("#### 👤 Continue as")
            for u in users:
                locked = db.has_pin(u.id)
                if not locked:
                    if st.button(f"👤 {u.name}", key=f"user-{u.id}", width="stretch"):
                        _sign_in(u.id)
                    continue
                with st.popover(f"🔒 {u.name}", width="stretch"):
                    with st.form(f"pin-{u.id}", border=False):
                        entered = st.text_input("PIN", type="password", max_chars=8, key=f"pin-in-{u.id}")
                        if st.form_submit_button("Unlock", type="primary"):
                            if db.check_pin(u.id, entered):
                                _sign_in(u.id)
                            else:
                                st.error("Wrong PIN.")
        st.markdown("#### 🧭 What happens here")
        st.markdown("- 🧑‍⚖️ Every answer is scored on **ten categories** by separate technical and English coaches\n"
                    "- 💛 A confidence coach reads how you sound and helps with nerves and fear of speaking\n"
                    "- 🎯 Weaknesses are recorded; repeated ones become priorities\n"
                    "- 🗺️ Your roadmap adapts to your real results\n"
                    "- 🗂️ Every conversation is saved so you can review it later")
        if not keys.any_key():
            st.info("🔑 After you create your profile, paste a Claude or OpenAI API key in the sidebar to switch on "
                    "AI coaching. Keys stay in your browser session only.")


def main() -> None:
    uid = st.session_state.get("user_id")
    user = db.get_user(uid) if uid else None
    if user is None:
        st.session_state.pop("user_id", None)
        onboarding()
        return

    with st.sidebar:
        st.markdown(brand_html(), unsafe_allow_html=True)
        page = st.radio("Navigate", list(PAGES), key="nav", label_visibility="collapsed")
        st.markdown("---")
        keys.sidebar_panel()
        st.caption(f"👤 **{user.name}**  \n🎯 {user.target_role}")
        if st.button("🔄 Switch user", width="stretch"):
            st.session_state.clear()
            st.rerun()

    PAGES[page](user, lambda: components.get_orchestrator(user.id))


main()
