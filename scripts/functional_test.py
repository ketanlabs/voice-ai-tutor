#!/usr/bin/env python3
"""End-to-end FUNCTIONAL test against a *running* backend + real Redis.

Unlike the unit tests (which use fakeredis in-process), this drives the live
HTTP API exactly as the frontend and voice agent do, and proves the headline
feature — cross-session memory — by reconnecting with the same handle and
checking that progress persisted.

WHAT IT COVERS
  session tokens · exercise list · pronunciation result → spaced-repetition ·
  session summaries · per-language memory (isolation) across "sessions".

WHAT IT DOES NOT COVER
  the live voice conversation (real STT/LLM/TTS + mic) — that needs API keys and
  a human, and is the manual walkthrough (README).

HOW TO RUN
  1) Start the backend + Redis (lightweight — no voice/LLM keys needed):
         docker compose up --build backend
     (this also starts Redis, which the backend depends on)
  2) In another terminal:
         python3 scripts/functional_test.py
         make functional-test           # equivalent

  Point at a different host with:  FUNCTEST_BACKEND_URL=http://localhost:8000
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("FUNCTEST_BACKEND_URL", "http://localhost:8000").rstrip("/")
HANDLE = os.environ.get("FUNCTEST_HANDLE", f"functest-{int(time.time())}")

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
_passed = 0
_failed = 0


def _req(method: str, path: str, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return resp.status, (json.loads(raw) if raw else {})


def check(desc: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  {GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"  {RED}✗ {desc}{RESET}" + (f"  {DIM}({detail}){RESET}" if detail else ""))


def preflight() -> None:
    try:
        status, body = _req("GET", "/health")
    except (urllib.error.URLError, ConnectionError) as exc:
        print(f"{RED}Cannot reach the backend at {BASE}{RESET}\n  {exc}\n")
        print("Start it first (Redis comes up as a dependency):")
        print(f"  {BOLD}docker compose up --build backend{RESET}\n")
        sys.exit(2)
    if status != 200 or body.get("status") != "ok":
        print(f"{RED}Backend health check failed: {status} {body}{RESET}")
        sys.exit(2)


def main() -> int:
    print(f"{BOLD}Functional test{RESET} → {BASE}   {DIM}(handle: {HANDLE}){RESET}\n")
    preflight()
    lid = f"{HANDLE}:fr"  # per-language learner id, as the voice agent uses it

    # 1) New learner connects (French) — gets a token.
    print(f"{BOLD}1. First session (new learner, French){RESET}")
    _, tok = _req("POST", "/session/token", {"handle": HANDLE, "language": "fr"})
    check("token issued", len(str(tok.get("token", "")).split(".")) == 3)
    check("identity == handle (greeting/display)", tok.get("identity") == HANDLE,
          f"got {tok.get('identity')}")
    check("language echoed", tok.get("language") == "fr", f"got {tok.get('language')}")
    check("livekit_url returned", str(tok.get("livekit_url", "")).startswith("ws"))

    # 2) Exercise list is served.
    print(f"\n{BOLD}2. Exercise list{RESET}")
    _, items = _req("GET", "/exercise")
    check(f"exercise items available ({len(items)})", len(items) >= 1)
    check("items have prompt + image", bool(items and "prompt" in items[0] and "image" in items[0]))

    # 3) A pronunciation attempt is recorded → enters spaced-repetition schedule.
    print(f"\n{BOLD}3. Pronunciation result → SRS{RESET}")
    status, _ = _req("POST", f"/learners/{lid}/attempt",
                     {"word": "pomme", "correct": True, "skill": "pronunciation"})
    check("result accepted", status == 200)
    _, review = _req("GET", f"/learners/{lid}/review-items?n=5")
    words = [i["word"] for i in review.get("items", [])]
    check("practiced word scheduled for review", "pomme" in words, f"got {words}")

    # 4) Save a session summary.
    print(f"\n{BOLD}4. Session summary{RESET}")
    status, _ = _req("POST", f"/learners/{lid}/sessions",
                     {"topics": ["pronunciation"], "new_words": ["pomme"], "notes": "functional test"})
    check("session summary saved", status == 200)

    # 5) THE KEY TEST — reconnect (same handle + language) → memory persisted.
    print(f"\n{BOLD}5. Reconnect (per-language memory){RESET}")
    _req("POST", "/session/token", {"handle": HANDLE, "language": "fr"})
    _, snap = _req("GET", f"/learners/{lid}")
    check("profile persisted (target_lang=fr)", snap.get("profile", {}).get("target_lang") == "fr")
    _, review2 = _req("GET", f"/learners/{lid}/review-items?n=5")
    check("practiced word still scheduled", "pomme" in [i["word"] for i in review2.get("items", [])])

    # 6) A different language is a separate journey.
    print(f"\n{BOLD}6. Language isolation{RESET}")
    _req("POST", "/session/token", {"handle": HANDLE, "language": "es"})
    _, review_es = _req("GET", f"/learners/{HANDLE}:es/review-items?n=5")
    check("Spanish journey is independent (no French words)",
          "pomme" not in [i["word"] for i in review_es.get("items", [])])

    # ---- summary ----
    total = _passed + _failed
    print(f"\n{BOLD}Result:{RESET} {GREEN}{_passed} passed{RESET}, "
          f"{(RED if _failed else DIM)}{_failed} failed{RESET}  (of {total})")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
