# 🗣️ Lingua — a Real-Time Voice AI Pronunciation Trainer

Lingua is a real-time **voice** pronunciation trainer for **Spanish, French, or
Italian**. You open the web app, enter your name, pick a language, and press
**Start** — Lingua **shows you a picture, says the word or sentence out loud**, you
**repeat it** (push-to-talk), and it gives you a **👍 / 👎** and moves to the next
one, until the set is complete.

Built on [LiveKit](https://livekit.io) for low-latency, interruptible voice.

**The flow:** picture → hear the word/sentence in your language → repeat it →
👍/👎 → next. Progress is remembered **per language**, so you pick up where you left
off (and the words you struggle with come back around via spaced repetition).

> **Video walkthrough:** _<add link here>_ — a ≤1-minute demo: enter a name, pick a
> language, and do a few pronunciation cards.

---

## Why this design? (product rationale)

- **Voice-native, low-friction practice.** Pronunciation is the one thing you can
  *only* practice out loud. A picture → hear-it → say-it → 👍/👎 loop is fast,
  concrete, and needs no reading — great for beginners and hands-free practice.
- **Push-to-talk.** The mic is muted until you hold the button (or Space), so the
  coach only hears you when you mean to speak — no ambient pickup, clear turns.
- **Authored once, works in three languages.** The item list is a single **English**
  file; the coach (Claude) translates each word/sentence to the target language at
  runtime. One file → Spanish, French, Italian. Add items by editing one YAML file.
- **Cross-session memory (per language).** Each practiced word is tracked as a
  spaced-repetition item in Redis keyed by `learner:{name}:{lang}`, so weak items
  resurface and French progress stays separate from Spanish.

**Honest note on the 👍/👎:** standard speech-to-text returns *text*, not
phoneme-level accent scores. So Lingua does **not** fake an accent grade — the
👍/👎 reflects whether your spoken attempt was **recognized as the target word**
(intelligibility). On a 👎 the coach models the word again. Truthful beats impressive.

---

## Architecture overview

Three **independently-owned components** with strict boundaries, matching the
brief's separation of concerns (session management · conversation handling ·
voice/AI layer). **Redis and the curriculum are owned only by the backend**; the
voice and frontend are stateless clients.

```
┌────────────┐   HTTP (token, exercise)  ┌─────────────────────────────┐
│  FRONTEND  │ ────────────────────────► │          BACKEND            │
│ (Next.js)  │ ◄──────────────────────── │  (FastAPI)  SESSION MGMT    │
│ presentation│         exercise list     │  tokens · exercise list ·   │
└─────┬──────┘                           │  learner SRS state          │
      │ WebRTC (audio + data channel)    └───────┬───────────┬─────────┘
      ▼                                    owns   │           │ loads
┌────────────┐        ┌──────────────┐   HTTP     ▼           ▼
│  LiveKit   │ ◄────► │    VOICE     │ ─────►   Redis     curriculum/exercise.yaml
│   server   │  audio │ (LK agent)   │
│(self-hosted)│       │ CONVERSATION │  tutor.py  = coach, show/score item tools
└────────────┘        │  + AI LAYER  │  pipeline.py = STT · LLM · TTS · turn
                      └──────────────┘
```

| Concern (from the brief) | Component | What it does |
| --- | --- | --- |
| **Session management** | `backend/` (FastAPI) | Learner identity, LiveKit tokens, the exercise list, per-prompt SRS state, session summaries. **Sole owner of Redis.** |
| **Conversation handling** | `voice/…/tutor.py` | The `LinguaTutor` coach: runs the exercise loop (`show_item` → say → `score_item` 👍/👎 → next), pushes UI events. Stateless — delegates persistence to the backend. |
| **Voice/AI layer** | `voice/…/pipeline.py` | STT · LLM · TTS · VAD · turn-detection wiring and provider selection. |
| **Presentation** | `frontend/` (Next.js) | Connect screen, the flashcard exercise view, transcript, audio visualizer. No secrets, no state. |

**How it flows:** the browser asks the backend for a token (identity = your handle,
namespaced per language) → connects to LiveKit → the voice worker joins, loads the
exercise list, greets you, and runs the picture-pronunciation loop — pushing each
image + 👍/👎 to the browser over the data channel and recording results in Redis.

