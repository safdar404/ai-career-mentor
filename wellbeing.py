"""💛 Confidence Coach: how you sounded, how you felt, and how to grow.

* emotion_card   - the mentor's read on one answer, with the evidence, a reframe, a technique and a self-check
* breathing      - an animated 4-4-4-4 box-breathing guide (60 seconds)
* checkin        - "How are you feeling right now?" before practice
* render         - the Confidence Coach page: check-in, calm reset, trends, growth plan, and a private mentor chat
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

import db
from avatar import avatar_svg, bubble
from components import bullet_list, chips, esc, page_header, run_safely

EMOTION_EMOJI = {"calm": "😌", "confident": "😎", "focused": "🎯", "enthusiastic": "🤩", "nervous": "😬",
                 "anxious": "😟", "hesitant": "🤔", "uncertain": "😕", "frustrated": "😤", "tired": "🥱",
                 "overwhelmed": "😵", "self-critical": "🙁"}
CALM_SET = {"calm", "confident", "focused", "enthusiastic"}

SELF_REPORTS = {"right": "🎯 Spot on", "calmer": "😌 I felt calmer than that", "worse": "😟 I felt more nervous",
                "other": "✍️ Something else"}


def _meter(label: str, value: int, invert: bool = False) -> str:
    good = (10 - value) if invert else value
    color = "#34D399" if good >= 7 else ("#FBBF24" if good >= 4 else "#F87171")
    return (f'<div class="lbl">{esc(label)}</div><div class="bar"><i style="width:{value * 10}%;'
            f'background:{color}"></i></div><div class="val">{value}</div>')


def breathing_html(seconds: int = 64) -> str:
    """Box breathing: in 4, hold 4, out 4, hold 4. Pure CSS so it works everywhere; motion-safe."""
    return f"""
<div class="am-breathe" role="img" aria-label="Breathing guide: in for 4, hold for 4, out for 4, hold for 4">
  <div class="ring"><div class="dot"></div></div>
  <div class="cue"><span>Breathe in</span><span>Hold</span><span>Breathe out</span><span>Hold</span></div>
  <div class="sub">Follow the circle for about {seconds} seconds. In through the nose, out slowly through the mouth.</div>
</div>"""


BREATHE_CSS = """
<style>
.am-breathe { display:flex; flex-direction:column; align-items:center; gap:10px; padding:14px 8px; }
.am-breathe .ring { width:150px; height:150px; border-radius:50%; position:relative; display:flex; align-items:center;
  justify-content:center; border:2px solid rgba(139,92,246,.45); }
