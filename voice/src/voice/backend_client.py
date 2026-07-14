"""Thin async HTTP client for the backend API.

The voice agent holds NO state itself — every read/write goes through the
backend, which owns Redis and the curriculum. This keeps the components
genuinely isolated (and makes the voice worker horizontally scalable).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("voice.backend")


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> dict | list:
        resp = await self._client.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: dict | None = None, **params: Any) -> Any:
        resp = await self._client.post(path, json=json, params=params or None)
        resp.raise_for_status()
        return resp.json()

    # --- reads ---------------------------------------------------------------
    async def get_snapshot(self, identity: str) -> dict:
        return await self._get(f"/learners/{identity}")  # type: ignore[return-value]

    async def get_exercise(self) -> list[dict]:
        return await self._get("/exercise")  # type: ignore[return-value]

    async def get_review_items(self, identity: str, n: int = 5) -> list[dict]:
        data = await self._get(f"/learners/{identity}/review-items", n=n)
        return data.get("items", [])  # type: ignore[union-attr]

    # --- writes --------------------------------------------------------------
    async def record_attempt(self, identity: str, *, correct: bool,
                             word: str | None = None, translation: str = "",
                             skill: str = "pronunciation") -> None:
        await self._post(
            f"/learners/{identity}/attempt",
            json={"correct": correct, "word": word, "translation": translation,
                  "skill": skill},
        )

    async def save_session(self, identity: str, *, topics: list[str],
                           new_words: list[str], notes: str = "") -> None:
        await self._post(
            f"/learners/{identity}/sessions",
            json={"topics": topics, "new_words": new_words, "notes": notes},
        )
