import json

import streamlit as st

import db
from config import settings
from llm import available_providers
from orchestrator import JOB_ROLES
from components import ACCENTS, STYLES, page_header, prefs

PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "openai": "OpenAI"}


def render(user, orch_getter) -> None:
    page_header("Settings", "Profile, AI provider, voice, and your data.")
    p = prefs(user.id)

    st.markdown("#### Profile")
    with st.form("profile"):
        role = st.selectbox("Target role", JOB_ROLES,
                            index=JOB_ROLES.index(user.target_role) if user.target_role in JOB_ROLES else 1)
        background = st.text_area("Your background (the interviewers use this as context)", value=user.background,
                                  height=120, max_chars=3000,
                                  placeholder="e.g. 5 years in GIS analysis, completed AI Full Stack training, built a RAG app...")
        if st.form_submit_button("Save profile", type="primary"):
            db.update_user(user.id, target_role=role, background=background.strip())
            st.success("Profile saved.")
            st.rerun()

    st.markdown("#### AI provider")
    avail = available_providers()
    st.markdown(f"Claude key: {'configured' if settings.has_anthropic else 'not set'}  \n"
                f"OpenAI key: {'configured' if settings.has_openai else 'not set'}  \n"
                f"Models: Claude `{settings.anthropic_model}`, OpenAI `{settings.openai_model}` (change in `.env`)")
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
        st.warning("No API key found. Add one to your .env file and restart.")

    st.markdown("#### Voice and interviewer")
    with st.form("voice"):
        c1, c2 = st.columns(2)
        accent = c1.selectbox("Default English variety", ACCENTS,
                              index=ACCENTS.index(p["accent"]) if p["accent"] in ACCENTS else 0)
        style = c2.selectbox("Default interviewer style", STYLES, index=STYLES.index(p["style"]) if p["style"] in STYLES else 1)
        tts_opts = ["browser", "openai", "off"]
        tts = st.radio("Spoken interviewer", tts_opts, index=tts_opts.index(p["tts"]) if p["tts"] in tts_opts else 0,
                       format_func={"browser": "Browser voice (free, follows the accent if your device has it)",
                                    "openai": "OpenAI voice (needs OPENAI_API_KEY, no accent choice)",
                                    "off": "Off"}.get)
        autoplay = st.checkbox("Read each question aloud automatically", value=p["autoplay"] == "true")
        urdu = st.checkbox("Allow short Roman Urdu summaries when teaching a concept I could not answer",
                           value=p["urdu_support"] == "true")
        if st.form_submit_button("Save voice settings", type="primary"):
            for k, v in {"accent": accent, "style": style, "tts": tts, "autoplay": str(autoplay).lower(),
                         "urdu_support": str(urdu).lower()}.items():
                db.set_setting(user.id, k, v)
            st.success("Saved.")
    st.caption("Speech-to-text needs OPENAI_API_KEY. Transcription gives text only, so pronunciation and speaking "
               "speed are not measured.")

    st.markdown("#### Your data")
    data = db.export_user_data(user.id)
    st.download_button("Export all my data (JSON)", data=json.dumps(data, indent=2, default=str),
                       file_name=f"ai-career-mentor-{user.name.replace(' ', '_')}.json", mime="application/json")
    with st.expander("Delete all my data"):
        st.markdown("This permanently deletes your profile, sessions, scores, weaknesses, roadmap and reports.")
        confirm = st.text_input("Type DELETE to confirm")
        if st.button("Delete everything", disabled=confirm != "DELETE"):
            db.delete_user_data(user.id)
            st.session_state.clear()
            st.rerun()
