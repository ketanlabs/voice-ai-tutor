# Architecture — Lingua

This document is the engineering-level companion to the product overview in
[`README.md`](./README.md). It describes the components, their boundaries, the
end-to-end runtime flow, the data model, and the wire protocols that connect
everything.

> **TL;DR** — Four services plus a store, split along the brief's three concerns
> (session management · conversation handling · voice/AI layer) plus presentation.
> **The backend is the sole owner of Redis and the curriculum.** The voice worker
> and the frontend are stateless clients that talk to the backend over HTTP and to
> each other over LiveKit (audio + a one-way data channel).

---

## 1. Components & ownership

| Component | Directory | Concern | Owns | Stateless? |
| --- | --- | --- | --- | --- |
| **Backend** | `backend/` (FastAPI) | Session management | **Redis**, **curriculum YAML**, LiveKit token minting | Yes (state is in Redis) |
| **Voice worker** | `voice/` (LiveKit Agents) | Conversation + Voice/AI | nothing — delegates all state to the backend | Yes → horizontally scalable |
| **Frontend** | `frontend/` (Next.js) | Presentation | nothing — no secrets, no state | Yes |
| **LiveKit server** | `livekit/` (self-hosted SFU) | Media transport | WebRTC routing | — |
| **Redis** | (compose service) | Persistence | the bytes | — |

**Enforced boundary:** the only module in the entire system that imports `redis`
is under `backend/`. A CI-style grep asserts this — no other component may reach
the store directly; they go through the backend's REST API.

```
┌────────────┐   HTTP (token, exercise)  ┌─────────────────────────────┐
│  FRONTEND  │ ────────────────────────► │          BACKEND            │
│ (Next.js)  │ ◄──────────────────────── │  (FastAPI)  SESSION MGMT    │
│ presentation│    token · exercise list  │  tokens · exercise list ·   │
└─────┬──────┘                           │  learner SRS state          │
      │ WebRTC: audio tracks             └───────┬───────────┬─────────┘
      │        + `tutor-ui` data channel   owns  │           │ loads
      ▼                                    HTTP  ▼           ▼
┌────────────┐        ┌──────────────┐  (attempt/    Redis     curriculum/
│  LiveKit   │ ◄────► │    VOICE     │ ─ session) ─►         exercise.yaml
│   server   │  audio │ (LK agent)   │
│(self-hosted)│       │ tutor.py     │  = coach + show/score tools
└────────────┘        │ pipeline.py  │  = STT · LLM · TTS · VAD · turn
                      └──────────────┘
```

---

## 2. End-to-end runtime flow

The full lifecycle of one practice session, from name entry to persistence.

### 2.1 Connect (frontend → backend)

1. **Landing** (`app/page.tsx`): learner types a **handle** and picks a
   **language** (`es`/`fr`/`it`). Both are cached in `localStorage`
   (`lingua.handle`, `lingua.language`) so returning is one click.
2. Navigate to `/practice` → `Session` calls
   **`fetchConnectionDetails(handle, language)`** (`lib/api.ts`), a
   `POST /session/token` to the backend.
3. **Backend** (`app.py :: issue_token`):
   - `learner_id = f"{handle}:{language}"` — the **per-language** identity that
     keys all memory.
   - `store.get_or_create_learner(learner_id, ...)` — creates a profile on first
     contact, bumps `last_seen` otherwise.
   - Mints a LiveKit JWT with `tokens.create_access_token`:
     - **`identity = handle`** (the bare name → the coach greets you by it),
     - **`room = room_for_learner(learner_id)`** (per-language room),
     - **`metadata = {"language", "learner_id"}`** (JSON) — how the worker learns
       which language + memory key to use.
   - Returns `{ token, livekit_url, identity, language }`.

