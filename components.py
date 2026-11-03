"""Reusable Streamlit components."""
from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

import db, voice
from avatar import avatar_svg, bubble
from config import get_logger, settings
from llm import LLMError
from orchestrator import Orchestrator, ValidationError
from topics import ALL_TOPICS, GROUP_LABELS, group_of

log = get_logger(__name__)

SCORE_LABELS = {
    "technical_accuracy": "Technical accuracy",
    "conceptual_understanding": "Conceptual understanding",
    "practical_knowledge": "Practical knowledge",
    "english_grammar": "English grammar",
    "vocabulary": "Vocabulary",
    "sentence_structure": "Sentence structure",
    "fluency_clarity": "Fluency and clarity",
    "confidence": "Confidence",
    "professional_communication": "Professional communication",
    "overall_interview_performance": "Overall interview performance",
}

ACCENTS = ["International English", "American English", "British English", "Canadian English",
           "Australian English", "New Zealand English"]
STYLES = ["Friendly", "Neutral", "Challenging"]

DEFAULT_PREFS = {"provider": "", "accent": "International English", "tts": "browser", "autoplay": "true",
                 "urdu_support": "false", "style": "Neutral", "mode": "chat", "hands_free": "false",
                 "presence": "true"}

MODES = {"chat": "💬 Chat", "voice": "🎙️ Voice call", "video": "🎥 Video call"}


def esc(text: Any) -> str:
    return html.escape(str(text or ""))


def topic_label(topic: str) -> str:
    return ALL_TOPICS.get(topic, topic)


# --------------------------------------------------------------------------- state helpers

def prefs(user_id: int) -> dict[str, str]:
    return {k: db.get_setting(user_id, k, v) for k, v in DEFAULT_PREFS.items()}


def get_orchestrator(user_id: int) -> Orchestrator | None:
    """Build (and cache per browser session) the orchestrator, or show setup help."""
    p = prefs(user_id).get("provider") or None
    key = f"orch::{p}"
    if key not in st.session_state:
        try:
            st.session_state[key] = Orchestrator(provider_name=p)
        except LLMError as exc:
            setup_notice(str(exc))
            return None
    return st.session_state[key]


def setup_notice(msg: str) -> None:
    import keys

    st.markdown(f'<div class="am-callout">{avatar_svg(56, "thinking", "AI Mentor")}<div><b>🔑 Connect an AI key to start</b>'
                '<br><span>Paste a Claude or OpenAI API key. It stays in this browser session only and is never saved.'
                '</span></div></div>', unsafe_allow_html=True)
    with st.container(border=True):
        keys.key_form("inline")
    st.caption("📊 Your dashboard, roadmap, history and saved data still work without a key.")


def run_safely(label: str, fn: Callable[[], Any]) -> Any:
    """Run an AI action with a spinner and turn errors into clear messages."""
    try:
        with st.spinner(label):
            return fn()
    except ValidationError as exc:
        st.warning(str(exc))
    except LLMError as exc:
        st.error(str(exc))
    except Exception:  # noqa: BLE001
        log.exception("Unexpected error during %s", label)
        st.error("Something went wrong. The error has been logged. Please try again.")
    return None


# --------------------------------------------------------------------------- layout pieces

def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="am-head"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>', unsafe_allow_html=True)


def chips(*items: tuple[str, str]) -> None:
    st.markdown("".join(f'<span class="am-chip {cls}">{esc(t)}</span>' for t, cls in items if t),
                unsafe_allow_html=True)


def metric_card(label: str, value: float | None, n: int, unit: str = "answers", suffix: str = "") -> None:
    if value is None:
        st.markdown(f'<div class="am-card am-metric empty"><div class="am-label">{esc(label)}</div>'
                    f'<div class="am-num">&mdash;</div><div class="am-sub">No data yet</div></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="am-card am-metric"><div class="am-label">{esc(label)}</div>'
                    f'<div class="am-num">{value:g}{esc(suffix)}</div><div class="am-sub">from {n} {esc(unit)}</div></div>',
                    unsafe_allow_html=True)


