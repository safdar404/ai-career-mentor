"""Tests for API-key handling, conversation history, PINs, presence coaching and the call modes."""
import base64
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
import db
import keys
import llm
import videocall
from fake_provider import FakeProvider
from orchestrator import Orchestrator, ValidationError

APP = str(Path(__file__).resolve().parent / "app.py")
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db._engine = None
    db.init_db(f"sqlite:///{tmp_path / 'f.db'}")
    yield


@pytest.fixture
def user():
    return db.get_or_create_user("Muhammad Safdar", "Junior AI Engineer")


# ----------------------------------------------------------------- keys

def test_settings_proxy_without_streamlit_uses_server_values():
    assert config.settings.anthropic_model == config.base_settings.anthropic_model
    assert config.resolve(config.settings) == config.current_settings()


def test_key_format_checks():
    assert keys.looks_valid("anthropic", "") == "Paste a key first."
    assert "start with" in keys.looks_valid("anthropic", "sk-proj-abcdefghijklmnopqrstuvwxyz")
    assert "spaces" in keys.looks_valid("openai", "sk-abc def ghijklmnopqrstuvwxyz")
    assert keys.looks_valid("anthropic", "sk-ant-" + "a" * 40) is None
    assert keys.looks_valid("openai", "sk-" + "a" * 40) is None


def test_session_keys_are_redacted_from_logs(caplog):
    secret = "sk-ant-" + "z" * 40
    config.remember_secret(secret)
    rec = __import__("logging").LogRecord("x", 20, __file__, 1, f"key={secret}", (), None)
    config._SecretFilter().filter(rec)
    assert secret not in rec.getMessage()


def test_claude_5_models_do_not_get_temperature():
    assert not llm._claude_accepts_sampling("claude-sonnet-5-5")
    assert not llm._claude_accepts_sampling("claude-opus-5")
    assert llm._claude_accepts_sampling("claude-sonnet-4-6")

    sent = {}

    class Msgs:
        def create(self, **kw):
            sent.update(kw)
            return type("R", (), {"content": [type("B", (), {"text": "{}"})()]})()

    prov = llm.AnthropicProvider.__new__(llm.AnthropicProvider)
    prov.model = "claude-sonnet-5-5"
    prov._client = type("C", (), {"messages": Msgs()})()
    prov.complete("sys", [{"role": "user", "content": "hi"}], temperature=0.3)
    assert "temperature" not in sent


# ----------------------------------------------------------------- PIN

def test_pin_round_trip_and_not_exported(user):
    assert db.check_pin(user.id, "") is True  # no PIN set: open
    with pytest.raises(ValueError):
        db.set_pin(user.id, "12ab")
    db.set_pin(user.id, "4321")
    assert db.has_pin(user.id)
    assert db.check_pin(user.id, "4321") and not db.check_pin(user.id, "1234")
    assert "4321" not in db.get_setting(user.id, "pin_hash")
    assert all(r["key"] != "pin_hash" for r in db.export_user_data(user.id)["settings"])
    db.set_pin(user.id, "")
    assert not db.has_pin(user.id)


# ----------------------------------------------------------------- conversation history

def test_conversations_are_saved_searchable_and_deletable(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 2)
    orch.submit_answer(sid, q["id"], "RAG retrieves documents from a vector store before generation.", "video")

    dialogue = db.get_messages(sid)
    assert [m.role for m in dialogue] == ["assistant", "user"]  # coaching notes are not dialogue turns
    full = db.get_messages(sid, include_meta=True)
    assert any(m.agent == "feedback" and "Score:" in m.content for m in full)

    rows = db.conversation_index(user.id)
    assert rows[0]["id"] == sid and rows[0]["answers"] == 1 and rows[0]["messages"] == 2
    assert db.conversation_index(user.id, search="vector store")[0]["id"] == sid
    assert db.conversation_index(user.id, search="kubernetes") == []
    assert db.conversation_index(user.id, module="english") == []

    other = db.get_or_create_user("Someone Else")
    assert db.delete_session(sid, other.id) is False  # only the owner can delete
    assert db.delete_session(sid, user.id) is True
    assert db.conversation_index(user.id) == [] and db.get_session(sid) is None


def test_coding_and_pitch_conversations_are_recorded(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, _ = orch.start_pitch(user.id, {"title": "GIS RAG"}, "1 minute", "British English")
    assert db.get_messages(sid)[0].role == "assistant"


# ----------------------------------------------------------------- presence

def test_presence_check_logs_tips_but_never_the_image(user):
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(user.id, "interview", "AI Engineer", "Beginner", "Technical", 2)
    res = orch.presence_check(sid, JPEG, q["question"])
    assert res["overall"] == 6 and res["tips"] and set(res) >= {"eye_contact", "lighting", "posture"}
    notes = [m for m in db.get_messages(sid, include_meta=True) if m.agent == "presence_coach"]
    assert len(notes) == 1 and "/10" in notes[0].content
    assert all(b"\xff\xd8" not in m.content.encode() for m in notes)
    with pytest.raises(ValidationError):
        orch.presence_check(sid, b"", q["question"])


def test_decode_image_accepts_only_small_jpeg_or_png():
    good = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
    assert videocall.decode_image(good) == JPEG
    assert videocall.decode_image("data:text/html;base64," + base64.b64encode(b"<script>").decode()) is None
    assert videocall.decode_image("data:image/jpeg;base64," + base64.b64encode(b"notajpeg").decode()) is None
    assert videocall.decode_image("data:image/jpeg;base64,!!!") is None
    assert videocall.decode_image(None) is None


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


@pytest.mark.parametrize("mode", ["voice", "video"])
def test_call_modes_render(ui, mode):
    at, u = ui
    db.set_setting(u.id, "mode", mode)
    at.run()
    at.sidebar.radio[0].set_value("🎤 Live AI Interview").run()
    _btn(at, "Start interview").click().run()
    assert not at.exception, at.exception


def test_history_page_shows_saved_conversation(ui):
    at, u = ui
    orch = Orchestrator(provider=FakeProvider())
    sid, q = orch.start_session(u.id, "interview", "AI Engineer", "Beginner", "Technical", 2)
    orch.submit_answer(sid, q["id"], "My distinctive answer about embeddings.")
    at.run()
    at.sidebar.radio[0].set_value("🗂️ Conversation History").run()
    assert not at.exception, at.exception
    assert any("distinctive answer" in m.value for m in at.markdown)


def test_bad_key_is_rejected_without_network(ui):
    at, _ = ui
    at.run()
    at.sidebar.text_input[0].set_value("not-a-key")
    next(b for b in at.sidebar.button if "Connect key" in b.label).click().run()
    assert not at.exception
    assert any("start with" in e.value for e in at.sidebar.error)
    assert not at.session_state["api_keys"] if "api_keys" in at.session_state else True


def test_locked_profile_needs_pin(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'p.db'}"
    db._engine = None
    monkeypatch.setattr(db, "init_db", lambda u=None: _real_init(url))
    db.init_db()
    st.cache_resource.clear()
    u = db.get_or_create_user("Locked Learner")
    db.set_pin(u.id, "2468")
    at = AppTest.from_file(APP, default_timeout=30).run()
    # creating a profile with the same name must not bypass the PIN
    at.text_input[0].set_value("Locked Learner")
    _btn(at, "Start training").click().run()
    assert "user_id" not in at.session_state
    assert any("PIN-protected" in w.value for w in at.warning)
