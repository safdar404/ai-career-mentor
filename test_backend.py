import datetime as dt

import pytest

import analytics, db
from llm import LLMError, complete_json, extract_json, get_provider
from config import Settings
from orchestrator import Orchestrator, ValidationError, check_syntax, pitch_length_feedback
from fake_provider import FakeProvider


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db._engine = None
    db.init_db(f"sqlite:///{tmp_path / 'test.db'}")
    yield


@pytest.fixture
def user():
    return db.get_or_create_user("Muhammad Safdar", "Junior AI Engineer", "GIS + Python")


def test_empty_dashboard_has_no_fake_numbers(user):
    m = analytics.dashboard_metrics(user.id)
    assert all(v["value"] is None and v["n"] == 0 for v in m.values())
    assert analytics.daily_trend(user.id) == []
    assert analytics.training_minutes(user.id) == 0


def test_interview_flow_scores_and_gaps(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 2)
    assert q["question"] and q["topic"] == "genai.rag"
    res = orch.submit_answer(sid, q["id"], "I am having experience with RAG, it retrieves documents.")
    assert set(res["scores"]) == set(db.SCORECARD)
    # 4 technical scores of 7 (28) + comm 6,6,5,6,5,6 (34) = 62 over 10 categories -> 62
    assert res["total"] == 62.0
    assert res["lesson"] is None
    assert {g["topic"] for g in res["gaps"]} == {"genai.rag", "comm.grammar"}
    assert not res["complete"]

    q2 = orch.next_question(sid)
    res2 = orch.submit_answer(sid, q2["id"], "Second answer about RAG.")
    assert res2["complete"]
    gaps = db.list_gaps(user.id)
    rag = [g for g in gaps if g.topic == "genai.rag"][0]
    assert rag.occurrences == 2 and rag.priority  # repeated weakness becomes a priority

    summary = orch.end_session(sid)
    assert summary["headline"] == "Solid start" and summary["answers"] == 2
    m = analytics.dashboard_metrics(user.id)
    assert m["Interview readiness"]["value"] == 62.0 and m["Interview readiness"]["n"] == 2
    assert m["Generative AI"]["value"] == 70.0


def test_weak_answer_triggers_teaching_and_retest(user):
    orch = Orchestrator(provider=FakeProvider(weak=True))
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Intermediate", "Technical", 5)
    res = orch.submit_answer(sid, q["id"], "I don't know")
    assert res["lesson"] and res["lesson"]["title"] == "RAG"
    q2 = orch.next_question(sid)
    assert q2["kind"] == "revision" and q2["topic"] == q["topic"]
    # second weak answer: lower difficulty after two weak answers
    res2 = orch.submit_answer(sid, q2["id"], "still not sure")
    assert res2["new_difficulty"] == "Beginner"
    # no infinite revision loop on the same topic
    q3 = orch.next_question(sid)
    assert q3["kind"] != "revision" or q3["topic"] != q["topic"]


def test_complete_interview_starts_with_hr_self_intro(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Complete Interview", 5)
    assert q["topic"] == "pro.self_intro"
    res = orch.submit_answer(sid, q["id"], "I am Muhammad, I worked in GIS and now build AI apps.")
    assert res["technical"]["star"] is not None
    # behavioural answers do not count toward technical topic skills
    assert db.technical_skills(user.id) == []


def test_english_lab_has_no_technical_scores(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, turn = orch.start_english(user.id, "Daily conversation", "British English")
    assert turn["question"].startswith("Morning")
    res = orch.submit_english(sid, turn["id"], "It was good, I am went to my village.")
    assert res["scores"]["technical_accuracy"] is None
    assert res["total"] == round((6 + 6 + 5 + 6 + 5 + 6) / 6 * 10, 1)
    again = orch.submit_english(sid, turn["id"], "It was great, thanks. I went to my village.")
    assert again["attempt"] == 2


def test_coding_lab_static_review(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, ch = orch.start_coding(user.id, "python.functions", "Beginner")
    assert ch["challenge"]["starter_code"]
    res = orch.submit_code(sid, ch["id"], "def chunk(t, s, o):\n    return [t[i:i+s] for i in range(0, len(t), s-o)]")
    assert res["syntax_error"] is None and res["scores"]["english_grammar"] is None
    assert check_syntax("def f(:\n") is not None


def test_academy_and_pitch(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, lesson = orch.start_lesson(user.id, "genai.rag", "Beginner")
    assert lesson["lesson"]["analogy"] == "Open-book exam"
    orch.submit_answer(sid, lesson["id"], "RAG means the model looks things up first.")
    p = db.save_project(user.id, title="GIS RAG assistant", description="Ask questions about land records")
    sid2, pq = orch.start_pitch(user.id, {"title": p.title}, "30 seconds", "American English")
    res = orch.submit_answer(sid2, pq["id"], " ".join(["word"] * 65))
    assert res["pitch"]["verdict"] == "about right" and res["pitch"]["estimated_seconds"] == 30


def test_validation_and_isolation(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    with pytest.raises(ValidationError):
        orch.submit_answer(sid, q["id"], "   ")
    other = db.get_or_create_user("Someone Else")
    sid2, q2 = orch.start_session(other.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    with pytest.raises(ValidationError):
        orch.submit_answer(sid, q2["id"], "answer to someone else's question")


def test_weekly_report_requires_real_data(user):
    orch = Orchestrator(provider=FakeProvider())
    with pytest.raises(ValidationError):
        orch.weekly_report(user.id)
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 1)
    orch.submit_answer(sid, q["id"], "An answer")
    rep = orch.weekly_report(user.id)
    assert rep["stats"]["current"]["answers"] == 1
    assert rep["stats"]["previous_period"]["answers"] == 0
    assert rep["content"]["vocabulary_development"] == "Not enough data."


def test_revision_and_roadmap(user):
    orch = Orchestrator(provider=FakeProvider())
    for _ in range(2):
        db.record_gap(user.id, "technical", "genai.embeddings", "Weak on embeddings", 2)
    topics = orch.revision_topics(user.id)
    assert topics == ["genai.embeddings"]
    sid, q = orch.start_session(user.id, "revision", "AI Engineer", "Beginner", "Revision", 2, focus_topics=topics)
    assert q["topic"] == "genai.embeddings"
    rm = orch.adjust_roadmap(user.id)
    assert rm["rationale"] == "Based on gaps"


def test_export_and_delete(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 1)
    orch.submit_answer(sid, q["id"], "An answer")
    data = db.export_user_data(user.id)
    assert len(data["answer_evaluations"]) == 1 and len(data["interview_questions"]) == 1
    db.delete_user_data(user.id)
    assert db.get_user(user.id) is None
    assert db.export_user_data(user.id) == {}


def test_json_repair_and_errors():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here: {"a": 2} done') == {"a": 2}
    fp = FakeProvider(broken_json_once=True)
    # first reply is broken, repair call goes through normal routing -> HR question JSON
    out = complete_json(fp, "Ask exactly ONE behavioural question", [{"role": "user", "content": "x"}])
    assert out["topic"] == "pro.self_intro" and fp.calls[0] == "broken"
    empty = Settings("", "", "anthropic", "m", "m", "s", "t", "sqlite://", "INFO", 6000, 30)
    with pytest.raises(LLMError):
        get_provider(cfg=empty)


def test_pitch_length_helper():
    assert pitch_length_feedback("a " * 10, 60)["verdict"] == "too short"
    assert pitch_length_feedback("a " * 400, 60)["verdict"] == "too long"