def question_block(text: str, who: str, meta: list[tuple[str, str]] | None = None) -> None:
    st.markdown(bubble(text, who, "assistant"), unsafe_allow_html=True)
    if meta:
        chips(*meta)


def speak(text: str, user_id: int, key: str, autoplay: bool | None = None, label: str = "Play") -> None:
    p = prefs(user_id)
    mode = p["tts"]
    if mode == "off" or not text:
        return
    auto = (p["autoplay"] == "true") if autoplay is None else autoplay
    if mode == "openai" and settings.has_openai:
        cache = st.session_state.setdefault("tts_cache", {})
        if key not in cache:
            try:
                cache[key] = voice.openai_tts(text)
            except LLMError as exc:
                st.caption(str(exc))
                return
        st.iframe(voice.audio_player_html(cache[key], autoplay=auto, label=label, with_avatar=False), height=46)
    else:
        st.iframe(voice.browser_tts_html(text, p["accent"], autoplay=auto, label=label, with_avatar=False), height=46)


def scorecard(scores: dict, total: float) -> None:
    rows = []
    for k in db.SCORECARD:
        v = scores.get(k)
        label = esc(SCORE_LABELS[k])
        if v is None:
            rows.append(f'<div class="lbl">{label}</div><div class="na">not assessed here</div><div></div>')
        else:
            rows.append(f'<div class="lbl">{label}</div><div class="bar"><i style="width:{v * 10}%"></i></div>'
                        f'<div class="val">{v}</div>')
    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(f'<div class="am-total">{total:g}<small> / 100</small></div>', unsafe_allow_html=True)
        assessed = sum(1 for k in db.SCORECARD if scores.get(k) is not None)
        if assessed < 10:
            st.caption(f"Total rescaled from the {assessed} categories assessed in this exercise.")
    with c2:
        st.markdown(f'<div class="am-score">{"".join(rows)}</div>', unsafe_allow_html=True)


def bullet_list(title: str, items: list, empty: str | None = None) -> None:
    items = [i for i in items if i]
    if not items and empty is None:
        return
    st.markdown(f"**{title}**")
    if items:
        st.markdown("\n".join(f"- {i}" for i in items))
    else:
        st.caption(empty)


def technical_feedback(t: dict) -> None:
    c1, c2 = st.columns(2)
    with c1:
        bullet_list("✅ What you got right", t.get("what_was_correct", []), "Nothing clearly correct yet.")
        bullet_list("⚠️ Misunderstood", t.get("misunderstood", []) + t.get("incorrect_concepts", []), "No misunderstandings found.")
    with c2:
        bullet_list("🧩 Missing concepts", t.get("missing_concepts", []), "Nothing important missing.")
        if t.get("star"):
            star = t["star"]
            st.markdown("**⭐ STAR structure**")
            for part in ("situation", "task", "action", "result"):
                val = star.get(part) or ""
                st.markdown(f"- {part.title()}: {esc(val) if val else '_missing_'}")
    if t.get("correct_explanation"):
        st.markdown("**📖 The correct explanation**")
        st.markdown(t["correct_explanation"])
    if t.get("exercise"):
        st.info(f"🏋️ Practice exercise: {t['exercise']}")


