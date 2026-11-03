"""Persistent learning records.

SQLAlchemy ORM so the same code runs on SQLite (local) and PostgreSQL
(production): change DATABASE_URL, nothing else.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_logger, settings
from topics import normalize_topic

log = get_logger(__name__)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    target_role: Mapped[str] = mapped_column(String(120), default="Junior AI Engineer")
    background: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(Text)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(40))  # interview, hr, assessment, english, academy, coding, project, revision
    job_role: Mapped[str] = mapped_column(String(120), default="")
    difficulty: Mapped[str] = mapped_column(String(40), default="Beginner")
    category: Mapped[str] = mapped_column(String(60), default="")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    planned_questions: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="active")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    agent: Mapped[str] = mapped_column(String(60), default="")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20), default="new")  # new / follow_up / revision
    difficulty: Mapped[str] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(60))
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), index=True)
    answer: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String(10), default="text")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    scores: Mapped[dict] = mapped_column(JSON)  # the 10-category scorecard
    total: Mapped[float] = mapped_column(Float)  # out of 100
    technical: Mapped[dict] = mapped_column(JSON)
    communication: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class TechnicalSkill(Base):
    __tablename__ = "technical_skills"
    __table_args__ = (UniqueConstraint("user_id", "topic"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(60))
    score_avg: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class CommunicationSkill(Base):
    __tablename__ = "communication_skills"
    __table_args__ = (UniqueConstraint("user_id", "dimension"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(String(60))
    score_avg: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"
    __table_args__ = (UniqueConstraint("user_id", "category", "topic"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # technical / communication / professional
    topic: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(Integer, default=2)  # 1 low .. 3 high
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    recommended_exercise: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[list] = mapped_column(JSON, default=list)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class LearningRoadmap(Base):
    __tablename__ = "learning_roadmaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class DailyProgress(Base):
    __tablename__ = "daily_progress"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[dt.date] = mapped_column(Date)
    answers: Mapped[int] = mapped_column(Integer, default=0)
    total_sum: Mapped[float] = mapped_column(Float, default=0)
    technical_n: Mapped[int] = mapped_column(Integer, default=0)
    technical_sum: Mapped[float] = mapped_column(Float, default=0)
    communication_n: Mapped[int] = mapped_column(Integer, default=0)
    communication_sum: Mapped[float] = mapped_column(Float, default=0)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)
    stats: Mapped[dict] = mapped_column(JSON)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    technologies: Mapped[str] = mapped_column(Text, default="")
    architecture: Mapped[str] = mapped_column(Text, default="")
    challenges: Mapped[str] = mapped_column(Text, default="")
    results: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class EmotionCheck(Base):
    """One reading of how the learner felt/sounded: after an answer, a check-in, or a self-report."""
    __tablename__ = "emotion_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # text / voice / video / checkin
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    self_report: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- engine

_engine = None
_SessionLocal: sessionmaker | None = None


def init_db(url: str | None = None) -> None:
    """Create the engine and tables. Safe to call repeatedly."""
    global _engine, _SessionLocal
    url = url or settings.database_url
    if _engine is not None and str(_engine.url) == url:
        return
    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(url, **kwargs)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    log.info("Database ready (%s)", _engine.url.get_backend_name())


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --------------------------------------------------------------------------- users & settings

def get_or_create_user(name: str, target_role: str = "Junior AI Engineer", background: str = "") -> User:
    name = name.strip()[:120]
    if not name:
        raise ValueError("Name cannot be empty.")
    with session_scope() as s:
        user = s.scalar(select(User).where(User.name == name))
        if user is None:
            user = User(name=name, target_role=target_role, background=background)
            s.add(user)
            s.flush()
        return user


def list_users() -> list[User]:
    with session_scope() as s:
        return list(s.scalars(select(User).order_by(User.name)))


def get_user(user_id: int) -> User | None:
    with session_scope() as s:
        return s.get(User, user_id)


def update_user(user_id: int, **fields: Any) -> None:
    with session_scope() as s:
        user = s.get(User, user_id)
        if user:
            for k, v in fields.items():
                if k in {"target_role", "background", "name"} and v is not None:
                    setattr(user, k, v)


def get_setting(user_id: int, key: str, default: str = "") -> str:
    with session_scope() as s:
        row = s.scalar(select(Setting).where(Setting.user_id == user_id, Setting.key == key))
        return row.value if row else default


def set_setting(user_id: int, key: str, value: str) -> None:
    with session_scope() as s:
        row = s.scalar(select(Setting).where(Setting.user_id == user_id, Setting.key == key))
        if row:
            row.value = value
        else:
            s.add(Setting(user_id=user_id, key=key, value=value))


# --------------------------------------------------------------------------- sessions & questions

def create_session(user_id: int, module: str, **fields: Any) -> InterviewSession:
    with session_scope() as s:
        sess = InterviewSession(user_id=user_id, module=module, **fields)
        s.add(sess)
        s.flush()
        return sess


def get_session(session_id: int) -> InterviewSession | None:
    with session_scope() as s:
        return s.get(InterviewSession, session_id)


def update_session(session_id: int, **fields: Any) -> None:
    with session_scope() as s:
        sess = s.get(InterviewSession, session_id)
        if sess:
            for k, v in fields.items():
                if k in {"difficulty", "context", "status", "planned_questions"}:
                    setattr(sess, k, v)


def end_session(session_id: int, summary: dict | None = None) -> None:
    with session_scope() as s:
        sess = s.get(InterviewSession, session_id)
        if sess and sess.status != "completed":
            sess.status = "completed"
            sess.ended_at = utcnow()
            sess.summary = summary


def add_message(user_id: int, session_id: int | None, role: str, content: str, agent: str = "") -> None:
    with session_scope() as s:
        s.add(Conversation(user_id=user_id, session_id=session_id, role=role, content=content, agent=agent))


META_AGENTS = ("feedback", "presence_coach", "confidence_coach")  # coaching notes saved in the transcript, not dialogue turns


def get_messages(session_id: int, include_meta: bool = False) -> list[Conversation]:
    """Dialogue for a session. Coaching notes (scores, presence tips) are left out unless include_meta."""
    with session_scope() as s:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        if not include_meta:
            stmt = stmt.where(Conversation.agent.not_in(META_AGENTS))
        return list(s.scalars(stmt.order_by(Conversation.id)))


# --------------------------------------------------------------------------- emotions & confidence

MOODS = ["😣 Very anxious", "😟 Nervous", "😐 Okay", "🙂 Good", "😄 Confident"]


def add_emotion_check(user_id: int, session_id: int | None, source: str, signals: dict | None = None,
                      result: dict | None = None, self_report: str = "") -> int:
    with session_scope() as s:
        row = EmotionCheck(user_id=user_id, session_id=session_id, source=source[:20], signals=signals or {},
                           result=result or {}, self_report=self_report[:500])
        s.add(row)
        s.flush()
        return row.id


def set_self_report(check_id: int, user_id: int, report: str) -> bool:
    with session_scope() as s:
        row = s.get(EmotionCheck, check_id)
        if row is None or row.user_id != user_id:
            return False
        row.self_report = report[:500]
        return True


def add_checkin(user_id: int, mood: int, note: str = "") -> int:
    mood = max(0, min(4, int(mood)))
    label = MOODS[mood]
    text = f"Check-in: felt {label.split(' ', 1)[1].lower()}" + (f" - {note.strip()[:300]}" if note.strip() else "")
    return add_emotion_check(user_id, None, "checkin", {"mood": mood}, {"mood": mood, "mood_label": label}, text)


def emotion_history(user_id: int, limit: int = 200) -> list[dict]:
    """Oldest first, as plain dicts."""
    with session_scope() as s:
        rows = list(s.scalars(select(EmotionCheck).where(EmotionCheck.user_id == user_id)
                              .order_by(EmotionCheck.created_at.desc(), EmotionCheck.id.desc()).limit(limit)))
    out = []
    for r in reversed(rows):
        res = r.result or {}
        out.append({"id": r.id, "at": r.created_at, "when": f"{r.created_at:%d %b %H:%M}", "source": r.source,
                    "session_id": r.session_id, "primary_emotion": res.get("primary_emotion"),
                    "confidence": res.get("confidence"), "calm": res.get("calm"),
                    "fear_of_speaking": res.get("fear_of_speaking"), "energy": res.get("energy"),
                    "mood": res.get("mood"), "self_report": r.self_report,
                    "voice": (r.signals or {}).get("voice") or {}, "text": (r.signals or {}).get("text") or {}})
    return out


def self_reports(user_id: int, limit: int = 12) -> list[str]:
    return [f"{h['when']}: {h['self_report']}" for h in emotion_history(user_id, 60) if h["self_report"]][-limit:]


def conversation_index(user_id: int, module: str | None = None, search: str = "", limit: int = 200) -> list[dict]:
    """Sessions that have a saved conversation, newest first, with message counts and a preview."""
    search = (search or "").strip()
    with session_scope() as s:
        stmt = select(InterviewSession).where(InterviewSession.user_id == user_id)
        if module:
            stmt = stmt.where(InterviewSession.module == module)
        if search:
            hits = select(Conversation.session_id).where(Conversation.user_id == user_id,
                                                         Conversation.content.ilike(f"%{search[:200]}%"))
            stmt = stmt.where(InterviewSession.id.in_(hits))
        sessions = list(s.scalars(stmt.order_by(InterviewSession.started_at.desc()).limit(limit)))
        out = []
        for sess in sessions:
            msgs = list(s.scalars(select(Conversation).where(Conversation.session_id == sess.id)
                                  .order_by(Conversation.id)))
            if not msgs:
                continue
            first = next((m.content for m in msgs if m.role == "assistant" and m.agent not in META_AGENTS), msgs[0].content)
            out.append({"id": sess.id, "module": sess.module, "category": sess.category, "status": sess.status,
                        "started_at": sess.started_at, "ended_at": sess.ended_at,
                        "messages": sum(1 for m in msgs if m.agent not in META_AGENTS),
                        "answers": sum(1 for m in msgs if m.role == "user"),
                        "average": (sess.summary or {}).get("average"), "preview": first[:160]})
        return out


def delete_session(session_id: int, user_id: int) -> bool:
    """Delete one session and everything recorded in it. Only the owner can delete."""
    with session_scope() as s:
        sess = s.get(InterviewSession, session_id)
        if sess is None or sess.user_id != user_id:
            return False
        q_ids = [x.id for x in s.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == session_id))]
        for r in s.scalars(select(AnswerEvaluation).where(AnswerEvaluation.question_id.in_(q_ids or [-1]))):
            s.delete(r)
        for model in (InterviewQuestion, Conversation, EmotionCheck):
            for r in s.scalars(select(model).where(model.session_id == session_id)):
                s.delete(r)
        s.delete(sess)
        return True


def add_question(session_id: int, question: str, topic: str, kind: str, difficulty: str, agent: str, extra: dict | None = None) -> InterviewQuestion:
    with session_scope() as s:
        pos = (s.scalar(select(func.count(InterviewQuestion.id)).where(InterviewQuestion.session_id == session_id)) or 0) + 1
        q = InterviewQuestion(session_id=session_id, position=pos, question=question, topic=normalize_topic(topic),
                              kind=kind, difficulty=difficulty, agent=agent, extra=extra or {})
        s.add(q)
        s.flush()
        return q


def get_question(question_id: int) -> InterviewQuestion | None:
    with session_scope() as s:
        return s.get(InterviewQuestion, question_id)


def session_questions(session_id: int) -> list[InterviewQuestion]:
    with session_scope() as s:
        return list(s.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.position)))


# --------------------------------------------------------------------------- evaluations

TECH_DIMS = ["technical_accuracy", "conceptual_understanding", "practical_knowledge"]
COMM_DIMS = ["english_grammar", "vocabulary", "sentence_structure", "fluency_clarity", "confidence",
             "professional_communication"]
SCORE_DIMS = TECH_DIMS + COMM_DIMS + ["overall_interview_performance"]
# The 10-category scorecard, in display order
SCORECARD = ["technical_accuracy", "conceptual_understanding", "practical_knowledge", "english_grammar", "vocabulary",
             "sentence_structure", "fluency_clarity", "confidence", "professional_communication",
             "overall_interview_performance"]


def score_total(scores: dict) -> float:
    """Total out of 100. Categories that do not apply (None) are excluded, then rescaled to 100."""
    vals = [scores[k] for k in SCORECARD if scores.get(k) is not None]
    return round(sum(vals) / len(vals) * 10, 1) if vals else 0.0


def _rolling(avg: float, n: int, new: float) -> float:
    return (avg * n + new) / (n + 1)


def save_evaluation(user_id: int, question_id: int, answer: str, input_mode: str, scores: dict,
                    total: float, technical: dict, communication: dict, topic: str,
                    count_technical: bool = True) -> AnswerEvaluation:
    with session_scope() as s:
        attempt = (s.scalar(select(func.count(AnswerEvaluation.id)).where(AnswerEvaluation.question_id == question_id)) or 0) + 1
        ev = AnswerEvaluation(user_id=user_id, question_id=question_id, answer=answer, input_mode=input_mode,
                              attempt=attempt, scores=scores, total=total, technical=technical, communication=communication)
        s.add(ev)

        tech_vals = [scores.get(k) for k in TECH_DIMS if scores.get(k) is not None]
        comm_vals = [scores.get(k) for k in COMM_DIMS if scores.get(k) is not None]
        tech_score = sum(tech_vals) / len(tech_vals) if tech_vals else None
        comm_score = sum(comm_vals) / len(comm_vals) if comm_vals else None

        if count_technical and tech_score is not None:
            ts = s.scalar(select(TechnicalSkill).where(TechnicalSkill.user_id == user_id, TechnicalSkill.topic == topic))
            if ts is None:
                ts = TechnicalSkill(user_id=user_id, topic=topic, score_avg=0, attempts=0)
                s.add(ts)
            ts.score_avg = _rolling(ts.score_avg, ts.attempts, tech_score)
            ts.attempts += 1
            ts.updated_at = utcnow()

        for d in COMM_DIMS:
            if scores.get(d) is None:
                continue
            cs = s.scalar(select(CommunicationSkill).where(CommunicationSkill.user_id == user_id, CommunicationSkill.dimension == d))
            if cs is None:
                cs = CommunicationSkill(user_id=user_id, dimension=d, score_avg=0, attempts=0)
                s.add(cs)
            cs.score_avg = _rolling(cs.score_avg, cs.attempts, scores[d])
            cs.attempts += 1
            cs.updated_at = utcnow()

        today = dt.date.today()
        dp = s.scalar(select(DailyProgress).where(DailyProgress.user_id == user_id, DailyProgress.day == today))
        if dp is None:
            dp = DailyProgress(user_id=user_id, day=today, answers=0, total_sum=0, technical_n=0,
                               technical_sum=0, communication_n=0, communication_sum=0)
            s.add(dp)
        dp.answers += 1
        dp.total_sum += total
        if tech_score is not None:
            dp.technical_n += 1
            dp.technical_sum += tech_score
        if comm_score is not None:
            dp.communication_n += 1
            dp.communication_sum += comm_score
        s.flush()
        return ev


def evaluations_for_user(user_id: int, since: dt.datetime | None = None) -> list[tuple[AnswerEvaluation, InterviewQuestion, InterviewSession]]:
    with session_scope() as s:
        stmt = (select(AnswerEvaluation, InterviewQuestion, InterviewSession)
                .join(InterviewQuestion, AnswerEvaluation.question_id == InterviewQuestion.id)
                .join(InterviewSession, InterviewQuestion.session_id == InterviewSession.id)
                .where(AnswerEvaluation.user_id == user_id)
                .order_by(AnswerEvaluation.created_at))
        if since:
            stmt = stmt.where(AnswerEvaluation.created_at >= since)
        return [tuple(r) for r in s.execute(stmt).all()]  # type: ignore[misc]


def evaluations_for_session(session_id: int) -> list[tuple[AnswerEvaluation, InterviewQuestion]]:
    with session_scope() as s:
        stmt = (select(AnswerEvaluation, InterviewQuestion)
                .join(InterviewQuestion, AnswerEvaluation.question_id == InterviewQuestion.id)
                .where(InterviewQuestion.session_id == session_id)
                .order_by(AnswerEvaluation.id))
        return [tuple(r) for r in s.execute(stmt).all()]  # type: ignore[misc]


def technical_skills(user_id: int) -> list[TechnicalSkill]:
    with session_scope() as s:
        return list(s.scalars(select(TechnicalSkill).where(TechnicalSkill.user_id == user_id)))


def communication_skills(user_id: int) -> list[CommunicationSkill]:
    with session_scope() as s:
        return list(s.scalars(select(CommunicationSkill).where(CommunicationSkill.user_id == user_id)))


def daily_progress(user_id: int) -> list[DailyProgress]:
    with session_scope() as s:
        return list(s.scalars(select(DailyProgress).where(DailyProgress.user_id == user_id).order_by(DailyProgress.day)))


def list_sessions(user_id: int, limit: int = 100) -> list[InterviewSession]:
    with session_scope() as s:
        return list(s.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id)
                              .order_by(InterviewSession.started_at.desc()).limit(limit)))


# --------------------------------------------------------------------------- knowledge gaps

PRIORITY_THRESHOLD = 2  # a weakness seen this many times becomes a priority


def record_gap(user_id: int, category: str, topic: str, description: str, severity: int,
               exercise: str = "", example: str = "") -> KnowledgeGap:
    category = category if category in {"technical", "communication", "professional"} else "technical"
    topic = normalize_topic(topic)
    severity = max(1, min(3, int(severity or 2)))
    with session_scope() as s:
        gap = s.scalar(select(KnowledgeGap).where(KnowledgeGap.user_id == user_id, KnowledgeGap.category == category,
                                                  KnowledgeGap.topic == topic))
        if gap is None:
            gap = KnowledgeGap(user_id=user_id, category=category, topic=topic, description=description,
                               severity=severity, occurrences=1, recommended_exercise=exercise,
                               examples=[example] if example else [])
            s.add(gap)
        else:
            gap.occurrences += 1
            gap.description = description or gap.description
            gap.severity = max(gap.severity, severity)
            gap.recommended_exercise = exercise or gap.recommended_exercise
            gap.last_seen = utcnow()
            gap.status = "open"  # a resolved gap that reappears is reopened
            if example:
                gap.examples = (list(gap.examples or []) + [example])[-5:]
        gap.priority = gap.occurrences >= PRIORITY_THRESHOLD
        s.flush()
        return gap


def list_gaps(user_id: int, status: str | None = "open") -> list[KnowledgeGap]:
    with session_scope() as s:
        stmt = select(KnowledgeGap).where(KnowledgeGap.user_id == user_id)
        if status:
            stmt = stmt.where(KnowledgeGap.status == status)
        stmt = stmt.order_by(KnowledgeGap.priority.desc(), KnowledgeGap.occurrences.desc(), KnowledgeGap.severity.desc())
        return list(s.scalars(stmt))


def set_gap_status(gap_id: int, user_id: int, status: str) -> None:
    with session_scope() as s:
        gap = s.get(KnowledgeGap, gap_id)
        if gap and gap.user_id == user_id:
            gap.status = status


# --------------------------------------------------------------------------- roadmap, reports, projects

def save_roadmap(user_id: int, content: dict, rationale: str = "", start_date: dt.date | None = None) -> LearningRoadmap:
    with session_scope() as s:
        for r in s.scalars(select(LearningRoadmap).where(LearningRoadmap.user_id == user_id, LearningRoadmap.is_active)):
            r.is_active = False
            start_date = start_date or r.start_date  # keep the original day-1 when adjusting
        rm = LearningRoadmap(user_id=user_id, content=content, rationale=rationale, is_active=True,
                             start_date=start_date or dt.date.today())
        s.add(rm)
        s.flush()
        return rm


def active_roadmap(user_id: int) -> LearningRoadmap | None:
    with session_scope() as s:
        return s.scalar(select(LearningRoadmap).where(LearningRoadmap.user_id == user_id, LearningRoadmap.is_active)
                        .order_by(LearningRoadmap.id.desc()))


def save_report(user_id: int, start: dt.date, end: dt.date, stats: dict, content: dict) -> WeeklyReport:
    with session_scope() as s:
        r = WeeklyReport(user_id=user_id, period_start=start, period_end=end, stats=stats, content=content)
        s.add(r)
        s.flush()
        return r


def list_reports(user_id: int) -> list[WeeklyReport]:
    with session_scope() as s:
        return list(s.scalars(select(WeeklyReport).where(WeeklyReport.user_id == user_id).order_by(WeeklyReport.id.desc())))


def save_project(user_id: int, project_id: int | None = None, **fields: Any) -> Project:
    allowed = {"title", "description", "technologies", "architecture", "challenges", "results"}
    data = {k: (v or "").strip() for k, v in fields.items() if k in allowed}
    if not data.get("title"):
        raise ValueError("Project title is required.")
    with session_scope() as s:
        if project_id:
            p = s.get(Project, project_id)
            if p is None or p.user_id != user_id:
                raise ValueError("Project not found.")
            for k, v in data.items():
                setattr(p, k, v)
        else:
            p = Project(user_id=user_id, **data)
            s.add(p)
        s.flush()
        return p


def list_projects(user_id: int) -> list[Project]:
    with session_scope() as s:
        return list(s.scalars(select(Project).where(Project.user_id == user_id).order_by(Project.id.desc())))


def delete_project(project_id: int, user_id: int) -> None:
    with session_scope() as s:
        p = s.get(Project, project_id)
        if p and p.user_id == user_id:
            s.delete(p)


# --------------------------------------------------------------------------- export / delete

def _row(obj: Any) -> dict:
    out = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.name)
        out[col.name] = v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v
    return out


def export_user_data(user_id: int) -> dict:
    """Everything stored about a user, as plain JSON-serialisable dicts."""
    with session_scope() as s:
        user = s.get(User, user_id)
        if user is None:
            return {}
        session_ids = [x.id for x in s.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id))]
        data: dict[str, Any] = {"user": _row(user), "exported_at": utcnow().isoformat()}
        simple = {
            "settings": Setting, "interview_sessions": InterviewSession, "conversations": Conversation,
            "answer_evaluations": AnswerEvaluation, "technical_skills": TechnicalSkill,
            "communication_skills": CommunicationSkill, "knowledge_gaps": KnowledgeGap,
            "learning_roadmaps": LearningRoadmap, "daily_progress": DailyProgress,
            "weekly_reports": WeeklyReport, "projects": Project, "emotion_checks": EmotionCheck,
        }
        for name, model in simple.items():
            data[name] = [_row(r) for r in s.scalars(select(model).where(model.user_id == user_id))]
        data["settings"] = [r for r in data["settings"] if r.get("key") != "pin_hash"]
        data["interview_questions"] = [_row(r) for r in s.scalars(
            select(InterviewQuestion).where(InterviewQuestion.session_id.in_(session_ids or [-1])))]
        return data


def delete_user_data(user_id: int) -> None:
    with session_scope() as s:
        session_ids = [x.id for x in s.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id))]
        q_ids = [x.id for x in s.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id.in_(session_ids or [-1])))]
        for model in (AnswerEvaluation,):
            for r in s.scalars(select(model).where(model.question_id.in_(q_ids or [-1]))):
                s.delete(r)
        for r in s.scalars(select(InterviewQuestion).where(InterviewQuestion.id.in_(q_ids or [-1]))):
            s.delete(r)
        for model in (EmotionCheck, Conversation, Setting, TechnicalSkill, CommunicationSkill, KnowledgeGap,
                      LearningRoadmap, DailyProgress, WeeklyReport, Project, InterviewSession):
            for r in s.scalars(select(model).where(model.user_id == user_id)):
                s.delete(r)
        user = s.get(User, user_id)
        if user:
            s.delete(user)


# --------------------------------------------------------------------------- profile PIN (optional)

def _pin_hash(pin: str, salt: bytes) -> str:
    import hashlib

    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()


def set_pin(user_id: int, pin: str) -> None:
    """Store a salted PBKDF2 hash of a 4-8 digit PIN. An empty PIN removes protection."""
    import os

    pin = (pin or "").strip()
    if not pin:
        set_setting(user_id, "pin_hash", "")
        return
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise ValueError("The PIN must be 4 to 8 digits.")
    salt = os.urandom(16)
    set_setting(user_id, "pin_hash", f"{salt.hex()}${_pin_hash(pin, salt)}")


def has_pin(user_id: int) -> bool:
    return bool(get_setting(user_id, "pin_hash", ""))


def check_pin(user_id: int, pin: str) -> bool:
    import hmac

    stored = get_setting(user_id, "pin_hash", "")
    if not stored:
        return True
    salt_hex, _, digest = stored.partition("$")
    try:
        return hmac.compare_digest(_pin_hash((pin or "").strip(), bytes.fromhex(salt_hex)), digest)
    except ValueError:
        return False
