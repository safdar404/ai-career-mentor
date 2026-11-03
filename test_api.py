import pytest
from fastapi.testclient import TestClient

import db

_real_init = db.init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'api.db'}"
    db._engine = None
    monkeypatch.setattr(db, "init_db", lambda u=None: _real_init(url))
    import api
    with TestClient(api.app) as c:
        yield c


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_disabled_without_token(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    assert client.get("/users").status_code == 503


def test_token_required_and_stats(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret-token")
    assert client.get("/users", headers={"Authorization": "Bearer wrong"}).status_code == 401
    u = db.get_or_create_user("Muhammad Safdar")
    h = {"Authorization": "Bearer secret-token"}
    assert client.get("/users", headers=h).json()[0]["name"] == "Muhammad Safdar"
    s = client.get(f"/users/{u.id}/stats", headers=h).json()
    assert s["metrics"]["Interview readiness"]["value"] is None
    assert client.get("/users/999/export", headers=h).status_code == 404