def english_feedback(c: dict, user_id: int, key: str) -> None:
    fixes = c.get("grammar_mistakes", []) + [
        {"original": u.get("original"), "correction": u.get("natural"), "explanation": u.get("explanation")}
        for u in c.get("unnatural_expressions", [])]
    if fixes:
        st.markdown("**✏️ Corrections**")
        for m in fixes:
            st.markdown(f'<div class="am-fix"><span class="from">{esc(m.get("original"))}</span><br>'
                        f'<span class="to">{esc(m.get("correction"))}</span>'
                        f'<div class="why">{esc(m.get("explanation"))}</div></div>', unsafe_allow_html=True)
    else:
        st.caption("No grammar or phrasing mistakes found.")
    if c.get("natural_version"):
        st.markdown("**💼 A natural, professional version**")
        st.success(c["natural_version"])
        speak(c["natural_version"], user_id, key=f"{key}-natural", autoplay=False, label="Listen to this version")
        if c.get("why_better"):
            st.caption(c["why_better"])
    cols = st.columns(2)
    with cols[0]:
        if c.get("new_vocabulary"):
            st.markdown("**📚 Vocabulary to use**")
            for v in c["new_vocabulary"]:
                st.markdown(f"- **{esc(v.get('term'))}**: {esc(v.get('meaning'))}  \n  _{esc(v.get('example'))}_")
    with cols[1]:
        if c.get("words_to_practise"):
            st.markdown("**🔤 Words to practise saying**")
            st.markdown("\n".join(f"- {esc(w.get('word'))} ({esc(w.get('stress'))})" for w in c["words_to_practise"]))
            st.caption("Suggested from your wording. Your audio is not analysed for pronunciation.")
    if c.get("practice_sentence"):
        st.markdown("**🗣️ Say this sentence out loud three times**")
        st.markdown(f"> {c['practice_sentence']}")
        speak(c["practice_sentence"], user_id, key=f"{key}-practice", autoplay=False, label="Hear it")


def gaps_found(gaps: list[dict]) -> None:
    if not gaps:
        st.caption("No new weaknesses recorded from this answer.")
        return
    for g in gaps:
        flag = ("Priority", "warn") if g.get("priority") else ("", "")
        chips((g["category"].title(), "violet"), (topic_label(g["topic"]), "volt"),
              (f"Seen {g.get('occurrences', 1)}x", ""), flag)
        st.markdown(f"{esc(g['description'])}")
        if g.get("recommended_exercise"):
            st.caption(f"Exercise: {g['recommended_exercise']}")


def lesson_view(lesson: dict, user_id: int, key: str) -> None:
    st.markdown(f"#### {esc(lesson.get('title'))}")
    st.markdown(lesson.get("simple_explanation", ""))
    if lesson.get("analogy"):
        st.markdown(f"**💡 Think of it like this:** {lesson['analogy']}")
    if lesson.get("example"):
        st.markdown("**Example**")
        st.markdown(lesson["example"])
    c1, c2 = st.columns(2)
    with c1:
        bullet_list("🔑 Key points", lesson.get("key_points", []))
    with c2:
        bullet_list("⚠️ Common mistakes", lesson.get("common_mistakes", []))
    if lesson.get("urdu_note"):
        st.markdown("**🇵🇰 Urdu support**")
        st.markdown(f"> {lesson['urdu_note']}")
    speak(lesson.get("simple_explanation", ""), user_id, key=f"{key}-lesson", autoplay=False, label="Listen to the explanation")


def evaluation_view(res: dict, user_id: int, key: str) -> None:
    scorecard(res["scores"], res["total"])
    if res.get("attempt", 1) > 1:
        st.caption(f"Attempt {res['attempt']} on this question.")
    if res.get("new_difficulty"):
        st.info(f"🎚️ Difficulty adjusted to {res['new_difficulty']} based on your last two answers.")
    if res.get("pitch"):
        p = res["pitch"]
        st.info(f"Length: about {p['estimated_seconds']}s for a {p['target_seconds']}s target ({p['verdict']}). "
                f"{p['note']}")
    tabs = []
    if res.get("technical"):
        tabs.append("🧠 Technical feedback")
    if res.get("communication"):
        tabs.append("🗣️ English feedback")
    tabs.append("✨ Improved answer")
    tabs.append("🎯 Weaknesses recorded")
    if res.get("lesson"):
        tabs.insert(0, "📚 Learn this first")
    t = dict(zip(tabs, st.tabs(tabs)))
    if "📚 Learn this first" in t:
        with t["📚 Learn this first"]:
            st.markdown("You could not answer this one yet, so here is the concept. "
                        "Your next question will check it again.")
            lesson_view(res["lesson"], user_id, key)
    if "🧠 Technical feedback" in t:
        with t["🧠 Technical feedback"]:
            technical_feedback(res["technical"])
    if "🗣️ English feedback" in t:
        with t["🗣️ English feedback"]:
            english_feedback(res["communication"], user_id, key)
    with t["✨ Improved answer"]:
        improved = (res.get("technical") or {}).get("improved_answer") or (res.get("communication") or {}).get("natural_version")
        if improved:
            st.markdown(improved)
            speak(improved, user_id, key=f"{key}-improved", autoplay=False, label="Listen")
            st.caption("Read it aloud, then use 'Answer again' to repeat it in your own words.")
        else:
            st.caption("No improved answer for this exercise.")
    with t["🎯 Weaknesses recorded"]:
        gaps_found(res.get("gaps", []))