### Tech stack
- **Backend:** Python 3.13, FastAPI, `redis`, `pydantic`, `livekit-api`.
- **Voice:** Python, LiveKit Agents SDK `1.6`, plugins for Deepgram (STT),
  Anthropic **Claude** (LLM), Cartesia (TTS), Silero (VAD), multilingual
  turn-detector.
- **Frontend:** Next.js 14 + `@livekit/components-react`.
- **Infra:** self-hosted `livekit/livekit-server`, Redis, all via Docker Compose.

---

## Run it (Docker only)

**Prerequisites:** Docker + Docker Compose. Then either provider API keys
(self-hosted default) **or** a LiveKit Cloud project.

```bash
cp .env.example .env          # then fill in the keys (see table below)
docker compose up --build     # starts redis + livekit + backend + voice + frontend
# wait for: backend /health OK, voice "registered worker", frontend on :3000
```

Open **http://localhost:3000**, enter a name, pick a language, click **Start
practicing**, allow the mic, and **hold the button (or Space) to say each word**.

```bash
docker compose down           # stop
docker compose down -v        # stop + wipe Redis volume (clears learner memory)
```

There's a `Makefile` for convenience: `make up`, `make down`, `make logs`,
`make clean`, `make seed` (reload the exercise list), `make lint`, and `make test`.

### Add or reorder exercise items
Edit **`backend/curriculum/exercise.yaml`** — a single English file; list order is
play order. Each entry is `{ prompt, image, emoji }` (`prompt` = a word or short
sentence; the coach translates it to the chosen language at runtime). Put picture
files in **`frontend/public/flashcards/`** and reference them as
`image: /flashcards/<name>.jpg` (missing image → emoji + text fallback). Both are
mounted as volumes, so after editing just `docker compose restart backend`.

### Two run modes (set in `.env`)
- **Self-hosted (default):** `USE_LIVEKIT_INFERENCE=false`. LiveKit runs in
  Docker; the voice agent uses your Deepgram / Anthropic / Cartesia keys.