> **Why identity = handle, not a random id?** Cross-session memory only works if
> the same learner maps to the same key every time. A random per-connect identity
> (the usual starter default) would silently break memory. See
> [README → design decisions](./README.md#key-design-decisions--tradeoffs).

### 2.2 Join & warm up (frontend + voice ↔ LiveKit)

4. Frontend connects to the LiveKit **room** with the token and publishes its mic
   track (muted — push-to-talk).
5. LiveKit dispatches a **job** to the voice worker pool. `agent.py :: entrypoint`:
   - `ctx.connect()` → `wait_for_participant()` → read `participant.identity`
     (the handle) and parse `participant.metadata` → `language`, `learner_id`.
   - **Load content + memory** via the backend HTTP client
     (`BackendClient`, `voice → backend`, no Redis here):
     - `GET /exercise` → the authored item list,
     - `GET /learners/{learner_id}/review-items?n=…` → SRS-ranked weak items.
   - **`_lead_with_weak_words(items, review)`** reorders so words the learner
     *previously got wrong* lead, then the rest keep authored order. New learners
     → list unchanged.
   - `prompts.build_instructions(name, language, items, resuming)` → the system
     prompt for this specific learner/session.
   - `pipeline.build_session(cfg, vad, language)` → the STT/LLM/TTS/VAD/turn
     `AgentSession` (see §4).
   - Constructs **`LinguaTutor`** (`tutor.py`) with the items, room, and backend
     client, then `session.start(agent, room)`.

### 2.3 The exercise loop (voice, driven by the LLM via tools)

6. Kickoff: `session.generate_reply(...)` tells the coach to greet by name **in
   English**, explain the exercise, and show the first item. From there the LLM
   drives the loop by calling three **function tools** on `LinguaTutor`:

   | Tool | What it does | UI event emitted | Backend call |
   | --- | --- | --- | --- |
   | **`show_item(prompt_en, prompt_target)`** | Shows the picture, increments progress, then the coach says the target word aloud and asks the learner to repeat. | `item` | — |
   | **`score_item(prompt_en, prompt_target, passed, tip)`** | Records the attempt; 👍/👎 to the UI; on 👎 the coach models the word again; advances. | `item_result` | `POST …/attempt` |
   | **`finish_exercise()`** | Ends after the last item; shows the final score. | `exercise_end` | — |

   Between tools, the **spoken turn** runs through the pipeline: learner audio →
   **STT** → **LLM** (coach reasoning + tool calls) → **TTS** → audio back. VAD +
   the multilingual turn detector decide when a turn is over.

7. **Scoring is honest.** STT returns *text*, not phoneme scores, so `passed`
   reflects whether the transcript **matched the target word** (intelligibility),
   not a fake accent grade. `score_item` keys the SRS record by the **English
   prompt** (`prompt_en`) — the stable, cross-language identifier — so weak words
   resurface next session regardless of language.

### 2.4 Persist & resume

8. Every `score_item` → `POST /learners/{learner_id}/attempt` →
   `store.record_attempt`: updates the item's **SRS schedule** (§3.2) and bumps
   per-skill stats (`pronunciation` accuracy over time).
9. On disconnect, `agent.py :: on_shutdown` → `POST …/sessions` saves a session
   summary (topics, new words). The backend client is then closed.
10. **Next time** the same handle+language connects, step 5's `review-items` call
    returns the now-overdue weak words, and `_lead_with_weak_words` floats them to
    the front — the spaced-repetition loop closes.

### 2.5 Sequence diagram

```
Learner    Frontend          Backend            LiveKit         Voice worker
  │  name+lang  │                │                  │                 │
  ├────────────►│ POST /session/token               │                 │
  │             ├───────────────►│ create learner   │                 │
  │             │                │ mint JWT(identity=handle,          │
  │             │◄───────────────┤   room, metadata) │                 │
  │             │  connect(token)│                  │                 │
  │             ├──────────────────────────────────►│  dispatch job   │
  │             │                │                  ├────────────────►│ entrypoint
  │             │                │  GET /exercise    │                 │
  │             │                │◄──────────────────────────────────┤
  │             │                │  GET /review-items│                 │
  │             │                │◄──────────────────────────────────┤ reorder weak-first
  │             │                │                  │  greet + show 1st│
  │             │◄─── `item` (data ch) ─────────────┼─────────────────┤ show_item()
  │  hold-to-talk / speak        │                  │  audio ─────────►│ STT→LLM→TTS
  │             │◄─── audio ──────────────────────  │◄────────────────┤
  │             │◄─── `item_result` 👍/👎 ──────────┼─────────────────┤ score_item()
  │             │                │  POST /attempt (SRS update)         │
  │             │                │◄──────────────────────────────────┤
  │            ...repeat per item...                │                 │
  │             │◄─── `exercise_end` ───────────────┼─────────────────┤ finish_exercise()
  │  End session│                │                  │  disconnect     │
  │             │                │  POST /sessions ◄─────────────────┤ on_shutdown
```

---

## 3. Data model & persistence

### 3.1 Redis keyspace

All keys are namespaced by the **per-language identity** `{handle}:{lang}`
(`store.py :: _k(identity, suffix)` → `learner:{identity}:{suffix}`). This is why
`Ketan:es` and `Ketan:fr` are separate journeys.

| Key | Type | Contents |
| --- | --- | --- |
| `learner:{handle}:{lang}:profile` | string (JSON) | `Profile` — CEFR level, native/target lang, `created_at`, `last_seen` |
| `learner:{handle}:{lang}:vocab` | hash (by English prompt) | `VocabItem` per practiced word — `seen/correct/ease/due_at` (the SRS record) |
| `learner:{handle}:{lang}:skills` | hash (by skill) | rolling `{seen, correct}` per skill (e.g. `pronunciation`) |
| `learner:{handle}:{lang}:sessions` | list (JSON) | `SessionSummary` appended per session |

Domain shapes live in `backend/models.py` (pydantic) and are the **contract** the
voice + frontend clients depend on.

### 3.2 Spaced repetition (`backend/srs.py`)

A small SM-2-flavoured scheme over `VocabItem`. Pure functions (`now` injected),
so trivially unit-testable without Redis.

- **`schedule_after_review(item, correct, now)`**
  - correct → `ease += 0.1` (cap `3.0`), next due `= now + BASE(6h) · ease ·
    max(1, correct)` — pushed further out each time.
  - wrong → `ease -= 0.2` (floor `1.3`), next due `= now + 60s` — comes right back.
- **`select_review_items(items, n, now)`** ranks by
  `(overdue?, accuracy, ease, due_at)` — overdue first, then weakest — and returns
  the top `n`. Empty for a brand-new learner (caller falls back to the curriculum).

> Intervals are in **hours, not days**, deliberately, so weak words actually
> resurface across nearby sessions in a demo instead of weeks later.

---

## 4. The voice/AI pipeline (`voice/pipeline.py`)

`build_session(cfg, vad, language)` assembles a LiveKit `AgentSession` from
env-selected providers. Two paths, chosen by `USE_LIVEKIT_INFERENCE`:

| Stage | Self-hosted (BYO keys, default) | LiveKit Inference (single key) |
| --- | --- | --- |
| **STT** | `deepgram` (`multi`) or `openai` (target lang) | `inference.STT` |
| **LLM** | `anthropic` Claude (`claude-sonnet-5`) | Claude via plugin* / `inference.LLM` |
| **TTS** | `cartesia` or `openai`, optional `voice_id` | `inference.TTS` |
| **VAD** | Silero (loaded once in `prewarm`) | Silero |
| **Turn** | `turn_detector.multilingual.MultilingualModel` | `inference.TurnDetector` |

\* LiveKit Inference has no Anthropic models, so when `LLM_PROVIDER=anthropic` the
LLM stays on the direct Claude plugin even on the Inference path.

Provider/model/voice are **all env-driven** (`voice/config.py`, read from the root
`.env`) — STT/LLM/TTS can be swapped with **no code change**. Because pedagogy
(`tutor.py`) is separate from transport (`pipeline.py`), swapping a provider never
touches the coach logic.

---

## 5. Wire protocols

### 5.1 Backend REST API (`backend/app.py`)

| Method & path | Purpose | Caller |
| --- | --- | --- |
| `GET /health` | liveness (compose healthcheck) | infra |
| `POST /session/token` | mint LiveKit token from `{handle, language}` | frontend |
| `GET /exercise` | the authored item list | voice |
| `GET /learners/{identity}` | learner snapshot (profile) | voice |
| `POST /learners/{identity}/vocab` | upsert an SRS vocab item | (admin/tests) |
| `GET /learners/{identity}/review-items?n=` | SRS-ranked weak items | voice |
| `POST /learners/{identity}/attempt` | record one pronunciation attempt | voice |
| `POST /learners/{identity}/sessions` | append a session summary | voice |

`{identity}` here is the **per-language** `learner_id` (`handle:lang`).

### 5.2 The `tutor-ui` data channel (voice → frontend)

A **one-way** side channel over LiveKit (topic `tutor-ui`, reliable). Audio flows
through the media tracks; this carries the flashcard UI state as `{type, data}`
JSON. Emitted by `voice/ui_events.py`; decoded + reduced by
`frontend/lib/tutorEvents.ts` (pure, unit-tested) and wired to React via
`useTutorEvents.ts` (`useDataChannel` → `useReducer`).

| Event `type` | `data` | Rendered as |
| --- | --- | --- |
| `item` | `{image, emoji, prompt_en, prompt_target, index, total}` | the flashcard + progress |
| `item_result` | `{passed, tip}` | 👍 / 👎 (+ optional tip) |
| `exercise_end` | `{correct, total}` | final score screen |
| `error` | `{message, fatal}` | error banner (e.g. provider 429/quota, surfaced by `agent.py :: _friendly_error`) |

> `exercise_start {total}` is defined in the event union and handled by the
> reducer, but the agent currently starts straight into the first `item` rather
> than emitting it — a harmless forward-compatible slot.

---

## 6. Deployment topology (`docker-compose.yml`)

Five services, one root `.env` (no secrets hardcoded). Startup order is enforced
by healthchecks: **redis → livekit / backend → voice / frontend**.

| Service | Image / build | Ports | Depends on |
| --- | --- | --- | --- |
| `redis` | `redis:7-alpine` (AOF persistence, volume `redis-data`) | `6379` | — |
| `livekit` | `livekit/livekit-server` (`--node-ip 127.0.0.1`) | `7880` (WS), `7881` (TCP fallback), `50000-50019/udp` (media) | redis (healthy) |
| `backend` | `./backend` | `8000` | redis (healthy) |
| `voice` | `./voice` (`LIVEKIT_URL=ws://livekit:7880`, `BACKEND_URL=http://backend:8000`) | — | backend (healthy) + livekit |
| `frontend` | `./frontend` (`NEXT_PUBLIC_*` inlined at build) | `3000` | backend (healthy) |

**Volumes for live editing (no rebuild):** `backend/curriculum` (exercise YAML,
picked up on `docker compose restart backend`) and `frontend/public/flashcards`
(images served live).

**Self-host media gotcha:** browser↔SFU WebRTC over Docker needs reachable
UDP/TCP ports and an advertised IP. Mitigated with `--node-ip 127.0.0.1`, the
published TCP fallback (`7881`), and the UDP range. If local networking still
misbehaves, LiveKit Cloud is a one-line `.env` switch (`USE_LIVEKIT_INFERENCE` +
the cloud `LIVEKIT_URL`/keys).

---

## 7. Where scaling pressure lands

The component split is already the foundation; at 10k concurrent sessions the
binding constraints are **media capacity** and **provider rate limits**, not app
code. The stateless voice worker is the layer that grows most (autoscale on
active-session count); the backend splits hot state (Redis) from durable history
(Postgres); model providers get multi-provider fallback + TTS caching per
`(word × language × voice)`. Full write-up in
[README → scaling](./README.md#how-id-scale-this-to-10000-concurrent-sessions).

---

## 8. File map (the parts that matter)

```
backend/src/backend/
  app.py            REST surface + create_app factory (DI for tests)
  models.py         pydantic domain shapes = the client contract
  store.py          the ONLY Redis owner (profile/vocab/skills/sessions)
  srs.py            spaced-repetition schedule + selection (pure)
  curriculum.py     load + validate exercise.yaml at startup (fail fast)
  tokens.py         LiveKit JWT minting (identity=handle, per-lang room)
  config.py         env-driven settings
  curriculum/exercise.yaml   authored items (English, one file, all langs)

voice/src/voice/
  agent.py          entrypoint: wire layers per job, weak-first reorder, shutdown
  tutor.py          LinguaTutor coach + show/score/finish tools (conversation)
  pipeline.py       STT/LLM/TTS/VAD/turn assembly (voice/AI, provider-swappable)
  prompts.py        per-learner system instructions
  ui_events.py      publish `tutor-ui` data-channel events
  backend_client.py async HTTP client (voice holds NO state)
  config.py         env-driven provider/model selection

frontend/
  app/page.tsx              landing: handle + language → localStorage
  app/practice/page.tsx     → Session → PracticeRoom
  components/PracticeRoom.tsx  voice UI: visualizer, push-to-talk, flashcard
  components/FlashcardExercise.tsx  renders tutor-ui state
  lib/api.ts                POST /session/token
  lib/tutorEvents.ts        parse + reduce data-channel events (pure)
  lib/useTutorEvents.ts     LiveKit data channel → React state
```