# --------------------------------------------------------------------------- answer input

def answer_input(key: str, user_id: int, placeholder: str = "Type your answer here, the way you would say it.") -> tuple[str, str] | None:
    """Text answer with optional voice recording. Returns (answer, mode) when submitted."""
    text_key, mode_key = f"{key}-text", f"{key}-mode"
    st.session_state.setdefault(mode_key, "text")

    if voice.stt_available():
        audio = st.audio_input("🎙️ Record your answer", key=f"{key}-audio")
        if audio is not None:
            def _transcribe() -> None:
                try:
                    st.session_state[text_key] = voice.transcribe(audio.getvalue())
                    st.session_state[mode_key] = "voice"
                except LLMError as exc:
                    st.session_state[f"{key}-err"] = str(exc)
            st.button("📝 Transcribe recording", key=f"{key}-tx", on_click=_transcribe)
            if st.session_state.get(f"{key}-err"):
                st.error(st.session_state.pop(f"{key}-err"))
        st.caption("Record → transcribe → check the text → submit.")
    else:
        st.caption("🎙️ Whisper recording needs an OpenAI key. Use 🎙️ Voice call mode for free browser voice typing, or type here.")

    st.text_area("Your answer", key=text_key, height=170, placeholder=placeholder, label_visibility="collapsed")
    words = len((st.session_state.get(text_key) or "").split())
    st.caption(f"✍️ {words} words")
    if st.button("✅ Submit answer", key=f"{key}-submit", type="primary"):
        ans = st.session_state.get(text_key, "")
        mode = st.session_state.get(mode_key, "text")
        return ans, mode
    return None


def clear_answer(key: str) -> None:
    for suffix in ("-text", "-mode", "-audio"):
        st.session_state.pop(f"{key}{suffix}", None)


# --------------------------------------------------------------------------- interview runner

