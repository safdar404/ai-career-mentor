import json

import streamlit as st

import db
import keys
from config import key_source, settings
from llm import available_providers
from orchestrator import JOB_ROLES
from components import ACCENTS, STYLES, page_header, prefs

PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "openai": "OpenAI"}


def render(user, orch_getter) -> None:
    page_header("⚙️ Settings", "Profile, AI provider, voice, and your data.")
    p = prefs(user.id)

    st.markdown("#### 👤 Profile")
    with st.form("profile"):
        role = st.selectbox("Target role", JOB_ROLES,
                            index=JOB_ROLES.index(user.target_role) if user.target_role in JOB_ROLES else 1)
        background = st.text_area("Your background (the interviewers use this as context)", value=user.background,
                                  height=120, max_chars=3000,
                                  placeholder="e.g. 5 years in GIS analysis, completed AI Full Stack training, built a RAG app...")
        if st.form_submit_button("💾 Save profile", type="primary"):
            db.update_user(user.id, target_role=role, background=background.strip())
            st.success("Profile saved.")
            st.rerun()

    st.markdown("#### 🔑 AI provider and API keys")
    avail = available_providers()
    st.markdown(keys.status_line() + f"  \n🧠 Models: Claude `{settings.anthropic_model}`, OpenAI `{settings.openai_model}`")
    with st.container(border=True):
        keys.key_form("settings")
        st.caption("🛡️ Keys you paste here live only in this browser session's memory and are never saved.")
        if key_source("anthropic") == "session" or key_source("openai") == "session":
            if st.button("🧹 Forget my keys", key="settings-forget"):
                keys.forget_keys()
                st.rerun()
    if avail:
        current = p["provider"] if p["provider"] in avail else avail[0]
        choice = st.radio("Use for coaching", avail, index=avail.index(current), format_func=PROVIDER_LABELS.get,
                          horizontal=True)
        if choice != p["provider"]:
            db.set_setting(user.id, "provider", choice)
            for k in [k for k in st.session_state if str(k).startswith("orch::")]:
                del st.session_state[k]
            st.rerun()
    else:
        st.warning("No API key yet. Paste one above to switch on AI coaching.")

    st.markdown("#### 🔊 Voice and interviewer")
    with st.form("voice"):
        c1, c2 = st.columns(2)
        accent = c1.selectbox("Default English variety", ACCENTS,
                              index=ACCENTS.index(p["accent"]) if p["accent"] in ACCENTS else 0)
        style = c2.selectbox("Default interviewer style", STYLES, index=STYLES.index(p["style"]) if p["style"] in STYLES else 1)
        tts_opts = ["browser", "openai", "off"]
        tts = st.radio("Spoken interviewer", tts_opts, index=tts_opts.index(p["tts"]) if p["tts"] in tts_opts else 0,
                       format_func={"browser": "🌐 Browser voice (free, follows the accent if your device has it)",
                                    "openai": "🟢 OpenAI voice (needs an OpenAI key, no accent choice)",
                                    "off": "🔇 Off"}.get)
        autoplay = st.checkbox("Read each question aloud automatically", value=p["autoplay"] == "true")
        emo = st.checkbox("💛 Confidence coach: read how I sound and feel after each answer, and coach me",
                          value=p["emotion_coach"] != "false")
        urdu = st.checkbox("Allow short Roman Urdu summaries when teaching a concept I could not answer",
                           value=p["urdu_support"] == "true")
        if st.form_submit_button("💾 Save voice settings", type="primary"):
            for k, v in {"accent": accent, "style": style, "tts": tts, "autoplay": str(autoplay).lower(),
                         "urdu_support": str(urdu).lower(), "emotion_coach": str(emo).lower()}.items():
                db.set_setting(user.id, k, v)
            st.success("Saved.")
    st.caption("🎙️ Voice/video call mode uses free browser voice typing (Chrome or Edge). Whisper recording needs an "
               "OpenAI key. Transcription gives text only, so pronunciation and speaking speed are not measured.")

    st.markdown("#### 🔒 Profile PIN")
    with st.form("pin-form"):
        st.caption("🔐 Protected" if db.has_pin(user.id) else "🔓 Not protected: anyone with this app link can open your profile.")
        new_pin = st.text_input("New PIN (4-8 digits, leave empty to remove)", type="password", max_chars=8)
        if st.form_submit_button("💾 Save PIN"):
            try:
                db.set_pin(user.id, new_pin)
                st.success("PIN saved." if new_pin else "PIN removed.")
            except ValueError as exc:
                st.warning(str(exc))

    st.markdown("#### 💾 Your data")
    data = db.export_user_data(user.id)
    st.download_button("⬇️ Export all my data (JSON)", data=json.dumps(data, indent=2, default=str),
                       file_name=f"ai-career-mentor-{user.name.replace(' ', '_')}.json", mime="application/json")
    with st.expander("🗑️ Delete all my data"):
        st.markdown("This permanently deletes your profile, sessions, scores, weaknesses, roadmap and reports.")
        confirm = st.text_input("Type DELETE to confirm")
        if st.button("Delete everything", disabled=confirm != "DELETE"):
            db.delete_user_data(user.id)
            st.session_state.clear()
            st.rerun()
