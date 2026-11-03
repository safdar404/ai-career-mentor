"""Drives the real Streamlit app headlessly with a fake model provider."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import db
from orchestrator import Orchestrator
from fake_provider import FakeProvider

APP = str(Path(__file__).resolve().parent / "app.py")
PAGES = ["📊 Dashboard", "🎤 Live AI Interview", "💛 Confidence Coach", "🗣️ English Communication Lab", "🧪 Technical Assessment",
         "🐍 Python Coding Lab", "🤖 Generative AI Academy", "🕸️ Agentic AI Academy", "📽️ Project Presentation Trainer",
         "🤝 HR Interview Simulator", "🎯 Weakness & Gap Analysis", "🗺️ Learning Roadmap", "📈 Performance Reports",
         "🗂️ Conversation History", "⚙️ Settings"]

_real_init = db.init_db


def page_label(name: str) -> str:
    return next(p for p in PAGES if p.endswith(" " + name))


@pytest.fixture
def app(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'ui.db'}"
    db._engine = None
    monkeypatch.setattr(db, "init_db", lambda u=None: _real_init(url))
    db.init_db()
    st.cache_resource.clear()
    user = db.get_or_create_user("Muhammad Safdar", "Junior AI Engineer")
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["user_id"] = user.id
    at.session_state["orch::None"] = Orchestrator(provider=FakeProvider())
    return at, user


def _button(at, label):
    for b in at.button:
        if b.label == label or b.label.endswith(" " + label):  # labels carry a leading emoji
            return b
    raise AssertionError(f"No button {label!r}; have {[b.label for b in at.button]}")


def test_onboarding_without_user(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'o.db'}"
    db._engine = None
    monkeypatch.setattr(db, "init_db", lambda u=None: _real_init(url))
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.text_input[0].set_value("Muhammad Safdar")
    _button(at, "Start training").click().run()
    assert not at.exception
    assert at.session_state["user_id"]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(app, page):
    at, _ = app
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception


def test_live_interview_end_to_end(app):
    at, user = app
    at.run()
    at.sidebar.radio[0].set_value(page_label("Live AI Interview")).run()
    _button(at, "Start interview").click().run()
    assert not at.exception
    assert any("How would you explain" in m.value for m in at.markdown)
    at.text_area[0].set_value("RAG retrieves relevant chunks from a vector database and adds them to the prompt.")
    _button(at, "Submit answer").click().run()
    assert not at.exception, at.exception
    assert any("Feedback" in m.value for m in at.markdown)
    _button(at, "Next question").click().run()
    assert not at.exception
    _button(at, "End session without answering").click().run()
    assert not at.exception
    assert any("Session summary" in m.value for m in at.markdown)
    # dashboard now shows real numbers
    at.sidebar.radio[0].set_value(page_label("Dashboard")).run()
    assert not at.exception
    assert db.evaluations_for_user(user.id)


def test_english_lab_retry(app):
    at, _ = app
    at.run()
    at.sidebar.radio[0].set_value(page_label("English Communication Lab")).run()
    _button(at, "Start conversation").click().run()
    at.text_area[0].set_value("It was good, I am went to my village.")
    _button(at, "Submit answer").click().run()
    assert not at.exception
    _button(at, "Try this reply again").click().run()
    at.text_area[0].set_value("It was great, thanks. I went to my village.")
    _button(at, "Submit answer").click().run()
    assert not at.exception
    assert any("Attempt 2" in i.value for i in at.info)


def test_coding_and_projects_and_reports(app):
    at, user = app
    at.run()
    at.sidebar.radio[0].set_value(page_label("Python Coding Lab")).run()
    _button(at, "Generate challenge").click().run()
    _button(at, "Submit for review").click().run()
    assert not at.exception
    assert any("not executed" in s.value for s in at.success) or at.error

    at.sidebar.radio[0].set_value(page_label("Project Presentation Trainer")).run()
    at.text_input[0].set_value("GIS RAG assistant")
    _button(at, "Save project").click().run()
    assert not at.exception
    assert db.list_projects(user.id)

    at.sidebar.radio[0].set_value(page_label("Learning Roadmap")).run()
    _button(at, "Create my 90-day roadmap").click().run()
    assert not at.exception and db.active_roadmap(user.id)

    at.sidebar.radio[0].set_value(page_label("Performance Reports")).run()
    _button(at, "Generate this week's report").click().run()
    assert not at.exception
    assert db.list_reports(user.id)