- **LiveKit Cloud:** point `LIVEKIT_URL` + `NEXT_PUBLIC_LIVEKIT_URL` and the API
  key/secret at a [LiveKit Cloud](https://cloud.livekit.io) project. Optionally
  set `USE_LIVEKIT_INFERENCE=true` to route models through LiveKit Inference with
  a single key. This is also the recommended escape hatch if local WebRTC/UDP
  networking gives you trouble (see Tradeoffs).

### Where to get the keys

| Variable | Where to get it |
| --- | --- |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `LIVEKIT_URL` | Self-hosted uses the dev values in `.env.example`; or create a project at [cloud.livekit.io](https://cloud.livekit.io) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) (STT) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) (Claude LLM) |
| `CARTESIA_API_KEY` | [play.cartesia.ai](https://play.cartesia.ai) (TTS) |

All configuration is read from the root `.env` — **no secrets are hardcoded**.
See `.env.example` for every variable (each is commented).

---

## Testing

```bash
make test        # backend pytest + frontend vitest, in Docker
```

`make test` is **fully offline — no API keys and no running services required.**
The backend suite runs against **fakeredis** + FastAPI's `TestClient`; the
frontend uses **Vitest**. Coverage focuses on the real logic:

- **`srs.py`** — spaced-repetition selection + scheduling (weak words resurface)
- **`curriculum.py`** — exercise-YAML schema validation fails loudly on bad content
- **`store.py`** — Redis round-trips (profile, per-prompt SRS, skill stats, sessions)
- **API** — `/session/token` (identity == handle), `/exercise`, review-items
- **`tutorEvents`** — data-channel decoding → flashcard UI state (frontend)

Run a single suite: `make test-backend` · `make test-frontend`. (The backend
image also runs its tests directly via `docker compose run --rm backend pytest`;
the frontend tests need the build stage, so use `make test-frontend`.)

### Functional (end-to-end) test

To exercise the **running** system over real HTTP + real Redis — and prove
cross-session memory — start the backend and run the functional test:

```bash
docker compose up --build backend      # brings up Redis + backend (no LLM keys needed)
make functional-test                   # = python3 scripts/functional_test.py
```

It walks the flow (token → `/exercise` list → record a pronunciation attempt →
spaced-repetition review → session summary), then **reconnects with the same
name + language** to confirm progress persisted, and checks that a *different*
language is a separate journey. It does not cover the live voice loop (mic +
STT/LLM/TTS) — that's the manual walkthrough.

---

## Key design decisions & tradeoffs

- **Three isolated components instead of one agent process.** More moving parts,
  but each is independently testable and scalable, and it enforces the brief's
  separation of concerns. The voice worker holds no state, which is exactly what
  makes it horizontally scalable (see below). *Tradeoff:* an extra network hop
  (voice → backend) per tool call; acceptable at conversational latencies and
  worth the clean boundary.
- **Backend owns Redis and the exercise list; nobody else touches them.** A single
  source of truth for state avoids drift and keeps secrets/DB access in one
  place. A CI-style grep asserts no `redis` import escapes `backend/`.
- **Content as version-controlled YAML, not a DB.** The exercise list is read-only
  authored content, authored **once in English** and translated at runtime — YAML
  is diffable, reviewable, and needs no migration. Loaded + validated at startup so
  bad content fails fast. *Tradeoff:* it's mounted as a volume, so editing +
  `docker compose restart backend` picks it up; the path to a CMS is clean (see scaling).
- **Claude for the LLM via a swappable pipeline.** The LLM is the coach's brain —
  Claude is strong at bilingual, pedagogically-aware, tool-using conversation.
  Providers are chosen entirely by env (`*_PROVIDER`, `USE_LIVEKIT_INFERENCE`) so
  STT/LLM/TTS can be swapped without code changes.
- **Stable identity = your handle.** Cross-session memory only works if the same
  learner maps to the same key. The handle (stored in `localStorage`, set as the
  LiveKit participant identity by the backend token) is that key. A random
  per-connect identity — the usual starter default — would silently break memory.
- **Self-hosted LiveKit in Compose.** Gives a fully local, reproducible stack
  with no cloud account. *Tradeoff:* browser↔SFU WebRTC media over Docker needs
  UDP/TCP ports and a reachable advertised IP — the classic self-host gotcha. We
  mitigate with a published TCP fallback (`7881`), a UDP range, and
  `--node-ip 127.0.0.1`; if it still misbehaves on your machine, LiveKit Cloud is
  a one-line `.env` switch.
- **Honest pronunciation scope** (above) — we build what STT can actually
  support rather than a fake accent score.

---

## How I'd scale this to 10,000 concurrent sessions

The component split is already the foundation; the binding constraints at 10k are
**media capacity** and **provider rate limits**, not app code.

1. **LiveKit** — move from a single self-hosted node to **LiveKit Cloud or a
   multi-node SFU cluster** (Redis-backed) with regional routing for low-latency
   media close to users.
2. **Voice workers** — they're **stateless** (all state via the backend), so run
   a large pool and **autoscale on active-session count** (~one job per session).
   This is the layer that grows most; interchangeable replicas make it easy.
3. **Backend** — stateless FastAPI behind a load balancer; scale horizontally.
   Split storage: **Redis (managed/clustered)** for hot session/live state, and a
   **durable store (Postgres)** for per-learner progress history as data grows.
4. **Model providers** — the real ceiling. Raise provider concurrency quotas,
   pool connections, and add **multi-provider fallback** across STT/TTS. Control
   cost with **model tiering** and **TTS caching** — every learner hears the same
   fixed set of words, so cached TTS per (word × language × voice) is a big win.
5. **Content → CMS** — promote the exercise YAML to a content service/DB with an
   authoring UI (and larger, leveled item sets) once it outgrows hand-edits.
6. **Observability** — per-session metrics (turn latency, errors, pass/fail rates),
   structured logs, and tracing across frontend → backend → voice to find the
   bottleneck before users do.

---

## Repository layout

```
backend/    FastAPI: tokens, exercise list, per-prompt SRS, Redis store (+ pytest)
  curriculum/exercise.yaml   the exercise list (English, one file, all languages)
voice/      LiveKit agent worker: pipeline.py (AI layer) + tutor.py (coach)
frontend/   Next.js UI: connect screen, flashcard exercise, transcript, visualizer
  public/flashcards/         the picture assets
livekit/    self-hosted server config
docker-compose.yml · Makefile · .env.example · PROMPT.md · workflow.md
```
