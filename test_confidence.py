"""Tests for the confidence & emotion coach: signals, agent wiring, storage, calibration and UI."""
import io
import wave
from pathlib import Path

import numpy as np
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import db
import prosody
from fake_provider import FakeProvider
from llm import LLMError
from orchestrator import Orchestrator, ValidationError, wellbeing_note

APP = str(Path(__file__).resolve().parent / "app.py")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db._engine = None
    db.init_db(f"sqlite:///{tmp_path / 'c.db'}")
    yield


@pytest.fixture
def user():
    return db.get_or_create_user("Muhammad Safdar", "Junior AI Engineer")


def _wav(segments, rate=16000):
    parts = []
    for kind, sec, f in segments:
        t = np.arange(int(rate * sec)) / rate
        parts.append(0.5 * np.sin(2 * np.pi * f * t) if kind == "tone" else np.zeros_like(t))
    x = np.concatenate(parts) + 0.002 * np.random.default_rng(1).standard_normal(sum(len(p) for p in parts))
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return b.getvalue()


# ----------------------------------------------------------------- signals

def test_text_signals_find_fillers_hedges_and_self_talk():
    t = prosody.text_signals("Um, sorry, I think maybe it is, uh, retrieval. I'm nervous, sorry. I built a RAG app.")
    assert t["fillers"] == {"um": 1, "uh": 1}
    assert {"i think", "maybe"} <= set(t["hedges"])
    assert t["apologies"] == 2
    assert t["negative_self_talk"] == ["i'm nervous"]
    assert t["positive_ownership"] == ["i built"]


def test_words_like_actually_are_not_counted_as_fillers():
    t = prosody.text_signals("I would like to actually deploy it with Docker on Azure because it scales well.")
    assert t["fillers"] == {}


def test_wav_analysis_measures_latency_pauses_and_pitch():
    v = prosody.analyze_wav(_wav([("sil", 4.0, 0), ("tone", 2.0, 150), ("sil", 2.0, 0), ("tone", 2.0, 150)]))
    assert 3.8 <= v["first_word_s"] <= 4.3
    assert v["long_pauses"] == 1
    assert 140 <= v["pitch_hz"] <= 160
    assert v["pitch_variation_st"] < 1  # a steady tone is flat
    obs = prosody.combine("RAG retrieves documents " * 3, v, "voice")["observations"]
    assert any("before the first word" in o for o in obs)


def test_bad_audio_and_hostile_browser_numbers_are_ignored():
    assert prosody.analyze_wav(b"not a wav") == {}
    clean = prosody.clean_live({"duration_s": 12, "long_pauses": -3, "pitch_hz": float("nan"),
                                "loudness_level": 7, "evil": "<script>", "first_word_s": True})
    assert clean == {"duration_s": 12.0}


# ----------------------------------------------------------------- coach in the flow

def test_answer_with_signals_gets_coached_and_stored(user):
    fake = FakeProvider()
    orch = Orchestrator(provider=fake)
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    sig = prosody.combine("Sorry, I'm nervous. RAG retrieves documents, sorry.", {"first_word_s": 5}, "voice")
    res = orch.submit_answer(sid, q["id"], "Sorry, I'm nervous. RAG retrieves documents, sorry.", "voice", signals=sig)
    e = res["emotion"]
    assert e["primary_emotion"] == "nervous" and e["confidence"] == 3 and e["check_id"]
    assert e["technique"]["steps"] and e["reframe"]["better"]
    assert "coach.assess" in fake.calls
    hist = db.emotion_history(user.id)
    assert hist[-1]["primary_emotion"] == "nervous" and hist[-1]["voice"]["first_word_s"] == 5
    # the mentor note is saved in the transcript but is not a dialogue turn
    assert any(m.agent == "confidence_coach" for m in db.get_messages(sid, include_meta=True))
    assert all(m.agent != "confidence_coach" for m in db.get_messages(sid))


def test_coach_off_means_no_emotion_call(user):
    fake = FakeProvider()
    orch = Orchestrator(provider=fake)
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    res = orch.submit_answer(sid, q["id"], "RAG retrieves documents before generation.")
    assert "emotion" not in res and "coach.assess" not in fake.calls
    assert db.emotion_history(user.id) == []


