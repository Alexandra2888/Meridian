# Meridian — Server

FastAPI + LangGraph backend for the Meridian learner orchestration layer.
See [`docs/rfc.md`](../docs/rfc.md) for the full design rationale.

**Live API:** https://meridian-g-q4wg.fly.dev · `GET /health` for status.

## Stack

| Layer            | Choice                                                                  |
| ---------------- | ----------------------------------------------------------------------- |
| Language         | Python 3.12                                                             |
| Web              | FastAPI + uvicorn                                                       |
| Orchestration    | LangGraph (`astream_events(version="v2")`)                              |
| LLMs             | OpenAI via `langchain-openai`                                           |
| CRM              | HubSpot (real) + stub fallback, switched via `CRM_PROVIDER`             |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic                                          |
| Database         | SQLite (local + Fly Volume in prod, mounted at `/data`)                 |
| Resilience       | `asyncio.wait_for` timeouts, `tenacity` retries, custom circuit breaker |
| Observability    | `structlog` + optional LangSmith via `LANGSMITH_API_KEY`                |
| Pkg / venv       | `uv`                                                                    |

## Quick start

Local dev runs on port **8000**. The deployed Fly container runs on **8080**
(both are normal — Dockerfile + `fly.toml` set the prod port).

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

| Method | Path                  | Purpose                                                              |
| ------ | --------------------- | -------------------------------------------------------------------- |
| GET    | `/health`             | Liveness + CRM provider status + configured model names              |
| GET    | `/learners`           | Lightweight list of learners (backs the FE picker)                   |
| GET    | `/learner/{id}`       | Resolve a `LearnerProfile` via the active CRM client                 |
| GET    | `/conversations`      | A learner's conversations (sidebar). Query: `?learner_id=…&limit=50` |
| GET    | `/conversations/{id}` | Full conversation with messages + per-message telemetry              |
| PATCH  | `/conversations/{id}` | Rename a conversation. Body: `{"title": "…"}`                        |
| DELETE | `/conversations/{id}` | Delete a conversation (cascades to messages); 204 on success         |
| POST   | `/chat`               | SSE stream: `status`, `delta`, `error`, `final`, `done` events       |

## Switching CRM provider

The **deployed** environment uses real HubSpot. The **local default** uses
the stub (no HubSpot setup required to clone-and-run).

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
uv run python -m evals.run_evals
```

Test layers:

- `test_stub_crm.py` — stub CRM correctness
- `test_hubspot_circuit_breaker.py` — failure mode + circuit breaker (no network)
- `test_routing.py` — pure routing function
- `test_schemas.py` — Pydantic contracts
- `test_conversation_repo.py` — `ConversationRepo` CRUD against an in-memory SQLite (cascading deletes, recency ordering, `set_step_durations`)
- `test_conversations_api.py` — HTTP layer for the conversation endpoints via `AsyncClient` over ASGI
- `test_title_generation.py` — background title generator with a stubbed LLM
- `evals/run_evals.py` — 15-case golden dataset for routing accuracy + LLM-judged response quality

`pytest` avoids live LLM calls. The eval harness intentionally touches the
orchestrator and judge model, forces `CRM_PROVIDER=stub` for repeatability, writes
per-case rows to `eval_runs`, and emits a markdown summary under
`evals/results/`.

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
│   │   ├── nodes/                 # load_context, plan, discovery_agent, career_agent, synthesize, persist (+ async title)
│   │   └── agents/                # discovery, career
│   ├── db/                        # SQLAlchemy models, session, repository
│   ├── data/                      # programs.json, careers.json, learners.json
│   ├── schemas/                   # Pydantic: LearnerProfile, ChatRequest, events
│   └── observability/tracing.py   # structlog + optional LangSmith via env var
├── alembic/                       # migrations
├── evals/
│   ├── golden_dataset.jsonl       # labelled routing + quality cases
│   └── run_evals.py               # routing accuracy + LLM-as-judge harness
├── tests/
├── Dockerfile                     # binds to port 8080 (Fly target)
├── fly.toml                       # Fly.io deployment config
├── pyproject.toml
└── .env.example
```
