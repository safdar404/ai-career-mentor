"""🗂️ Conversation history: every saved conversation, searchable, replayable and downloadable."""
from __future__ import annotations

import datetime as dt
import json

import streamlit as st

import db
from avatar import bubble
from components import page_header

MODULES = {
    "": "🗂️ All conversations", "interview": "🎤 Live interviews", "hr": "🤝 HR interviews",
    "assessment": "🧪 Technical assessments", "english": "🗣️ English lab", "academy": "🎓 Academy lessons",
    "coding": "🐍 Coding lab", "project": "📽️ Project pitches", "revision": "🔁 Revision",
}
AGENT_NAMES = {
    "technical_interviewer": "Technical Interviewer", "english_coach": "English Coach",
    "technical_mentor": "Technical Mentor", "hr_coach": "HR & Career Coach", "gap_analyst": "Gap Analyst",
    "progress_manager": "Progress Manager", "presence_coach": "📸 Video Presence Coach", "feedback": "📊 Feedback",
}


def _local(d):
    """Stored times are UTC; show them in the viewer's browser time zone when we know it."""
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        tz = st.context.timezone
        return d.replace(tzinfo=dt.timezone.utc).astimezone(ZoneInfo(tz)) if tz else d
    except Exception:  # noqa: BLE001 - unknown zone or no browser context
        return d


def _when(d) -> str:
    d = _local(d)
    return d.strftime("%d %b %Y, %H:%M") if d else ""


def transcript_markdown(sess_row: dict, messages: list, user_name: str) -> str:
    lines = [f"# {MODULES.get(sess_row['module'], sess_row['module'])} - {sess_row.get('category') or ''}".rstrip(" -"),
             f"_{_when(sess_row['started_at'])}_", ""]
    for m in messages:
        who = user_name if m.role == "user" else AGENT_NAMES.get(m.agent, "AI Mentor")
        lines += [f"**{who}** ({_local(m.created_at):%H:%M}):", "", m.content, ""]
    return "\n".join(lines)


def render(user, orch_getter) -> None:
    page_header("🗂️ Conversation History",
                "Every interview, lesson and practice conversation is saved here. Search it, replay it, "
                "download it or delete it.")
    c1, c2 = st.columns([1, 2])
    module = c1.selectbox("Type", list(MODULES), format_func=MODULES.get, key="hist-module")
    search = c2.text_input("🔎 Search inside conversations", key="hist-search", placeholder="e.g. RAG, STAR, Docker")
    rows = db.conversation_index(user.id, module or None, search)

    if not rows:
        st.info("No saved conversations yet. Start a 🎤 Live AI Interview or 🗣️ English lab session and it "
                "will appear here automatically." if not search else "No conversations match that search.")
        return

    total_answers = sum(r["answers"] for r in rows)
    m1, m2, m3 = st.columns(3)
    m1.metric("💬 Conversations", len(rows))
    m2.metric("✍️ Your answers", total_answers)
    scored = [r["average"] for r in rows if r["average"] is not None]
    m3.metric("📈 Average session score", f"{sum(scored) / len(scored):.0f}/100" if scored else "—")

    labels = {r["id"]: (f"{MODULES.get(r['module'], r['module']).split(' ', 1)[0]} {_when(r['started_at'])} · "
                        f"{r['category'] or r['module'].title()} · {r['messages']} messages"
                        + ("" if r["status"] == "completed" else " · in progress"))
              for r in rows}
    sid = st.selectbox("Open a conversation", list(labels), format_func=labels.get, key="hist-open")
    row = next(r for r in rows if r["id"] == sid)
    msgs = db.get_messages(sid, include_meta=True)
    show_notes = st.toggle("Show coaching notes (scores and presence tips)", value=True, key="hist-notes")

    st.markdown('<div class="am-chat">' + "".join(
        bubble(m.content, user.name if m.role == "user" else AGENT_NAMES.get(m.agent, "AI Mentor"), m.role,
               meta=f'<div class="am-time">{_local(m.created_at):%d %b %H:%M}</div>')
        for m in msgs if show_notes or m.agent not in db.META_AGENTS) + "</div>", unsafe_allow_html=True)

    sess = db.get_session(sid)
    if sess and sess.summary and sess.summary.get("headline"):
        st.info(f"📝 Session summary: {sess.summary['headline']}")

    d1, d2, d3 = st.columns(3)
    md = transcript_markdown(row, msgs, user.name)
    safe = f"conversation-{sid}-{row['started_at']:%Y%m%d-%H%M}"
    d1.download_button("⬇️ Download transcript (.md)", md, file_name=f"{safe}.md", mime="text/markdown",
                       width="stretch")
    d2.download_button("⬇️ Download (.json)", json.dumps(
        {"session": {k: str(v) if k in {"started_at", "ended_at"} else v for k, v in row.items()},
         "messages": [{"role": m.role, "agent": m.agent, "content": m.content, "at": str(m.created_at)} for m in msgs]},
        indent=2), file_name=f"{safe}.json", mime="application/json", width="stretch")
    with d3.popover("🗑️ Delete", width="stretch"):
        st.caption("Deletes this conversation and its answers. Scores already added to your progress stay.")
        if st.button("Delete permanently", key=f"hist-del-{sid}", type="primary"):
            db.delete_session(sid, user.id)
            st.toast("Conversation deleted", icon="🗑️")
            st.rerun()
    st.caption("💾 Saved in the app database. On Streamlit Community Cloud the disk resets on restart, "
               "so download transcripts you want to keep, or connect PostgreSQL with DATABASE_URL.")
