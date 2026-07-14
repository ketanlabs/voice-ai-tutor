# Workflow — how I built this with AI

This project was built end-to-end using an AI coding harness. Below is exactly
which tools/models I used and, more importantly, *how* I used them to move fast
without shipping guesswork.

## Tools, models, and harnesses

| Tool / harness | Model | Role |
| --- | --- | --- |
| **Claude Code** (Anthropic's agentic CLI) | **Claude Opus 4.8** | Primary driver — planning, writing code, running commands, iterating. |
| **Plan mode** (Claude Code) | Opus 4.8 | Forced an explicit, reviewed plan before any code was written. |
| **Web search / fetch** (built into the harness) | — | Verifying the *current* LiveKit Agents API against live docs, not memory. |
| **Local toolchain the agent drove** | — | `uv` (Python envs), `npm`/Next.js, `pytest`, `vitest`, `git`, `gh`. |

## How I actually used them

**1. Plan first, in plan mode.** I started in Claude Code's plan mode, which is
read-only until a plan is approved. I iterated the plan with the reviewer through
several rounds — subject choice, the persistence model (curriculum in YAML vs
Redis), the **three-component split** (session / conversation / voice), the test
strategy, and the exact deliverables. Nailing these decisions on paper first
meant the implementation was mostly mechanical.

**2. Verify APIs instead of trusting memory.** LiveKit's Agents SDK moves fast,
so before writing the voice agent I:
- **web-searched the official quickstart** to confirm the modern `AgentSession` /
  `TurnHandlingOptions` shape and the `agent-starter-*` templates;
- **installed the real packages into a scratch venv and introspected them** with
  `inspect.signature(...)` — `livekit-agents 1.6.5`, `deepgram.STT`,
  `anthropic.LLM`, `cartesia.TTS`, `inference.*`, `rtc.publish_data`, and the
  `@livekit/components-react` exports/types.

This "introspect-then-write" loop is the single biggest speed/quality win: it
turned an error-prone integration into copy-from-verified-signatures.

**3. Build in dependency order, validating each layer.** Backend first (everyone
depends on it), then voice, then frontend, then Docker. After each layer I ran
the real tooling in the harness:
- backend → `pytest` (22 tests: SRS, curriculum validation, Redis store via
  `fakeredis`, API) — **green before moving on**;
- voice → imported every module to catch wiring errors without needing a live
  call;
- frontend → `next build` (typechecked) + `vitest` — **green** before Docker.

**4. Let the agent run the loops, I steer.** Claude Code executed the shell
commands (venvs, installs, test runs, git), read the failures, and fixed them.
My job was direction and review: catching design gaps (e.g. that a random
per-connect LiveKit identity would silently break cross-session memory, and that
"pronunciation scoring" from STT is not real and shouldn't be faked).

**5. Keep the human decisions with the human.** Where a choice was genuinely the
reviewer's — subject, coverage depth, Docker-only vs native dev, CI or not — I
surfaced it as an explicit question rather than assuming.

## What I'd do next with more time
- Run the full `docker compose up` on a machine with Docker to record the video
  walkthrough (this environment had no Docker daemon; all components were verified
  natively — pytest, `next build`, Vitest, module imports).
- Add a fake-LLM behavioral test for the voice tools using the Agents test
  harness, and wire `make test` into GitHub Actions.
