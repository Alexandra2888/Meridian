# Meridian

> **Meridian**: the line along which disconnected things align. The orchestration layer that pulls independent learner-facing agents onto a single path, so one learner question gets one coherent answer.

A learner asking a compound question — _"What program is right for me, and what jobs does it lead to once I graduate?"_ — should not have to bounce between unconnected chat agents. Meridian routes the query across a Discovery and a Career agent in parallel, pulls live CRM context from HubSpot, and synthesizes a **single** streamed response.

The design rationale lives in [`docs/rfc.md`](docs/rfc.md). This README is operator-facing — how to run it, where the pieces live.

---

## What's in the box

| Folder    | Stack                                                                       |
| --------- | --------------------------------------------------------------------------- |
| `server/` | FastAPI + LangGraph orchestrator, SQLAlchemy/Alembic, OpenAI, HubSpot       |
| `client/` | Next.js 16 (App Router) + React 19, Tailwind v4, shadcn/ui, Zustand         |
| `docs/`   | `rfc.md` — full design RFC, decisions + alternatives considered             |

The server speaks SSE; the client renders the orchestration trace as it streams.

---

## Quick start

Run both halves in two terminals. The Next.js route handlers proxy through to FastAPI, so the browser never talks to the backend directly.

### 1. Server (`localhost:8000`)

```bash
cd server
uv sync
cp .env.example .env             # fill in OPENAI_API_KEY; CRM_PROVIDER=stub works offline
uv run alembic upgrade head      # creates messages + conversations tables
uv run uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/learner/stub-001
```

See [`server/README.md`](server/README.md) for the full endpoint table, CRM provider switch, and layout.

### 2. Client (`localhost:3000`)

```bash
cd client
pnpm install
cp .env.example .env             # API_URL=http://localhost:8000 by default
pnpm dev
```

Open <http://localhost:3000>. Pick a learner from the header, ask a question, and watch the orchestration trace render alongside the streamed answer.

---

## Tests

| Suite             | What it covers                                                                                       | Command                                  |
| ----------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Server (pytest)   | Repo CRUD, conversation API, title generation (LLM mocked), routing, schemas, stub CRM, HubSpot CB   | `cd server && uv run pytest`             |
| Client (e2e)      | Happy path: load → send → trace + cost badges → reload persists → rename → delete → mobile + 404     | `cd client && pnpm test:e2e`             |

The Playwright suite spawns both servers via its `webServer` config and reuses already-running ones if present.

---

## Reading order

1. [`docs/rfc.md`](docs/rfc.md) — design rationale, alternatives considered, scope cuts. Start here if you want to understand *why* the system is shaped this way.
2. [`server/README.md`](server/README.md) — operator runbook for the orchestrator: endpoints, env vars, layout, CRM switch.
3. [`client/README.md`](client/README.md) — operator runbook for the chat UI.
