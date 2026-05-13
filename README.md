# Meridian — Server

FastAPI + LangGraph backend for the Meridian learner orchestration layer.
See [`docs/rfc.md`](../docs/rfc.md) for the full design rationale.

## Stack

| Layer            | Choice                                       |
| ---------------- | -------------------------------------------- |
| Language         | Python 3.12                                  |
| Web              | FastAPI + uvicorn                            |
| Orchestration    | LangGraph (`astream_events(version="v2")`)  |
| LLMs             | OpenAI via `langchain-openai`                |
| CRM              | HubSpot (real) + stub fallback               |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic               |
| Database         | SQLite (local + Fly Volume in prod)          |
| Resilience       | `httpx`, `tenacity`, custom circuit breaker  |
| Observability    | `structlog` + optional LangSmith             |
| Pkg / venv       | `uv`                                         |

## Quick start

```bash
cd server
uv sync
cp .env.example .env
# fill in OPENAI_API_KEY; CRM_PROVIDER=stub works without HubSpot
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/learner/stub-001
```

Stream a chat (the canonical compound query from the RFC):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "learner_id": "stub-001",
    "message": "What program is right for me, and what jobs does it lead to once I graduate?"
  }'
```

Expect to see `status` events for each LangGraph node, `delta` events with
streamed synthesis tokens, a `final` event with metadata, and a `done`
terminator.

## Endpoints

| Method | Path                  | Purpose                                                         |
| ------ | --------------------- | --------------------------------------------------------------- |
| GET    | `/health`             | Liveness + CRM provider status + configured model names         |
| GET    | `/learner/{id}`       | Resolve a `LearnerProfile` via the active CRM client            |
| POST   | `/chat`               | SSE stream: `status`, `delta`, `error`, `final`, `done` events  |

## Switching CRM provider

```bash
# Real HubSpot — requires the developer-portal setup in RFC §4.6
CRM_PROVIDER=hubspot
HUBSPOT_ACCESS_TOKEN=pat-...

# Offline / eval mode — same interface, JSON-backed
CRM_PROVIDER=stub
```

The factory in `app/clients/crm/base.py` is the only place that branches on the
env var; nothing else in the orchestrator knows the difference.

## Tests

```bash
uv run pytest
```

Test layers:
- `test_stub_crm.py` — stub CRM correctness
- `test_hubspot_circuit_breaker.py` — failure mode + circuit breaker (no network)
- `test_routing.py` — pure routing function
- `test_schemas.py` — Pydantic contracts

LLM-touching tests are deliberately out of scope here — that surface lives in
`evals/` (Phase 3).

## Layout

```
server/
├── app/
│   ├── main.py                    # FastAPI app + endpoints
│   ├── config.py                  # pydantic-settings
│   ├── api/sse.py                 # LangGraph events → SSE wire protocol
│   ├── clients/
│   │   ├── llm.py                 # ChatOpenAI factory + cost estimation
│   │   └── crm/                   # CRMClient interface + stub + HubSpot
│   ├── orchestrator/
│   │   ├── graph.py               # LangGraph wiring + routing
│   │   ├── state.py               # OrchestratorState (TypedDict + reducers)
│   │   ├── nodes/                 # load_context, plan, synthesize, persist
│   │   └── agents/                # discovery, career
│   ├── db/                        # SQLAlchemy models, session, repository
│   ├── data/                      # programs.json, careers.json, learners.json
│   ├── schemas/                   # Pydantic: LearnerProfile, ChatRequest, events
│   └── observability/tracing.py   # structlog + LangSmith opt-in
├── alembic/                       # migrations
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```