.am-breathe .dot { width:56px; height:56px; border-radius:50%;
  background: radial-gradient(circle at 35% 35%, #A5F3FC, #5B7CFA 60%, #8B5CF6);
  box-shadow: 0 0 40px rgba(34,211,238,.45); animation: am-box 16s ease-in-out infinite; }
.am-breathe .cue { position:relative; height:1.6em; width:12em; text-align:center; font-family:'Sora',sans-serif;
  font-size:1.15rem; color:#E7EBF7; }
.am-breathe .cue span { position:absolute; inset:0; opacity:0; animation: am-cue 16s infinite; }
.am-breathe .cue span:nth-child(2) { animation-delay:4s; } .am-breathe .cue span:nth-child(3) { animation-delay:8s; }
.am-breathe .cue span:nth-child(4) { animation-delay:12s; }
.am-breathe .sub { color:#A3ACCB; font-size:.85rem; text-align:center; max-width:40ch; }
@keyframes am-box { 0% { transform:scale(1); } 25% { transform:scale(2.45); } 50% { transform:scale(2.45); }
  75% { transform:scale(1); } 100% { transform:scale(1); } }
@keyframes am-cue { 0% { opacity:0; } 3%, 22% { opacity:1; } 25%, 100% { opacity:0; } }
@media (prefers-reduced-motion: reduce) { .am-breathe .dot { animation:none; } .am-breathe .cue span { animation:none; }
  .am-breathe .cue span:first-child { opacity:1; } }
.am-reframe { display:grid; grid-template-columns: 1fr auto 1fr; gap:10px; align-items:center; margin:6px 0 10px; }
.am-reframe .old { color:#FCA5A5; border:1px dashed rgba(248,113,113,.45); border-radius:10px; padding:8px 10px; }
.am-reframe .new { color:#86EFAC; border:1px solid rgba(52,211,153,.45); border-radius:10px; padding:8px 10px; }
.am-mentor { display:flex; gap:14px; align-items:flex-start; padding:14px 16px; border-radius:16px; margin-bottom:10px;
  background: linear-gradient(135deg, rgba(244,114,182,.10), rgba(139,92,246,.10)); border:1px solid rgba(244,114,182,.35); }
.am-mentor .msg { font-size:1.05rem; line-height:1.5; color:#E7EBF7; }
.am-mentor .who { color:#F9A8D4; font-size:.8rem; margin-bottom:4px; }
@media (max-width:700px) { .am-reframe { grid-template-columns: 1fr; } }
</style>"""


def breathing(seconds: int = 64) -> None:
    st.markdown(BREATHE_CSS + breathing_html(seconds), unsafe_allow_html=True)


def emotion_card(e: dict, user_id: int, key: str) -> None:
    st.markdown(BREATHE_CSS, unsafe_allow_html=True)
    if e.get("concern"):
        st.warning("💛 Your mentor noticed this may be a hard moment. Practice can wait. If things feel heavy, "
                   "please talk to someone you trust or a professional. You don't have to handle it alone.")
    emo = e.get("primary_emotion", "uncertain")
    st.markdown(f'<div class="am-mentor">{avatar_svg(52, "speaking" if emo not in CALM_SET else "idle", "Mentor")}'
                f'<div><div class="who">💛 Your mentor · you sounded {EMOTION_EMOJI.get(emo, "")} {esc(emo)}</div>'
                f'<div class="msg">{esc(e.get("mentor_message"))}</div></div></div>', unsafe_allow_html=True)
    with st.expander("💛 How you sounded, and how to feel more confident", expanded=emo not in CALM_SET):
        chips(*[(f"{EMOTION_EMOJI.get(x['label'], '')} {x['label']} {x['intensity']}/10",
                 "volt" if x["label"] in CALM_SET else "warn") for x in e.get("emotions", [])])
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown('<div class="am-score">' + _meter("😎 Confidence", e["confidence"]) + _meter("😌 Calm", e["calm"])
                        + _meter("😬 Fear of speaking", e["fear_of_speaking"], invert=True)
                        + _meter("⚡ Energy", e["energy"]) + "</div>", unsafe_allow_html=True)
            bullet_list("🔎 What I noticed", e.get("evidence", []))
        with c2:
            bullet_list("🌟 What went well", e.get("what_went_well", []))
            if e.get("next_focus"):
                st.markdown(f"**🧭 Next focus:** {esc(e['next_focus'])}")
        rf = e.get("reframe") or {}
        if rf.get("thought") and rf.get("better"):
            st.markdown("**🔄 Reframe the thought**")
            st.markdown(f'<div class="am-reframe"><div class="old">“{esc(rf["thought"])}”</div><div>➜</div>'
                        f'<div class="new">“{esc(rf["better"])}”</div></div>', unsafe_allow_html=True)
        t = e.get("technique") or {}
        if t.get("name"):
            st.markdown(f"**🧘 Try this: {esc(t['name'])}**" + (f" · {esc(t['why'])}" if t.get("why") else ""))
            if t.get("steps"):
                st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(t["steps"], 1)))
            if "breath" in t["name"].lower():
                breathing(t.get("seconds", 64))
        if e.get("power_phrase"):
            st.markdown("**💬 Power phrase for next time**")
            st.success(e["power_phrase"])
        if e.get("micro_exercise"):
            st.info(f"🏋️ Right now: {e['micro_exercise']}")
        st.caption("These are estimates from your pace, pauses, voice steadiness and words, not a diagnosis. "
                   "Tell your mentor how it really felt; it learns from you.")
        if e.get("check_id"):
            _self_report(e["check_id"], user_id, key)


def _self_report(check_id: int, user_id: int, key: str) -> None:
    done = st.session_state.setdefault("self_reported", set())
    if check_id in done:
        st.caption("✅ Thanks. Your mentor will use this to read you better next time.")
        return
    choice = st.pills("Was this right?", list(SELF_REPORTS), format_func=SELF_REPORTS.get, key=f"{key}-sr")
    note = ""
    if choice == "other":
        note = st.text_input("How did you actually feel?", key=f"{key}-sr-note", max_chars=300)
    if choice and (choice != "other" or note) and st.button("💾 Save", key=f"{key}-sr-save"):
        text = {"right": "the coach's read was accurate", "calmer": "I actually felt calmer than the coach thought",
                "worse": "I actually felt more nervous than the coach thought"}.get(choice, note)
        db.set_self_report(check_id, user_id, text)
        done.add(check_id)
        st.toast("Thanks! Your mentor is learning how you feel.", icon="💛")
        st.rerun()


def checkin(user_id: int, key: str) -> int | None:
    """Mood check-in. Returns the mood just saved (0-4) or None."""
    st.markdown("**💛 How are you feeling right now?**")
    mood = st.feedback("faces", key=f"{key}-mood")
    if mood is None:
        return None
    note = st.text_input("Anything on your mind? (optional)", key=f"{key}-mood-note", max_chars=300,
                         placeholder="e.g. I freeze when they ask about my projects")
    if st.button("💾 Save check-in", key=f"{key}-mood-save"):
        db.add_checkin(user_id, mood, note)
        st.session_state[f"{key}-saved"] = mood
        st.toast("Check-in saved", icon="💛")
    saved = st.session_state.get(f"{key}-saved")
    if saved is not None and saved <= 1:
        st.markdown("It's completely normal to feel nervous before speaking. Let's slow your body down first. 🫁")
        breathing()
    elif saved is not None:
        st.caption("Great. Carry that energy into your answers. 🚀")
    return saved


def _trend(history: list[dict]) -> None:
    pts = [h for h in history if h.get("confidence") is not None]
    if len(pts) < 2:
        st.caption("📈 Your confidence trend appears after two coached answers.")
        return
    x = list(range(1, len(pts) + 1))
    fig = go.Figure()
    for col, name, color in (("confidence", "Confidence", "#8B5CF6"), ("calm", "Calm", "#22D3EE"),
                             ("fear_of_speaking", "Fear of speaking", "#F472B6")):
        fig.add_trace(go.Scatter(x=x, y=[h[col] for h in pts], name=name, mode="lines+markers",
                                 line={"color": color, "width": 2.5}, marker={"size": 6},
                                 hovertext=[h["when"] for h in pts]))
    fig.update_layout(height=300, margin={"l": 10, "r": 10, "t": 10, "b": 10}, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font={"color": "#A3ACCB"}, legend={"orientation": "h", "y": -0.2},
                      yaxis={"range": [0, 10.5], "gridcolor": "#1C2550", "title": "0-10"},
                      xaxis={"gridcolor": "#1C2550", "title": "Coached answers (oldest → newest)"})
    st.plotly_chart(fig, width="stretch")


TOOLKIT = {
    "🫁 Box breathing (60s)": ("Calms your body before or during an interview.",
                              ["Breathe in through your nose for 4", "Hold for 4", "Breathe out slowly for 4",
                               "Hold for 4", "Repeat 4 times"]),
    "⏸️ The power pause": ("A 2-second pause sounds thoughtful, not lost.",
                          ["When asked a question, nod and say 'Good question.'", "Pause for two seconds",
                           "Start with one short headline sentence", "Then add one example"]),
    "🌉 Bridging phrases": ("Buy thinking time with professional phrases instead of 'um'.",
                           ["'Let me think about that for a moment.'", "'The way I'd approach this is...'",
                            "'There are two parts to this. First...'", "'I haven't used X directly, but I've done Y.'"]),
    "🔄 Reframe the inner critic": ("Swap absolute thoughts for true, kinder ones.",
                                   ["Notice the thought ('My English is bad')", "Ask: is it 100% true?",
                                    "Rewrite it ('My English is clear enough, and improving every week')",
                                    "Say the new version out loud once"]),
    "⚓ Confidence anchor": ("Link a calm, confident feeling to a small gesture you can use before speaking.",
                            ["Remember a moment you explained something well", "Feel it fully for 20 seconds",
                             "Press thumb and finger together at the peak", "Repeat daily; use the gesture before answers"]),
    "🪜 Exposure ladder": ("Fear shrinks when you approach it in small steps.",
                          ["Answer out loud alone", "Record yourself and listen back", "Practise with the 🎙️ Voice call",
                           "Practise with the 🎥 Video call", "Mock interview with a friend"]),
}


def render(user, orch_getter) -> None:
    page_header("💛 Confidence Coach",
                "Your kind, honest mentor for the human side of interviews: nerves, fear of speaking, self-doubt "
                "and confidence. It listens to how you speak, tracks how you feel, and guides you step by step.")
    history = db.emotion_history(user.id)
    coached = [h for h in history if h.get("confidence") is not None]

    top = st.columns(4)
    if coached:
        last = coached[-5:]
        top[0].metric("😎 Confidence", f"{sum(h['confidence'] for h in last) / len(last):.1f}/10",
                      delta=(round(coached[-1]["confidence"] - coached[0]["confidence"], 1) if len(coached) > 1 else None))
        top[1].metric("😌 Calm", f"{sum(h['calm'] for h in last) / len(last):.1f}/10")
        top[2].metric("😬 Fear of speaking", f"{sum(h['fear_of_speaking'] for h in last) / len(last):.1f}/10",
                      delta=(round(coached[-1]["fear_of_speaking"] - coached[0]["fear_of_speaking"], 1) if len(coached) > 1 else None),
                      delta_color="inverse")
    else:
        for c, label in zip(top[:3], ("😎 Confidence", "😌 Calm", "😬 Fear of speaking")):
            c.metric(label, "—")
    top[3].metric("💬 Coached answers", len(coached))

    tabs = st.tabs(["🌤️ Check-in & calm", "📈 My journey", "🗣️ Talk to my mentor", "🧰 Toolkit"])
    with tabs[0]:
        c1, c2 = st.columns([3, 2], gap="large")
        with c1:
            checkin(user.id, "coach-page")
            st.markdown("---")
            st.markdown("**🫁 Need a calm reset? Follow the circle.**")
        with c2:
            st.markdown(f'<div style="text-align:center">{avatar_svg(120, "idle", "Mentor")}</div>', unsafe_allow_html=True)
            st.caption("Tip: in 🎙️ Voice or 🎥 Video call mode, the coach also reads your pace, pauses and voice "
                       "steadiness. In 💬 Chat it reads your words.")
        breathing()

    with tabs[1]:
        _trend(history)
        if coached:
            counts: dict[str, int] = {}
            for h in coached[-20:]:
                counts[h["primary_emotion"]] = counts.get(h["primary_emotion"], 0) + 1
            chips(*[(f"{EMOTION_EMOJI.get(k, '')} {k} ×{v}", "volt" if k in CALM_SET else "warn")
                    for k, v in sorted(counts.items(), key=lambda kv: -kv[1])])
            voice = [h["voice"] for h in coached if h.get("voice", {}).get("words_per_minute")]
            if voice:
                wpm = [v["words_per_minute"] for v in voice[-5:]]
                st.caption(f"🎙️ Recent speaking pace: {sum(wpm) / len(wpm):.0f} words/min (calm interview pace is 120-160).")
        orch = None
        if st.button("🧭 Build my confidence growth plan", type="primary", key="journey-go"):
            orch = orch_getter()
            if orch is not None:
                plan = run_safely("💛 Your mentor is reviewing your journey...", lambda: orch.confidence_journey(user.id))
                if plan:
                    st.session_state["journey_plan"] = plan
        plan = st.session_state.get("journey_plan")
        if plan:
            st.markdown(f"#### 🌱 {esc(plan['summary'])}")
            c1, c2 = st.columns(2)
            with c1:
                bullet_list("🔁 Patterns", plan["patterns"])
                bullet_list("💪 Strengths", plan["strengths"])
                bullet_list("📅 Daily routine", plan["daily_routine"])
            with c2:
                st.markdown("**🪜 Your speaking ladder (easiest first)**")
                for i, s in enumerate(plan["exposure_ladder"], 1):
                    st.markdown(f"{i}. **{esc(s['step'])}**  \n   ✅ {esc(s['goal'])}")
            if plan.get("affirmation"):
                st.success(f"💛 {plan['affirmation']}")
        with st.expander("🗒️ Every reading"):
            for h in reversed(history[-30:]):
                if h["source"] == "checkin":
                    st.markdown(f"- {h['when']} · 💛 {esc(h['self_report'])}")
                else:
                    st.markdown(f"- {h['when']} · {h['source']} · {EMOTION_EMOJI.get(h['primary_emotion'], '')} "
                                f"{h['primary_emotion']} · confidence {h['confidence']}/10"
                                + (f" · _you said: {esc(h['self_report'])}_" if h["self_report"] else ""))

    with tabs[2]:
        _mentor_chat(user, orch_getter)

    with tabs[3]:
        for name, (why, steps) in TOOLKIT.items():
            with st.expander(name):
                st.markdown(f"_{why}_")
                st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))
                if "breathing" in name.lower():
                    breathing()

    st.caption("💛 Your mentor is an AI coach, not a therapist. If anxiety is affecting your daily life, talking to a "
               "doctor or counsellor can really help.")


def _mentor_chat(user, orch_getter) -> None:
    sid = st.session_state.get("coach_sid")
    msgs = db.get_messages(sid) if sid else []
    if not msgs:
        st.markdown(bubble("Hi, I'm your mentor. 💛 What's on your mind about speaking or interviews? For example: "
                           "\"I freeze when I don't know an answer\" or \"I feel my English isn't good enough.\"",
                           "💛 Mentor"), unsafe_allow_html=True)
    else:
        st.markdown('<div class="am-chat">' + "".join(
            bubble(m.content, "💛 Mentor" if m.role == "assistant" else user.name, m.role) for m in msgs) + "</div>",
            unsafe_allow_html=True)
    with st.form("mentor-chat", clear_on_submit=True):
        text = st.text_area("Message your mentor", height=90, max_chars=2000, label_visibility="collapsed",
                            placeholder="Tell your mentor how you feel, or ask for help with a fear...")
        send = st.form_submit_button("💬 Send", type="primary")
    if send and text.strip():
        orch = orch_getter()
        if orch is not None:
            out = run_safely("💛 Your mentor is listening...", lambda: orch.mentor_chat(user.id, sid, text))
            if out:
                st.session_state["coach_sid"] = out[0]
                if out[1].get("concern"):
                    st.session_state["coach_concern"] = True
                st.rerun()
    if st.session_state.get("coach_concern"):
        st.warning("💛 It sounds like things are heavy right now. Please consider talking with someone you trust or a "
                   "professional. You deserve support.")
    if sid and st.button("🆕 New conversation", key="coach-new"):
        st.session_state.pop("coach_sid", None)
        st.session_state.pop("coach_concern", None)
        st.rerun()
    st.caption("🔒 Saved privately in your 🗂️ Conversation History. You can delete it any time.")