def test_coach_failure_never_loses_the_evaluation(user):
    class Flaky(FakeProvider):
        def complete(self, system, messages, max_tokens=1500, temperature=0.4):
            if "TASK: Read one answer" in system:
                raise LLMError("down")
            return super().complete(system, messages, max_tokens, temperature)

    orch = Orchestrator(provider=Flaky())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    res = orch.submit_answer(sid, q["id"], "RAG retrieves documents.", signals=prosody.combine("RAG retrieves documents."))
    assert res["total"] > 0 and "emotion" not in res


def test_english_lab_is_coached_too(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_english(user.id, "Daily conversation", "British English")
    res = orch.submit_english(sid, q["id"], "It was great, I visited family.", "text",
                              signals=prosody.combine("It was great, I visited family."))
    assert res["emotion"]["primary_emotion"] == "focused"


def test_self_reports_calibrate_and_interviewers_adapt(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    for _ in range(2):
        res = orch.submit_answer(sid, q["id"], "Sorry, I'm nervous.", "voice",
                                 signals=prosody.combine("Sorry, I'm nervous."))
    assert db.set_self_report(res["emotion"]["check_id"], user.id, "I actually felt calmer")
    other = db.get_or_create_user("Someone Else")
    assert not db.set_self_report(res["emotion"]["check_id"], other.id, "hijack")
    assert any("felt calmer" in r for r in db.self_reports(user.id))
    note = orch.context(user.id).block()
    assert "sounded nervous" in note and "warm tone" in note


def test_wellbeing_note_levels():
    assert wellbeing_note([]) == ""
    assert "raise the challenge" in wellbeing_note([{"confidence": 9}, {"confidence": 8}])
    assert "anxious" in wellbeing_note([{"mood": 0, "confidence": None}])


def test_checkin_mentor_chat_and_journey(user):
    orch = Orchestrator(provider=FakeProvider())
    db.add_checkin(user.id, 1, "I freeze on project questions")
    assert "freeze" in db.self_reports(user.id)[-1]
    with pytest.raises(ValidationError):
        orch.confidence_journey(user.id)  # only one data point so far
    sid, out = orch.mentor_chat(user.id, None, "I freeze when they ask about my projects.")
    assert "3-breath reset" in out["reply_text"]
    sid2, _ = orch.mentor_chat(user.id, sid, "Thanks, what else?")
    assert sid2 == sid and [m.role for m in db.get_messages(sid)] == ["user", "assistant", "user", "assistant"]
    assert db.conversation_index(user.id, module="coach")[0]["id"] == sid
    isid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    orch.submit_answer(isid, q["id"], "RAG retrieves.", signals=prosody.combine("RAG retrieves."))
    plan = orch.confidence_journey(user.id)
    assert len(plan["exposure_ladder"]) == 5 and plan["affirmation"]


def test_emotion_data_is_exported_and_deleted(user):
    db.add_checkin(user.id, 3)
    assert db.export_user_data(user.id)["emotion_checks"]
    db.delete_user_data(user.id)
    assert db.emotion_history(user.id) == []


# ----------------------------------------------------------------- UI

_real_init = db.init_db


@pytest.fixture
def ui(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'ui.db'}"
    db._engine = None
    monkeypatch.setattr(db, "init_db", lambda u=None: _real_init(url))
    db.init_db()
    st.cache_resource.clear()
    u = db.get_or_create_user("Muhammad Safdar", "Junior AI Engineer")
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["user_id"] = u.id
    at.session_state["orch::None"] = Orchestrator(provider=FakeProvider())
    return at, u


def _btn(at, label):
    return next(b for b in at.button if b.label == label or b.label.endswith(" " + label))


def test_chat_answer_shows_mentor_card(ui):
    at, _ = ui
    at.run()
    at.sidebar.radio[0].set_value("🎤 Live AI Interview").run()
    _btn(at, "Start interview").click().run()
    at.text_area[0].set_value("Sorry, I'm nervous. RAG retrieves documents.")
    _btn(at, "Submit answer").click().run()
    assert not at.exception, at.exception
    assert any("Your mentor" in m.value for m in at.markdown)


def test_confidence_coach_page_with_history(ui):
    at, u = ui
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(u.id, "interview", "AI Engineer", "Beginner", "Technical", 3)
    for text in ("Sorry, I'm nervous.", "RAG retrieves documents and grounds answers."):
        orch.submit_answer(sid, q["id"], text, signals=prosody.combine(text))
    at.run()
    at.sidebar.radio[0].set_value("💛 Confidence Coach").run()
    assert not at.exception, at.exception
    _btn(at, "Build my confidence growth plan").click().run()
    assert not at.exception, at.exception
    assert any("Confidence is rising" in m.value for m in at.markdown)