def interview_runner(prefix: str, user_id: int, orch: Orchestrator) -> None:
    """Shared question -> answer -> evaluation -> next/end loop for any interview-style session."""
    sid = st.session_state.get(f"{prefix}_sid")
    if not sid:
        return
    sess = db.get_session(sid)
    if sess is None or sess.user_id != user_id:
        st.session_state.pop(f"{prefix}_sid", None)
        return

    summary = st.session_state.get(f"{prefix}_summary")
    if summary:
        session_summary_view(summary)
        if st.button("🚀 Start a new session", key=f"{prefix}-new", type="primary"):
            reset_runner(prefix)
            st.rerun()
        return

    q = st.session_state.get(f"{prefix}_q")
    res = st.session_state.get(f"{prefix}_res")
    answer_key = f"{prefix}-ans-{q['id']}" if q else f"{prefix}-ans"

    mode = conversation_mode(prefix, user_id)
    if q:
        meta = [(f"Question {q.get('position', 1)} of {sess.planned_questions}" if sess.planned_questions < 100 else "", ""),
                (topic_label(q["topic"]), "volt"), (q.get("difficulty") or sess.difficulty, "violet"),
                ("Follow-up" if q.get("kind") == "follow_up" else ("Re-check" if q.get("kind") == "revision" else ""), "warn")]
        if mode == "chat" or res:
            question_block(q["question"], q.get("agent", "Interviewer"), meta)
            if mode == "chat":
                speak(q["question"], user_id, key=f"q-{q['id']}", label="Hear the question")
        else:
            chips(*meta)

    if q and not res:
        if mode == "chat":
            submitted = answer_input(answer_key, user_id)
        else:
            submitted = call_stage(prefix, user_id, sid, q, mode, orch)
            with st.expander("⌨️ Prefer to type, or record with Whisper?"):
                submitted = answer_input(answer_key, user_id) or submitted
        if submitted:
            out = run_safely("🧑‍⚖️ Your technical and English coaches are reviewing the answer...",
                             lambda: orch.submit_answer(sid, q["id"], submitted[0], submitted[1]))
            if out:
                run_pending_presence(prefix, sid, q, orch)
                st.session_state[f"{prefix}_res"] = out
                st.rerun()
        presence_view(st.session_state.get(f"{prefix}_presence", {}).get(q["id"]))

    if res:
        st.markdown("---")
        st.markdown("### 📊 Feedback")
        evaluation_view(res, user_id, key=f"{prefix}-{q['id']}-{res['evaluation_id']}")
        presence_view(st.session_state.get(f"{prefix}_presence", {}).get(q["id"]))
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔁 Answer again", key=f"{prefix}-again", help="Try the same question again using the feedback"):
                st.session_state.pop(f"{prefix}_res", None)
                clear_answer(answer_key)
                st.rerun()
        with c2:
            if not res.get("complete") and st.button("➡️ Next question", key=f"{prefix}-next", type="primary"):
                nq = run_safely("Preparing the next question...", lambda: orch.next_question(sid))
                if nq:
                    st.session_state[f"{prefix}_q"] = nq
                    st.session_state.pop(f"{prefix}_res", None)
                    st.rerun()
        with c3:
            label = "🏁 See session summary" if res.get("complete") else "⏹️ End session"
            if st.button(label, key=f"{prefix}-end", type="primary" if res.get("complete") else "secondary"):
                summ = run_safely("Writing your session summary...", lambda: orch.end_session(sid))
                if summ:
                    st.session_state[f"{prefix}_summary"] = summ
                    st.rerun()
    elif q:
        if st.button("⏹️ End session without answering", key=f"{prefix}-quit"):
            summ = run_safely("Closing the session...", lambda: orch.end_session(sid))
            if summ is not None:
                st.session_state[f"{prefix}_summary"] = summ
                st.rerun()


def conversation_mode(prefix: str, user_id: int) -> str:
    """💬 / 🎙️ / 🎥 switch, remembered per learner."""
    p = prefs(user_id)
    current = p["mode"] if p["mode"] in MODES else "chat"
    c1, c2 = st.columns([3, 2])
    with c1:
        choice = st.segmented_control("Conversation mode", list(MODES), format_func=MODES.get, default=current,
                                      key=f"{prefix}-mode-ctl", label_visibility="collapsed")
    choice = choice or current
    if choice != current:
        db.set_setting(user_id, "mode", choice)
    if choice != "chat":
        with c2.popover("⚙️ Call settings", width="stretch"):
            hf = st.toggle("🤲 Hands-free: listen after each question and send after a pause",
                           value=p["hands_free"] == "true", key=f"{prefix}-hf")
            pr = st.toggle("📸 Presence feedback on each answer (sends one camera frame to your AI provider)",
                           value=p["presence"] == "true", key=f"{prefix}-pr", disabled=choice != "video")
            if str(hf).lower() != p["hands_free"]:
                db.set_setting(user_id, "hands_free", str(hf).lower())
            if str(pr).lower() != p["presence"]:
                db.set_setting(user_id, "presence", str(pr).lower())
            st.caption("Voice typing uses your browser's speech recognition (Chrome or Edge). "
                       "Camera frames are used for one feedback call and never stored.")
    return choice


