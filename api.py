"""Optional REST API (FastAPI) over the same database.

Run with:  uvicorn api:app --port 8000

Every endpoint except /health requires `Authorization: Bearer <API_TOKEN>`.
If API_TOKEN is not set, those endpoints are disabled. They expose personal
training data and should never be open by accident.
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from mentor import analytics, db
from mentor.config import settings
from mentor.llm import available_providers

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI Career Mentor API", version="1.0.0", lifespan=lifespan)


def require_token(authorization: str = Header(default="")) -> None:
    token = os.getenv("API_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "API disabled: set API_TOKEN to enable it.")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "Invalid or missing token.")


@app.get("/health")
def health() -> dict:
    db.init_db()
    return {"status": "ok", "providers": available_providers(), "speech_to_text": settings.has_openai}


@app.get("/users", dependencies=[Depends(require_token)])
def users() -> list[dict]:
    return [{"id": u.id, "name": u.name, "target_role": u.target_role} for u in db.list_users()]


def _user_or_404(user_id: int):
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(404, "User not found.")
    return u


@app.get("/users/{user_id}/stats", dependencies=[Depends(require_token)])
def stats(user_id: int) -> dict:
    _user_or_404(user_id)
    return {"metrics": analytics.dashboard_metrics(user_id), "daily": analytics.daily_trend(user_id),
            "areas": analytics.group_scores(user_id),
            "open_gaps": [{"category": g.category, "topic": g.topic, "description": g.description,
                           "occurrences": g.occurrences, "priority": g.priority} for g in db.list_gaps(user_id)]}


@app.get("/users/{user_id}/export", dependencies=[Depends(require_token)])
def export(user_id: int) -> dict:
    _user_or_404(user_id)
    return db.export_user_data(user_id)
