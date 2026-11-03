"""Orchestration layer.

The orchestrator is the only component that knows about all agents. For each
learner action it:
  1. loads shared learner context from the database,
  2. picks which agent(s) should act,
  3. runs independent agents in parallel (technical + language evaluation),
  4. combines their outputs into the 10-category scorecard,
  5. hands the result to the Gap Analyst and persists everything,
  6. decides what happens next (follow-up, teaching + re-test, difficulty change, end).
"""
from __future__ import annotations

import ast
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any

import analytics, db
from agents import (ConfidenceCoach, EnglishCoach, GapAnalyst, HRCareerCoach, LearnerContext, PresenceCoach, ProgressManager, SessionSpec,
                     TechnicalInterviewer, TechnicalMentor)
from config import get_logger, settings
from llm import LLMError, LLMProvider, get_provider
from topics import ALL_TOPICS, normalize_topic

log = get_logger(__name__)

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced", "Senior Engineer"]
JOB_ROLES = ["Python Developer", "Junior AI Engineer", "AI Engineer", "Generative AI Engineer", "Agentic AI Developer",
             "AI Automation Engineer", "AI Full Stack Developer", "LLM Application Developer"]
CATEGORIES = ["Technical", "Communication", "Behavioral", "System Design", "Project Discussion", "Complete Interview"]
PITCH_LENGTHS = {"30 seconds": 30, "1 minute": 60, "3 minutes": 180, "5 minutes": 300}
SPEAKING_WPM = 130  # typical comfortable interview speaking rate, used only to estimate pitch length from word count


class ValidationError(ValueError):
    pass


def validate_answer(answer: str) -> str:
    answer = (answer or "").strip()
    if not answer:
        raise ValidationError("Your answer is empty. Type or record an answer first.")
    if len(answer) > settings.max_answer_chars:
        raise ValidationError(f"Your answer is too long ({len(answer)} characters). Keep it under "
                              f"{settings.max_answer_chars} characters.")
    return answer


SPOKEN_MODES = {"voice", "video"}


def wellbeing_note(history: list[dict]) -> str:
    """A short, factual line for the interviewers so they can adapt their tone to how the learner has been feeling."""
    conf = [h["confidence"] for h in history if isinstance(h.get("confidence"), (int, float))]
    moods = [h["mood"] for h in history if isinstance(h.get("mood"), (int, float))]
    if not conf and not moods:
        return ""
    parts = []
    if conf:
        avg = sum(conf[-5:]) / len(conf[-5:])
        parts.append(f"recent speaking confidence about {avg:.0f}/10")
        if avg <= 4:
            parts.append("they have sounded nervous: keep a warm tone, ask one clear question at a time, and "
                         "acknowledge effort before probing (keep the standard of scoring unchanged)")
        elif avg >= 8:
            parts.append("they sound confident: you can raise the challenge")
    if moods and moods[-1] <= 1:
        parts.append("at their last check-in they said they felt anxious")
    return "; ".join(parts) + "."