def call_stage(prefix: str, user_id: int, sid: int, q: dict, mode: str, orch: Orchestrator) -> tuple[str, str] | None:
    """Audio/video call stage. Returns (answer, input_mode) when the learner sends an answer."""
    import videocall

    p = prefs(user_id)
    video = mode == "video"
    result = videocall.stage(q["id"], q["question"], q.get("agent", "Interviewer"), p["accent"], camera=video,
                             presence=video and p["presence"] == "true", hands_free=p["hands_free"] == "true",
                             autoplay=p["tts"] != "off", key=f"{prefix}-stage")
    snap = getattr(result, "presence", None)
    if snap and snap.get("qid") == q["id"]:
        _run_presence(prefix, sid, q, videocall.decode_image(snap.get("image")), orch)
    ans = getattr(result, "answer", None)
    if ans and ans.get("qid") == q["id"] and (ans.get("text") or "").strip():
        img = videocall.decode_image(ans.get("image"))
        if img:  # coached right after the answer is evaluated, so the transcript stays in order
            st.session_state[f"{prefix}_pending_frame"] = (q["id"], img)
        return ans["text"], mode
    return None


def run_pending_presence(prefix: str, sid: int, q: dict, orch: Orchestrator) -> None:
    pending = st.session_state.pop(f"{prefix}_pending_frame", None)
    if pending and pending[0] == q["id"]:
        _run_presence(prefix, sid, q, pending[1], orch)


def _run_presence(prefix: str, sid: int, q: dict, image: bytes | None, orch: Orchestrator) -> None:
    if not image:
        st.caption("📸 No camera frame was available for presence feedback.")
        return
    out = run_safely("📸 Your video presence coach is looking at the frame...",
                     lambda: orch.presence_check(sid, image, q["question"]))
    if out:
        st.session_state.setdefault(f"{prefix}_presence", {})[q["id"]] = out


PRESENCE_LABELS = {"eye_contact": "👀 Eye contact", "posture": "🧍 Posture", "framing": "🖼️ Framing",
                   "lighting": "💡 Lighting", "expression": "🙂 Expression", "background": "🏠 Background"}


def presence_view(r: dict | None) -> None:
    if not r:
        return
    with st.container(border=True):
        st.markdown(f"#### 📸 On-camera presence · {r['overall']}/10")
        if not r.get("person_visible", True):
            st.warning("No one was visible in the frame. Check that your camera is pointing at you.")
        rows = "".join(f'<div class="lbl">{esc(lbl)}</div><div class="bar"><i style="width:{r.get(k, 0) * 10}%"></i></div>'
                       f'<div class="val">{r.get(k, 0)}</div>' for k, lbl in PRESENCE_LABELS.items())
        c1, c2 = st.columns([3, 2])
        c1.markdown(f'<div class="am-score">{rows}</div>', unsafe_allow_html=True)
        with c2:
            bullet_list("✅ Quick fixes", r.get("tips", []))
        if r.get("observations"):
            st.caption(" · ".join(r["observations"]))
        if r.get("encouragement"):
            st.success(f"💪 {r['encouragement']}")


def start_runner(prefix: str, sid: int, q: dict) -> None:
    reset_runner(prefix)
    st.session_state[f"{prefix}_sid"] = sid
    st.session_state[f"{prefix}_q"] = q


def reset_runner(prefix: str) -> None:
    for k in ("_sid", "_q", "_res", "_summary", "_presence", "_pending_frame"):
        st.session_state.pop(f"{prefix}{k}", None)


def runner_active(prefix: str) -> bool:
    return bool(st.session_state.get(f"{prefix}_sid"))


def session_summary_view(s: dict) -> None:
    st.markdown("### 🏁 Session summary")
    if s.get("average") is not None:
        st.markdown(f'<div class="am-total">{s["average"]:g}<small> / 100 average over {s.get("answers", 0)} answers</small></div>',
                    unsafe_allow_html=True)
    if s.get("headline"):
        st.markdown(f"**{s['headline']}**")
    c1, c2 = st.columns(2)
    with c1:
        bullet_list("💪 Strengths", s.get("strengths", []))
    with c2:
        bullet_list("🎯 To work on", s.get("weaknesses", []))
    bullet_list("🧭 Next steps", s.get("next_steps", []))
    if s.get("readiness_comment"):
        st.info(s["readiness_comment"])


def topic_options(groups: list[str]) -> list[str]:
    from topics import TOPIC_GROUPS
    return [t for g in groups for t in TOPIC_GROUPS[g]]


def group_label_of(topic: str) -> str:
    return GROUP_LABELS.get(group_of(topic), "Other")
