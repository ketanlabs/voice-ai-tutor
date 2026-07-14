"""API happy-path tests via FastAPI TestClient (fakeredis-backed, offline)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client(settings, redis_client, exercise):
    app = create_app(settings=settings, redis_client=redis_client, exercise=exercise)
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_session_token_creates_learner_with_handle_identity(client):
    resp = client.post("/session/token", json={"handle": "maria"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"] == "maria"            # identity == handle (greeting/display)
    assert body["language"] == "es"               # default language
    assert body["livekit_url"].startswith("ws")
    assert len(body["token"].split(".")) == 3     # looks like a JWT


def test_session_token_honours_language(client):
    body = client.post("/session/token", json={"handle": "pierre", "language": "fr"}).json()
    assert body["language"] == "fr"


def test_empty_handle_is_rejected(client):
    assert client.post("/session/token", json={"handle": ""}).status_code == 422


def test_exercise_list_served(client):
    items = client.get("/exercise").json()
    assert len(items) >= 1
    assert {"prompt", "image", "emoji"} <= set(items[0])


def test_pronunciation_attempt_flow(client):
    # namespaced per-language learner id, as the voice agent uses it
    lid = "leo:fr"
    client.post("/session/token", json={"handle": "leo", "language": "fr"})
    r = client.post(
        f"/learners/{lid}/attempt",
        json={"word": "pomme", "correct": True, "skill": "pronunciation"},
    )
    assert r.status_code == 200
    items = client.get(f"/learners/{lid}/review-items", params={"n": 5}).json()["items"]
    assert "pomme" in [i["word"] for i in items]
