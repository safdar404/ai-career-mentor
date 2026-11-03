"""Deterministic analytics computed from stored evaluations.

Nothing here calls an LLM. If there is no data, functions return None or empty
results and the UI shows an empty state instead of a made-up number.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from statistics import mean
from typing import Any

import db
from topics import GROUP_LABELS, group_of


def _mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(mean(vals), 1) if vals else None


def _tech(scores: dict) -> float | None:
    vals = [scores.get(k) for k in db.TECH_DIMS if scores.get(k) is not None]
    return mean(vals) if vals else None


def _comm(scores: dict) -> float | None:
    vals = [scores.get(k) for k in db.COMM_DIMS if scores.get(k) is not None]
    return mean(vals) if vals else None


def dashboard_metrics(user_id: int) -> dict[str, dict[str, Any]]:
    rows = db.evaluations_for_user(user_id)
    recent = rows[-20:]

    def by_groups(groups: set[str], modules: set[str] | None = None) -> list[float]:
        out = []
        for ev, q, sess in rows:
            if group_of(q.topic) in groups or (modules and sess.module in modules):
                t = _tech(ev.scores)
                if t is not None:
                    out.append(t * 10)
        return out

    def metric(vals: list[float], n_label: str = "answers") -> dict[str, Any]:
        vals = [v for v in vals if v is not None]
        return {"value": _mean(vals), "n": len(vals), "unit": n_label}

    return {
        "Interview readiness": metric([ev.total for ev, _, _ in recent]),
        "Technical knowledge": metric([_tech(ev.scores) * 10 for ev, _, _ in rows if _tech(ev.scores) is not None]),
        "English communication": metric([_comm(ev.scores) * 10 for ev, _, _ in rows if _comm(ev.scores) is not None]),
        "Python skills": metric(by_groups({"python", "python_libs"}, {"coding"})),
        "Generative AI": metric(by_groups({"genai"})),
        "Agentic AI": metric(by_groups({"agentic"})),
        "Problem solving": metric([ev.scores["practical_knowledge"] * 10 for ev, _, _ in rows
                                   if ev.scores.get("practical_knowledge") is not None]),
        "Interview confidence": metric([ev.scores["confidence"] * 10 for ev, _, _ in rows
                                        if ev.scores.get("confidence") is not None]),
    }


def daily_trend(user_id: int) -> list[dict]:
    out = []
    for d in db.daily_progress(user_id):
        out.append({
            "day": d.day,
            "answers": d.answers,
            "overall": round(d.total_sum / d.answers, 1) if d.answers else None,
            "technical": round(d.technical_sum / d.technical_n * 10, 1) if d.technical_n else None,
            "communication": round(d.communication_sum / d.communication_n * 10, 1) if d.communication_n else None,
        })
    return out


def week_comparison(user_id: int, today: dt.date | None = None) -> dict[str, float | None]:
    today = today or dt.date.today()
    this_start = today - dt.timedelta(days=6)
    prev_start = this_start - dt.timedelta(days=7)
    this, prev = [], []
    for ev, _, _ in db.evaluations_for_user(user_id):
        d = ev.created_at.date()
        if this_start <= d <= today:
            this.append(ev.total)
        elif prev_start <= d < this_start:
            prev.append(ev.total)
    a, b = _mean(this), _mean(prev)
    return {"this_week": a, "last_week": b, "this_n": len(this), "last_n": len(prev),
            "change": round(a - b, 1) if a is not None and b is not None else None}


def topic_strengths(user_id: int, min_attempts: int = 1) -> tuple[list[dict], list[dict]]:
    skills = [s for s in db.technical_skills(user_id) if s.attempts >= min_attempts]
    rows = [{"topic": s.topic, "group": GROUP_LABELS.get(group_of(s.topic), "Other"),
             "score": round(s.score_avg * 10, 1), "attempts": s.attempts} for s in skills]
    rows.sort(key=lambda r: r["score"], reverse=True)
    strongest = [r for r in rows if r["score"] >= 60][:5]
    weakest = sorted([r for r in rows if r["score"] < 60], key=lambda r: r["score"])[:5]
    return strongest, weakest


def group_scores(user_id: int) -> list[dict]:
    agg: dict[str, list[tuple[float, int]]] = {}
    for s in db.technical_skills(user_id):
        agg.setdefault(group_of(s.topic), []).append((s.score_avg, s.attempts))
    out = []
    for g, vals in agg.items():
        n = sum(a for _, a in vals)
        out.append({"group": GROUP_LABELS.get(g, g), "score": round(sum(v * a for v, a in vals) / n * 10, 1), "answers": n})
    return sorted(out, key=lambda r: r["score"])


def training_minutes(user_id: int) -> float:
    """Session time from start to end (or last answer), capped at 2 hours per session."""
    last_answer: dict[int, dt.datetime] = {}
    for ev, _, sess in db.evaluations_for_user(user_id):
        last_answer[sess.id] = max(last_answer.get(sess.id, ev.created_at), ev.created_at)
    total = 0.0
    for sess in db.list_sessions(user_id, limit=10_000):
        end = sess.ended_at or last_answer.get(sess.id)
        if end:
            total += min(max((end - sess.started_at).total_seconds() / 60, 0), 120)
    return round(total, 1)


def interview_history(user_id: int, limit: int = 30) -> list[dict]:
    sessions = db.list_sessions(user_id, limit=limit)
    out = []
    for s in sessions:
        evs = db.evaluations_for_session(s.id)
        out.append({"id": s.id, "date": s.started_at.strftime("%Y-%m-%d %H:%M"), "module": s.module,
                    "role": s.job_role, "category": s.category, "difficulty": s.difficulty,
                    "answers": len(evs), "avg_score": _mean([e.total for e, _ in evs]), "status": s.status})
    return out


def period_stats(user_id: int, start: dt.date, end: dt.date) -> dict[str, Any]:
    """Facts for one reporting period, plus the previous period of the same length for comparison."""
    length = (end - start).days + 1
    prev_start, prev_end = start - dt.timedelta(days=length), start - dt.timedelta(days=1)
    rows = db.evaluations_for_user(user_id)

    def summarise(a: dt.date, b: dt.date) -> dict[str, Any]:
        sel = [(ev, q, s) for ev, q, s in rows if a <= ev.created_at.date() <= b]
        if not sel:
            return {"answers": 0}
        dims = {k: _mean([ev.scores.get(k) for ev, _, _ in sel]) for k in db.SCORECARD}
        groups: dict[str, list[float]] = {}
        for ev, q, _ in sel:
            t = _tech(ev.scores)
            if t is not None:
                groups.setdefault(GROUP_LABELS.get(group_of(q.topic), "Other"), []).append(t * 10)
        grammar = Counter()
        vocab: list[str] = []
        for ev, _, _ in sel:
            for m in (ev.communication or {}).get("grammar_mistakes", []):
                if m.get("explanation"):
                    grammar[m["explanation"][:120]] += 1
            vocab += [v.get("term", "") for v in (ev.communication or {}).get("new_vocabulary", []) if v.get("term")]
        unanswered = [q.question for ev, q, _ in sel
                      if not (ev.technical or {}).get("attempted", True) or (_tech(ev.scores) or 10) <= 3]
        return {
            "answers": len(sel),
            "sessions": len({s.id for _, _, s in sel}),
            "average_total": _mean([ev.total for ev, _, _ in sel]),
            "dimension_averages_out_of_10": dims,
            "technical_by_area_out_of_100": {g: _mean(v) for g, v in groups.items()},
            "frequent_grammar_issues": grammar.most_common(6),
            "vocabulary_introduced": sorted(set(vocab))[:30],
            "questions_scored_3_or_less": unanswered[:10],
        }

    gaps = [{"category": g.category, "topic": g.topic, "description": g.description, "occurrences": g.occurrences,
             "priority": g.priority} for g in db.list_gaps(user_id)]
    return {"period": f"{start} to {end}", "current": summarise(start, end),
            "previous_period": {"period": f"{prev_start} to {prev_end}", **summarise(prev_start, prev_end)},
            "open_gaps": gaps[:15], "training_minutes_all_time": training_minutes(user_id)}


# --------------------------------------------------------------------------- roadmap

BASE_ROADMAP = {"phases": [
    {"phase": "English communication and Python fundamentals", "days": "1-15",
     "focus": "Self-introduction, everyday professional English, core Python",
     "goals": ["Deliver a confident 1-minute self-introduction", "Answer Python fundamentals and OOP questions clearly"],
     "daily_activities": ["English Lab: 2 role-play turns", "Live Interview: 5 Python questions", "Coding Lab: 1 challenge"],
     "milestone": "Average 60+ on Python fundamentals and self-introduction"},
    {"phase": "Machine learning and AI concepts", "days": "16-30",
     "focus": "Supervised/unsupervised learning, evaluation, overfitting, deep learning basics",
     "goals": ["Explain ML concepts in simple English", "Discuss model evaluation trade-offs"],
     "daily_activities": ["Academy: 1 concept explained back", "Technical Assessment: ML", "English Lab: Technical English"],
     "milestone": "Average 60+ on machine learning topics"},
    {"phase": "Generative AI, LLMs and RAG", "days": "31-45",
     "focus": "Transformers, tokens, embeddings, prompting, RAG, vector databases, hallucinations",
     "goals": ["Design and explain a RAG pipeline end to end", "Compare RAG with fine-tuning"],
     "daily_activities": ["Generative AI Academy lesson", "Live Interview: Generative AI Engineer", "Coding Lab: retrieval"],
     "milestone": "Average 65+ on Generative AI topics"},
    {"phase": "Agentic AI and multi-agent architecture", "days": "46-60",
     "focus": "Tool calling, memory, planning, orchestration, human-in-the-loop, evaluation, safety",
     "goals": ["Explain an agent loop with tool calling", "Defend an orchestration design"],
     "daily_activities": ["Agentic AI Academy lesson", "System Design interview", "Revision session on priority gaps"],
     "milestone": "Average 65+ on Agentic AI topics"},
    {"phase": "Streamlit, APIs, Docker and automation", "days": "61-75",
     "focus": "FastAPI, REST, Docker and Compose, deployment, n8n/Zapier/Make webhooks",
     "goals": ["Explain how your app is containerised and deployed", "Design an AI automation workflow"],
     "daily_activities": ["Technical Assessment: deployment", "Project Presentation Trainer", "Coding Lab"],
     "milestone": "Can explain a full deployment of one of your projects"},
    {"phase": "Project presentations and international mock interviews", "days": "76-90",
     "focus": "30s/1m/3m/5m project pitches, complete mock interviews, HR and salary conversations",
     "goals": ["Pass three complete mock interviews at 70+", "Answer 'Why should we hire you?' convincingly"],
     "daily_activities": ["Complete Interview", "HR Interview Simulator", "Project pitch practice"],
     "milestone": "Consistent 70+ on complete interviews"},
]}


def roadmap_day(start: dt.date, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return max(1, min(90, (today - start).days + 1))


def skill_summary_text(user_id: int) -> str:
    groups = group_scores(user_id)
    metrics = dashboard_metrics(user_id)
    gaps = db.list_gaps(user_id)
    lines = ["Area scores (out of 100, from real answers):"]
    lines += [f"- {g['group']}: {g['score']} ({g['answers']} answers)" for g in groups] or ["- no technical answers yet"]
    lines.append("Overall metrics:")
    lines += [f"- {k}: {v['value'] if v['value'] is not None else 'no data'} ({v['n']} answers)" for k, v in metrics.items()]
    lines.append("Open weaknesses:")
    lines += [f"- [{g.category}] {g.topic}: {g.description} (x{g.occurrences}{', PRIORITY' if g.priority else ''})"
              for g in gaps[:15]] or ["- none recorded"]
    return "\n".join(lines)
