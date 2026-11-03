import streamlit as st

import db
from agents import SCENARIOS
from avatar import bubble
from components import (ACCENTS, answer_input, call_stage, clear_answer, conversation_mode, evaluation_view,
                        page_header, prefs, presence_view, question_block, run_pending_presence, run_safely, speak)


def _reset() -> None:
    for k in ("eng_sid", "eng_q", "eng_res", "eng_prev", "eng_presence", "eng_pending_frame"):
        st.session_state.pop(k, None)


def render(user, orch_getter) -> None:
    page_header("🗣️ English Communication Lab",
                "Role-play real workplace conversations. Each reply gets corrections, a natural professional "
                "version, and new vocabulary. Then try it again.")
    orch = orch_getter()
    if orch is None:
        return

    if not st.session_state.get("eng_sid"):
        st.markdown("##### How do you want to talk?")
        conversation_mode("eng", user.id)
        p = prefs(user.id)
        with st.form("eng-setup"):
            scenario = st.selectbox("Practice scenario", list(SCENARIOS),
                                    format_func=lambda s: f"{s}: {SCENARIOS[s]}")
            accent = st.selectbox("Conversation partner's English", ACCENTS,
                                  index=ACCENTS.index(p["accent"]) if p["accent"] in ACCENTS else 0)
            start = st.form_submit_button("🚀 Start conversation", type="primary")
        if start:
            out = run_safely("Starting the conversation...", lambda: orch.start_english(user.id, scenario, accent))
            if out:
                st.session_state["eng_sid"], st.session_state["eng_q"] = out
                st.rerun()
        st.caption("💡 Tip: answer in 2-4 full sentences. Short answers are fine in small talk, but practise extending "
                   "them with one detail.")
        return

    sid = st.session_state["eng_sid"]
    sess = db.get_session(sid)
    if sess is None or sess.user_id != user.id:
        _reset()
        st.rerun()
    q = st.session_state["eng_q"]
    res = st.session_state.get("eng_res")

    msgs = db.get_messages(sid)[:-1]  # everything before the current line
    if msgs:
        with st.expander(f"💬 Conversation so far ({len(msgs)} messages)"):
            st.markdown('<div class="am-chat">' + "".join(
                bubble(m.content, "Partner" if m.role == "assistant" else user.name, m.role) for m in msgs) + "</div>",
                unsafe_allow_html=True)

    mode = conversation_mode("eng", user.id)
    who = f"{sess.category} | {(sess.context or {}).get('region', '')}"
    if mode == "chat" or res:
        question_block(q["question"], who)
        if mode == "chat":
            speak(q["question"], user.id, key=f"eng-{q['id']}", label="Hear it")
    if q.get("tip") and not res:
        st.caption(f"💡 Coach tip: {q['tip']}")

    ans_key = f"eng-ans-{q['id']}"
    if not res:
        if mode == "chat":
            submitted = answer_input(ans_key, user.id, "Reply as you would in this conversation.")
        else:
            submitted = call_stage("eng", user.id, sid, {**q, "agent": who}, mode, orch)
            with st.expander("⌨️ Prefer to type, or record with Whisper?"):
                submitted = answer_input(ans_key, user.id, "Reply as you would in this conversation.") or submitted
        presence_view(st.session_state.get("eng_presence", {}).get(q["id"]))
        if submitted:
            out = run_safely("🗣️ Your English coach is reviewing your reply...",
                             lambda: orch.submit_english(sid, q["id"], submitted[0], submitted[1]))
            if out:
                run_pending_presence("eng", sid, q, orch)
                st.session_state["eng_res"] = out
                st.rerun()
    else:
        prev = st.session_state.get("eng_prev")
        if prev is not None and res.get("attempt", 1) > 1:
            delta = res["total"] - prev
            st.info(f"📈 Attempt {res['attempt']}: {res['total']:g} / 100 ({'+' if delta >= 0 else ''}{delta:g} vs your previous attempt).")
        evaluation_view(res, user.id, key=f"eng-{q['id']}-{res['evaluation_id']}")
        presence_view(st.session_state.get("eng_presence", {}).get(q["id"]))
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔁 Try this reply again", help="Use the natural version as a model and answer again"):
                st.session_state["eng_prev"] = res["total"]
                st.session_state.pop("eng_res", None)
                clear_answer(ans_key)
                st.rerun()
        with c2:
            if st.button("💬 Continue the conversation", type="primary"):
                nq = run_safely("Your partner is replying...", lambda: orch.english_turn(sid))
                if nq:
                    st.session_state["eng_q"] = nq
                    st.session_state.pop("eng_res", None)
                    st.session_state.pop("eng_prev", None)
                    st.rerun()
        with c3:
            if st.button("🏁 End and choose a new scenario"):
                db.end_session(sid, {"headline": "English practice session"})
                _reset()
                st.rerun()