class Orchestrator:
    def __init__(self, provider: LLMProvider | None = None, provider_name: str | None = None):
        self.provider = provider or get_provider(provider_name)
        self.interviewer = TechnicalInterviewer(self.provider)
        self.english = EnglishCoach(self.provider)
        self.mentor = TechnicalMentor(self.provider)
        self.gaps = GapAnalyst(self.provider)
        self.hr = HRCareerCoach(self.provider)
        self.progress = ProgressManager(self.provider)
        self.presence = PresenceCoach(self.provider)
        self.coach = ConfidenceCoach(self.provider)

    # ------------------------------------------------------------------ shared context

    def context(self, user_id: int) -> LearnerContext:
        user = db.get_user(user_id)
        if user is None:
            raise ValidationError("User not found.")
        gaps = [{"category": g.category, "topic": g.topic, "description": g.description,
                 "occurrences": g.occurrences, "priority": g.priority} for g in db.list_gaps(user_id)]
        recent = [ev.total for ev, _, _ in db.evaluations_for_user(user_id)[-10:]]
        return LearnerContext(name=user.name, target_role=user.target_role, background=user.background,
                              open_gaps=gaps, recent_average=sum(recent) / len(recent) if recent else None,
                              wellbeing_note=wellbeing_note(db.emotion_history(user_id, 8)))

    @staticmethod
    def _spec(sess: db.InterviewSession) -> SessionSpec:
        c = sess.context or {}
        return SessionSpec(module=sess.module, job_role=sess.job_role, difficulty=sess.difficulty,
                           category=sess.category, region=c.get("region", "International English"),
                           style=c.get("style", "Neutral"), focus_topics=c.get("focus_topics", []),
                           project=c.get("project"), extra=c.get("extra", {}))

    @staticmethod
    def _history(session_id: int) -> list[dict]:
        evs = {q.id: ev for ev, q in db.evaluations_for_session(session_id)}  # latest attempt wins
        out = []
        for q in db.session_questions(session_id):
            ev = evs.get(q.id)
            if ev is None:
                continue
            t = ev.technical or {}
            note = "; ".join((t.get("misunderstood") or [])[:2] + (t.get("missing_concepts") or [])[:2])
            out.append({"question": q.question, "topic": q.topic, "kind": q.kind, "answer": ev.answer,
                        "score": ev.scores.get("technical_accuracy"), "note": note})
        return out

    # ------------------------------------------------------------------ interview-style sessions

    def start_session(self, user_id: int, module: str, job_role: str, difficulty: str, category: str,
                      planned_questions: int = 5, region: str = "International English", style: str = "Neutral",
                      focus_topics: list[str] | None = None, project: dict | None = None) -> tuple[int, dict]:
        if difficulty not in DIFFICULTIES:
            raise ValidationError("Unknown difficulty.")
        planned_questions = max(1, min(30, int(planned_questions)))
        ctx = {"region": region, "style": style, "focus_topics": [normalize_topic(t) for t in (focus_topics or [])],
               "project": project}
        sess = db.create_session(user_id, module, job_role=job_role, difficulty=difficulty, category=category,
                                 planned_questions=planned_questions, context=ctx)
        q = self.next_question(sess.id)
        return sess.id, q

    def _pick_agent(self, spec: SessionSpec, position: int, planned: int) -> tuple[Any, str | None]:
        """Decide which agent asks the next question (and optionally which topic)."""
        if spec.module == "hr" or spec.category == "Behavioral":
            return self.hr, ("pro.self_intro" if position == 1 else None)
        if spec.category == "Complete Interview":
            if position == 1:
                return self.hr, "pro.self_intro"
            if planned >= 4 and position == planned:
                return self.hr, "pro.behavioral_star"
            return self.interviewer, None
        if spec.module == "revision" and spec.focus_topics:
            topic = spec.focus_topics[(position - 1) % len(spec.focus_topics)]
            agent = self.hr if topic.startswith("pro.") else self.interviewer
            return agent, topic
        return self.interviewer, None

    def next_question(self, session_id: int) -> dict:
        sess = db.get_session(session_id)
        if sess is None:
            raise ValidationError("Session not found.")
        spec = self._spec(sess)
        history = self._history(session_id)
        position = len(db.session_questions(session_id)) + 1
        ctx = self.context(sess.user_id)

        pending = (sess.context or {}).get("pending_revision")
        if pending:
            agent, topic, kind = self.interviewer, pending, "revision"
            if pending.startswith("pro."):
                agent = self.hr
            new_ctx = dict(sess.context or {})
            new_ctx.pop("pending_revision", None)
            db.update_session(session_id, context=new_ctx)
        else:
            agent, topic = self._pick_agent(spec, position, sess.planned_questions)
            kind = None

        out = agent.ask(ctx, spec, history, force_topic=topic, force_kind=kind)
        if not out["question"]:
            raise LLMError("The interviewer did not return a question. Please try again.")
        q = db.add_question(session_id, out["question"], out["topic"], out["kind"], sess.difficulty, agent.name)
        db.add_message(sess.user_id, session_id, "assistant", out["question"], agent.name)
        return {"id": q.id, "question": q.question, "topic": q.topic, "kind": q.kind, "agent": agent.title,
                "difficulty": q.difficulty, "position": q.position}

    def submit_answer(self, session_id: int, question_id: int, answer: str, input_mode: str = "text",
                      signals: dict | None = None) -> dict:
        answer = validate_answer(answer)
        sess = db.get_session(session_id)
        q = db.get_question(question_id)
        if sess is None or q is None or q.session_id != session_id:
            raise ValidationError("This question does not belong to the current session.")
        spec = self._spec(sess)
        ctx = self.context(sess.user_id)
        voice = input_mode in SPOKEN_MODES
        db.add_message(sess.user_id, session_id, "user", answer)

        evaluator = self.hr if q.agent == HRCareerCoach.name else self.interviewer
        register = "job interview" if spec.module != "english" else spec.category
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_tech = pool.submit(evaluator.evaluate, ctx, spec, q.question, q.topic, answer, voice)
            f_comm = pool.submit(self.english.evaluate, q.question, answer, voice, register)
            f_emo = self._start_emotion(pool, sess.user_id, ctx, q.question, answer, signals)
            technical, communication = f_tech.result(), f_comm.result()
            emotion = self._finish_emotion(f_emo, sess.user_id, session_id, input_mode, signals)

        scores = {k: technical[k] for k in ("technical_accuracy", "conceptual_understanding", "practical_knowledge",
                                             "overall_interview_performance")}
        scores.update({k: communication[k] for k in db.COMM_DIMS})
        extra: dict[str, Any] = {}
        target = (q.extra or {}).get("target_seconds")
        if target:
            extra["pitch"] = pitch_length_feedback(answer, target)
        if emotion:
            extra["emotion"] = emotion
        return self._finish(sess, spec, ctx, q, answer, input_mode, scores, technical, communication, extra)

    def _finish(self, sess, spec, ctx, q, answer, input_mode, scores, technical, communication, extra) -> dict:
        total = db.score_total(scores)
        improved = (technical or {}).get("improved_answer") or (communication or {}).get("natural_version") or ""
        db.add_message(sess.user_id, sess.id, "assistant",
                       f"Score: {total:g}/100" + (f"\n\nA stronger answer: {improved}" if improved else ""), "feedback")
        is_technical = not q.topic.startswith(("comm.", "pro."))
        ev = db.save_evaluation(sess.user_id, q.id, answer, input_mode, scores, total, technical or {},
                                communication or {}, q.topic, count_technical=is_technical and technical is not None)

        existing = [{"category": g.category, "topic": g.topic, "description": g.description}
                    for g in db.list_gaps(sess.user_id)]
        try:
            found = self.gaps.analyze(q.question, q.topic, answer, technical, communication, existing)
        except LLMError as exc:  # gap analysis failing should not lose the evaluation
            log.warning("Gap analysis failed: %s", exc)
            found = []
        recorded = []
        for g in found:
            gap = db.record_gap(sess.user_id, g["category"], g["topic"], g["description"], g["severity"],
                                g["recommended_exercise"], g["evidence"])
            recorded.append({**g, "topic": gap.topic, "occurrences": gap.occurrences, "priority": gap.priority})

        # Teaching rule: if they could not answer, teach first, then re-test the same concept.
        lesson = None
        tech_avg = None
        if technical is not None:
            tech_avg = (scores["technical_accuracy"] + scores["conceptual_understanding"]) / 2
        if sess.module not in {"english", "coding"} and technical is not None and (not technical["attempted"] or tech_avg <= 3):
            try:
                user_ctx = db.get_setting(sess.user_id, "urdu_support", "false") == "true"
                lesson = self.mentor.teach(ctx, q.topic, sess.difficulty, urdu_support=user_ctx,
                                           after_failed_question=q.question,
                                           mistakes=technical["misunderstood"] + technical["missing_concepts"])
                already = [x.kind for x in db.session_questions(sess.id) if x.topic == q.topic].count("revision")
                if already == 0 and q.kind != "revision":
                    new_ctx = dict(sess.context or {})
                    new_ctx["pending_revision"] = q.topic
                    db.update_session(sess.id, context=new_ctx)
            except LLMError as exc:
                log.warning("Teaching step failed: %s", exc)

        new_difficulty = self._adapt_difficulty(sess) if sess.module not in {"english", "coding"} else None
        answered = len({x.question_id for x, _ in db.evaluations_for_session(sess.id)})
        return {"evaluation_id": ev.id, "attempt": ev.attempt, "scores": scores, "total": total,
                "technical": technical, "communication": communication, "gaps": recorded, "lesson": lesson,
                "new_difficulty": new_difficulty, "answered": answered,
                "complete": answered >= sess.planned_questions, **extra}

    @staticmethod
    def _adapt_difficulty(sess: db.InterviewSession) -> str | None:
        evs = db.evaluations_for_session(sess.id)
        tech = [(e.scores["technical_accuracy"] + e.scores["conceptual_understanding"]) / 2 for e, _ in evs
                if e.scores.get("technical_accuracy") is not None]
        if len(tech) < 2:
            return None
        last2 = tech[-2:]
        idx = DIFFICULTIES.index(sess.difficulty) if sess.difficulty in DIFFICULTIES else 0
        if min(last2) >= 8 and idx < len(DIFFICULTIES) - 1:
            idx += 1
        elif max(last2) <= 4 and idx > 0:
            idx -= 1
        else:
            return None
        db.update_session(sess.id, difficulty=DIFFICULTIES[idx])
        return DIFFICULTIES[idx]

    def end_session(self, session_id: int) -> dict:
        sess = db.get_session(session_id)
        if sess is None:
            raise ValidationError("Session not found.")
        if sess.summary:
            return sess.summary
        rows = [{"question": q.question, "topic": q.topic, "total": ev.total,
                 "technical": (ev.technical or {}).get("misunderstood", []),
                 "communication_issues": [m.get("explanation") for m in (ev.communication or {}).get("grammar_mistakes", [])][:3]}
                for ev, q in db.evaluations_for_session(session_id)]
        if not rows:
            db.end_session(session_id, {"headline": "Session ended before any answers were evaluated."})
            return {"headline": "Session ended before any answers were evaluated."}
        summary = self.progress.session_summary(self.context(sess.user_id), self._spec(sess), rows)
        summary["average"] = round(sum(r["total"] for r in rows) / len(rows), 1)
        summary["answers"] = len(rows)
        db.end_session(session_id, summary)
        return summary

    # ------------------------------------------------------------------ English lab

    def start_english(self, user_id: int, scenario: str, region: str) -> tuple[int, dict]:
        sess = db.create_session(user_id, "english", job_role="", difficulty="Intermediate", category=scenario,
                                 planned_questions=1000, context={"region": region})
        return sess.id, self.english_turn(sess.id)

    def english_turn(self, session_id: int) -> dict:
        sess = db.get_session(session_id)
        if sess is None:
            raise ValidationError("Session not found.")
        history = [{"role": m.role, "content": m.content} for m in db.get_messages(session_id)]
        out = self.english.converse(sess.category, (sess.context or {}).get("region", "International English"), history)
        q = db.add_question(session_id, out["line"], "comm.fluency", "new", sess.difficulty, EnglishCoach.name,
                            {"tip": out["tip"]})
        db.add_message(sess.user_id, session_id, "assistant", out["line"], EnglishCoach.name)
        return {"id": q.id, "question": q.question, "tip": out["tip"], "topic": q.topic}

    def submit_english(self, session_id: int, question_id: int, answer: str, input_mode: str = "text",
                       signals: dict | None = None) -> dict:
        answer = validate_answer(answer)
        sess = db.get_session(session_id)
        q = db.get_question(question_id)
        if sess is None or q is None or q.session_id != session_id:
            raise ValidationError("This prompt does not belong to the current session.")
        db.add_message(sess.user_id, session_id, "user", answer)
        ctx = self.context(sess.user_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_emo = self._start_emotion(pool, sess.user_id, ctx, q.question, answer, signals)
            comm = self.english.evaluate(q.question, answer, input_mode in SPOKEN_MODES, register=sess.category)
            emotion = self._finish_emotion(f_emo, sess.user_id, session_id, input_mode, signals)
        scores: dict[str, Any] = {k: None for k in db.TECH_DIMS}
        scores["overall_interview_performance"] = None
        scores.update({k: comm[k] for k in db.COMM_DIMS})
        return self._finish(sess, self._spec(sess), ctx, q, answer, input_mode, scores,
                            None, comm, {"emotion": emotion} if emotion else {})

    # ------------------------------------------------------------------ Academy (teach -> explain back)

    def start_lesson(self, user_id: int, topic: str, level: str, urdu_support: bool = False) -> tuple[int, dict]:
        topic = normalize_topic(topic)
        ctx = self.context(user_id)
        lesson = self.mentor.teach(ctx, topic, level, urdu_support=urdu_support)
        sess = db.create_session(user_id, "academy", job_role=ctx.target_role, difficulty=level,
                                 category="Concept Explanation", planned_questions=3,
                                 context={"topic": topic, "focus_topics": [topic]})
        check = lesson.get("check_question") or f"Explain {ALL_TOPICS.get(topic, topic)} in your own words."
        q = db.add_question(sess.id, check, topic, "new", level, TechnicalMentor.name, {"lesson": lesson})
        db.add_message(user_id, sess.id, "assistant", check, TechnicalMentor.name)
        return sess.id, {"id": q.id, "question": check, "topic": topic, "lesson": lesson, "position": 1,
                         "agent": TechnicalMentor.title, "difficulty": level, "kind": "new"}

    # ------------------------------------------------------------------ Coding lab

    def start_coding(self, user_id: int, topic: str, difficulty: str) -> tuple[int, dict]:
        topic = normalize_topic(topic, "python.fundamentals")
        ctx = self.context(user_id)
        ch = self.mentor.coding_challenge(ctx, topic, difficulty)
        sess = db.create_session(user_id, "coding", job_role=ctx.target_role, difficulty=difficulty,
                                 category="Coding", planned_questions=1, context={"topic": topic})
        q = db.add_question(sess.id, ch["title"] + "\n\n" + ch["problem"], topic, "new", difficulty,
                            TechnicalMentor.name, {"challenge": ch})
        db.add_message(user_id, sess.id, "assistant", q.question, TechnicalMentor.name)
        return sess.id, {"id": q.id, "challenge": ch}

    def submit_code(self, session_id: int, question_id: int, code: str) -> dict:
        code = (code or "").strip()
        if not code:
            raise ValidationError("Paste your code first.")
        if len(code) > 20_000:
            raise ValidationError("Code is too long for review (20,000 character limit).")
        sess = db.get_session(session_id)
        q = db.get_question(question_id)
        if sess is None or q is None or q.session_id != session_id:
            raise ValidationError("This challenge does not belong to the current session.")
        db.add_message(sess.user_id, session_id, "user", code)
        syntax_error = check_syntax(code)
        review = self.mentor.review_code((q.extra or {}).get("challenge", {}), code, syntax_error)
        scores: dict[str, Any] = {"technical_accuracy": review["correctness"],
                                  "conceptual_understanding": review["problem_solving"],
                                  "practical_knowledge": review["code_quality"],
                                  "overall_interview_performance": review["overall"]}
        scores.update({k: None for k in db.COMM_DIMS})
        technical = {**review, "attempted": True, "misunderstood": [i.get("issue", "") for i in review["issues"]][:5],
                     "missing_concepts": [], "what_was_correct": review["what_was_good"]}
        result = self._finish(sess, self._spec(sess), self.context(sess.user_id), q, code, "code", scores,
                              technical, None, {"syntax_error": syntax_error})
        result["review"] = review
        return result

    # ------------------------------------------------------------------ Confidence & emotions

    def _start_emotion(self, pool, user_id: int, ctx, question: str, answer: str, signals: dict | None):
        """Start the confidence coach in parallel with the evaluators (only when the learner opted in)."""
        if signals is None:
            return None
        return pool.submit(self.coach.assess, ctx, question, answer, signals,
                           db.emotion_history(user_id, 8), db.self_reports(user_id))

    def _finish_emotion(self, future, user_id: int, session_id: int, input_mode: str, signals: dict | None) -> dict | None:
        if future is None:
            return None
        try:
            res = future.result()
        except (LLMError, ValueError) as exc:  # coaching must never cost the learner their evaluation
            log.warning("Confidence coach failed: %s", exc)
            return None
        res["check_id"] = db.add_emotion_check(user_id, session_id, input_mode, signals, res)
        db.add_message(user_id, session_id, "assistant", f"💛 {res['mentor_message']}".strip(), ConfidenceCoach.name)
        return res

    def mentor_chat(self, user_id: int, session_id: int | None, text: str) -> tuple[int, dict]:
        """One turn of the private mentoring chat. Creates the session on the first message."""
        text = validate_answer(text)
        if session_id is None:
            session_id = db.create_session(user_id, "coach", job_role="", difficulty="", category="Mentor chat",
                                           planned_questions=1000).id
        sess = db.get_session(session_id)
        if sess is None or sess.user_id != user_id:
            raise ValidationError("This chat does not belong to you.")
        db.add_message(user_id, session_id, "user", text)
        msgs = [{"role": m.role, "content": m.content} for m in db.get_messages(session_id)]
        out = self.coach.chat(self.context(user_id), msgs, db.emotion_history(user_id, 10), db.self_reports(user_id))
        reply = out["reply"]
        if out.get("technique") and out["technique"].get("steps"):
            reply += "\n\n" + f"🧘 {out['technique']['name']}:\n" + "\n".join(f"{i}. {x}" for i, x in
                                                                           enumerate(out["technique"]["steps"], 1))
        db.add_message(user_id, session_id, "assistant", reply, ConfidenceCoach.name + "_chat")
        return session_id, {**out, "reply_text": reply}

    def confidence_journey(self, user_id: int) -> dict:
        hist = [h for h in db.emotion_history(user_id, 60) if h["source"] != "checkin" or h["self_report"]]
        if len(hist) < 2:
            raise ValidationError("Answer a few questions with the confidence coach switched on first, so the plan "
                                  "is based on real data.")
        return self.coach.journey(self.context(user_id), hist, db.self_reports(user_id, 20))

    # ------------------------------------------------------------------ Video presence

    def presence_check(self, session_id: int, image: bytes, question: str = "") -> dict:
        """Coach on-camera presence from one webcam frame. The image itself is never stored."""
        sess = db.get_session(session_id)
        if sess is None:
            raise ValidationError("Session not found.")
        if not image or len(image) > 4 * 1024 * 1024:
            raise ValidationError("The camera snapshot was empty or too large.")
        res = self.presence.assess(image, question)
        tips = "\n".join(f"- {t}" for t in res["tips"])
        db.add_message(sess.user_id, session_id, "assistant",
                       f"On-camera presence: {res['overall']}/10\n{tips}".strip(), PresenceCoach.name)
        return res

    # ------------------------------------------------------------------ Project pitch

    def start_pitch(self, user_id: int, project: dict, length_label: str, region: str) -> tuple[int, dict]:
        seconds = PITCH_LENGTHS.get(length_label, 60)
        user = db.get_user(user_id)
        sess = db.create_session(user_id, "project", job_role=user.target_role if user else "", difficulty="Intermediate",
                                 category="Project Discussion", planned_questions=1,
                                 context={"region": region, "project": project})
        prompt = (f"Please give me a {length_label} overview of your project \"{project.get('title')}\": the problem, "
                  f"what you built, how it works, and the result.")
        q = db.add_question(sess.id, prompt, "pro.project_explanation", "new", "Intermediate",
                            TechnicalInterviewer.name, {"target_seconds": seconds})
        db.add_message(user_id, sess.id, "assistant", prompt, TechnicalInterviewer.name)
        return sess.id, {"id": q.id, "question": prompt, "target_seconds": seconds}

    # ------------------------------------------------------------------ Reports & roadmap

    def weekly_report(self, user_id: int, end: dt.date | None = None) -> dict:
        end = end or dt.date.today()
        start = end - dt.timedelta(days=6)
        stats = analytics.period_stats(user_id, start, end)
        if stats["current"]["answers"] == 0:
            raise ValidationError("No evaluated answers in the last 7 days, so there is nothing to report yet. "
                                  "Complete a practice session first.")
        content = self.progress.weekly_report(self.context(user_id), stats)
        rep = db.save_report(user_id, start, end, stats, content)
        return {"id": rep.id, "stats": stats, "content": content}

    def adjust_roadmap(self, user_id: int) -> dict:
        current = db.active_roadmap(user_id)
        base = current.content if current else analytics.BASE_ROADMAP
        start = current.start_date if current else dt.date.today()
        day = analytics.roadmap_day(start)
        out = self.mentor.adjust_roadmap(self.context(user_id), base, analytics.skill_summary_text(user_id), day)
        rm = db.save_roadmap(user_id, {"phases": out["phases"]}, out["rationale"], start)
        return {"id": rm.id, "content": rm.content, "rationale": rm.rationale}

    def revision_topics(self, user_id: int, limit: int = 5) -> list[str]:
        gaps = db.list_gaps(user_id)
        topics = [g.topic for g in gaps if g.priority] or [g.topic for g in gaps]
        seen: list[str] = []
        for t in topics:
            if t not in seen:
                seen.append(t)
        return seen[:limit]


def check_syntax(code: str) -> str | None:
    """Parse only. The code is never executed."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"


def pitch_length_feedback(answer: str, target_seconds: int) -> dict:
    words = len(answer.split())
    est = round(words / SPEAKING_WPM * 60)
    low, high = target_seconds * 0.75, target_seconds * 1.25
    verdict = "about right" if low <= est <= high else ("too short" if est < low else "too long")
    return {"words": words, "estimated_seconds": est, "target_seconds": target_seconds, "verdict": verdict,
            "note": f"Estimated from word count at about {SPEAKING_WPM} words per minute, not measured from audio."}


def spec_dict(spec: SessionSpec) -> dict:
    return asdict(spec)
