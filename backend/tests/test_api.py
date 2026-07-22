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


def test_progress_report(client, exercise):
    # Curriculum-driven progress: one row per exercise item, joined with practice.
    lid = "ana:es"
    client.post("/session/token", json={"handle": "ana", "language": "es"})

    prompts = [it.prompt for it in exercise]
    correct_prompt, wrong_prompt, untouched_prompt = prompts[0], prompts[1], prompts[2]

    # One word passed (correct), one attempted-but-wrong, a third left untouched.
    client.post(
        f"/learners/{lid}/attempt",
        json={"word": correct_prompt, "translation": "manzana", "correct": True},
    )
    client.post(
        f"/learners/{lid}/attempt",
        json={"word": wrong_prompt, "translation": "naranja", "correct": False},
    )

    body = client.get(f"/learners/{lid}/progress").json()
    assert body["language"] == "es"
    assert body["profile"]["target_lang"] == "es"

    # All curriculum items present, one row each.
    assert len(body["items"]) == len(exercise)
    by_prompt = {row["prompt"]: row for row in body["items"]}
    assert set(by_prompt) == set(prompts)

    # Correct word: passed, translation captured.
    assert by_prompt[correct_prompt]["passed"] is True
    assert by_prompt[correct_prompt]["correct"] >= 1
    assert by_prompt[correct_prompt]["word"] == "manzana"

    # Wrong-only word: seen but not passed.
    assert by_prompt[wrong_prompt]["passed"] is False
    assert by_prompt[wrong_prompt]["seen"] >= 1
    assert by_prompt[wrong_prompt]["correct"] == 0

    # Untouched word: all zeros, blank translation.
    assert by_prompt[untouched_prompt] == {
        "prompt": untouched_prompt, "word": "", "seen": 0, "correct": 0, "passed": False,
    }

    # Mastery score = distinct words passed / total curriculum items.
    assert body["score"] == {"passed": 1, "total": len(exercise)}
