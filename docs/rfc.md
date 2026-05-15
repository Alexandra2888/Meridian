# RFC: Meridian — Learner Orchestration Layer

> **Meridian**: the line along which disconnected things align. The orchestration layer that pulls independent learner-facing agents onto a single path, so one learner question gets one coherent answer.

|              |                                                                                |
| ------------ | ------------------------------------------------------------------------------ |
| **Status**   | v1 — implemented and deployed                                                  |
| **Author**   | Alexandra Moldovan                                                             |
| **Live app** | [https://meridian-one-mu.vercel.app](https://meridian-one-mu.vercel.app)       |
| **Live API** | [https://meridian-g-q4wg.fly.dev](https://meridian-g-q4wg.fly.dev) (`/health`) |

---

## 0. Context

This RFC is the design document for the Meridian prototype. It captures every architectural decision, the alternatives considered, and the rationale — so the implementation is grounded in deliberate choices rather than improvisation, and so the design is defensible end-to-end on the demo call.

The repo's `README.md` is the operator-facing document (how to run, what's deployed where, what's stubbed). This RFC is the design-facing document (why the system is shaped this way). The two are complementary, not redundant.

### 0.1 On scope: product, not prototype

Meridian originated as a response to a take-home design brief that asked for a 6-hour orchestration prototype. It is built as a **live, deployed product** instead — running at the URLs at the top of this document, against real HubSpot, with persistent storage on a Fly Volume. The framing:

> **The brief asked for a prototype. Meridian is a product.**

**Why a live product:**

- The stated problem — disconnected learner-facing agents — is a _learner-facing_ problem. Solving it visibly, on a URL a learner can actually visit, makes the demonstration of value tangible.
- Real HubSpot integration tests the integration-brittleness risk against actual API quirks, rate limits, and network conditions. A stub cannot.
- Streaming UX with live orchestration events (§4.7) exposes the architecture as it runs — the orchestrator's parallel execution is visible in the UI, not just claimed in the README.
- Live deployment forces the architecture to survive its first real environment, which is where most prototypes break.

**Why this isn't scope drift:**

- The brief is delivered exactly: orchestration between agents + one external system + a coherent response. The external system is real; the response is reachable from a real URL.
- Cuts are still extensive (see §2 non-goals): no auth, no Redis, no PII redaction, no light-mode toggle, no admin UI, no custom domain, no staging environment, no monitoring/alerting beyond defaults. Every one of those would be in a production-grade product. Scoping discipline lives in _which_ additions made the cut and _which_ were refused.
- No auth is the single biggest scope cut. It removes ~80% of deployment complexity (login flows, sessions, JWT, password resets, OAuth, RBAC) — which is what makes the "live product" path tractable inside the time budget.

**The accepted trade:** going past the brief's hour suggestion is a deliberate choice. The cuts are visible, the rationale is explicit, and the architectural decisions are owned end-to-end in this document.

---

## 1. Problem statement

Online universities and EdTech platforms commonly run multiple learner-facing AI agents (Discovery/Admissions, Career Advisor, Financial Aid, Technical Support) built independently on different stacks with no shared context. A learner asking a compound question — _"What program is right for me, and what jobs does it lead to once I graduate?"_ — has to bounce between agents that do not know each other exist.

Meridian is the orchestration layer that fixes this pattern. The design brief that motivated this v1:

1. Route a single learner query across ≥2 agents and ≥1 external system.
2. Look up learner enrolment status from a CRM (HubSpot or a stub — Meridian uses the real HubSpot API in production).
3. Return **one coherent response**, not three disconnected ones.
4. Design for ~10k learners with a clear path to production.

**Definition of success:**

- Working end-to-end product: one learner question, one synthesized answer, streamed in real-time with visible orchestration events.
- Architecture that reads as deliberate and defensible end-to-end, with each external dependency abstracted behind an interface.
- Both technical and non-technical stakeholders can understand the value and the design from the README and the demo alone.

---

## 2. Goals & non-goals

### Goals (v1, in scope)

- ✅ Single orchestrator that classifies intent and routes to specialist agents
- ✅ Two specialist agents: Discovery (program recommendation) + Career (job outcomes)
- ✅ One external system: **live HubSpot CRM integration** (real API, real test contacts) with a stub available as fallback for offline development and evals
- ✅ **Deployed live**: API on Fly.io (Frankfurt, with SQLite on a 1 GB Fly Volume), frontend on Vercel — both URLs at the top of this document
- ✅ Coherent synthesis: when both agents are needed, output reads as one voice, not concatenated
- ✅ Conversation state across turns (so follow-ups work)
- ✅ Per-learner conversation history with a sidebar — rename, delete, switch between conversations
- ✅ Minimal but real evals: a small golden dataset + routing accuracy + LLM-as-judge response quality
- ✅ Observability: trace every run, see which agents fired and why
- ✅ Cost & latency tracking per request
- ✅ **Streaming UX with live orchestration events** — agent-status events emit as each LangGraph node runs (Discovery started → Career started → Synthesis started → tokens streaming → final metadata). The UI exposes the architecture as it runs.
- ✅ **Learner-facing frontend** (Next.js 16): chat interface, visible agent trace panel, visible learner context from CRM
- ✅ **Considered visual craft**: dark-default aesthetic, mobile-first responsive, semantic design tokens layered on shadcn. The frontend reflects the author's senior frontend engineering background; visual polish is part of the architecture's value, not decoration over it.
- ✅ Clear stubbed-vs-real boundary documented in README (mostly real; the stub exists as a dev fallback)

### Non-goals (cut from v1, justified in memo)

- ❌ **Auth** — prototype-scope, single demo learner ID selected from URL param; v2 work
- ❌ **Real Canvas/LMS integration** — not in Scenario A
- ❌ **Multi-tenancy / org isolation** — single-tenant prototype
- ❌ **Caching layer (Redis)** — not justified at 10k learners; documented in §10
- ❌ **PII redaction pipeline** — flagged in §8, documented but not built
- ❌ **A/B testing infrastructure** — flagged in memo as "next two weeks" work
- ❌ **Light-mode toggle, multi-theme support, custom design-system package** — dark-only in v1; design tokens live inline. Theming is a v2 conversation.

The discipline of cutting these _deliberately_ is itself part of the work.

---

## 3. Scenario selection

Scenario A (orchestration) is the chosen scenario. The comparison:

| Factor                            | Scenario A (Orchestration)                                               | Scenario B (Adaptive tutor)                                            |
| --------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Maps to brief's stated motivation | ✅ Directly — the brief opens with the disconnected-agents problem       | ⚠️ Valuable but less directly aligned with the brief's primary problem |
| Demo legibility in 15 min         | ✅ One question → one synthesized answer is instantly legible            | ⚠️ Adaptation only shows value over many turns                         |
| Multi-agent architecture surface  | ✅ Routing, parallelism, synthesis — core orchestration concepts visible | ⚠️ Adaptation logic is primarily single-agent learner-state work       |
| External system integration       | ✅ CRM is central to the scenario; surfaces real integration patterns    | ⚠️ LMS integration is required but less architecturally central        |
| Productionization story           | ✅ Clear path: orchestrator + agent registry scales to N agents          | ✅ Also clear: learner-state model scales to many topics               |

**Decision: Scenario A.** Demo-friendly, directly addresses the disconnected-agents problem the brief opens with, and exercises the multi-agent + integration concerns that are the architecturally interesting work.

### 3.1 The compound query as the canonical test

Throughout this document, the brief's example question is treated as the canonical test case:

> _"What program is right for me, and what jobs does it lead to once I graduate?"_

This single query forces every architectural decision: it requires routing to two agents, parallel execution for latency, synthesis to one voice, and CRM context to personalize. Any architecture that handles this query well handles the rest. Every design choice below is judged against it.

---

## 4. Architecture

### 4.0 Backend stack at a glance

Pulled together here so the full stack is visible in one place. Each choice is justified in the subsection where it lives architecturally; this table is the index.

| Layer                  | Choice                                                                                                                            | Defended in                                                                                                                                                                                                      |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language               | **Python 3.12**                                                                                                                   | §0 — LLM ecosystem maturity; production AI experience for the author is in Python                                                                                                                                |
| Web framework          | **FastAPI**                                                                                                                       | §4.7 — native async, SSE-friendly via `StreamingResponse`, Pydantic-first                                                                                                                                        |
| Package + venv manager | **uv**                                                                                                                            | New industry default in 2026: 10–100× faster than pip, single tool replaces pip + venv + pip-tools                                                                                                               |
| Orchestration          | **LangGraph**                                                                                                                     | §4.4 — state-machine model for deterministic routing; native parallelism via `Send`; `astream_events` for the streaming event protocol                                                                           |
| LLM clients            | **OpenAI via `langchain-openai`**                                                                                                 | §4.5 — model-per-role configurable (planner/agent/synthesizer) via env vars; cross-provider support (Anthropic, Bedrock) is v2 — the factory in `clients/llm.py` is in place but only returns `ChatOpenAI` today |
| Validation + schemas   | **Pydantic v2**                                                                                                                   | Used everywhere — request/response models, structured LLM outputs from the planner, `LearnerProfile` shape, SSE event payloads. Single source of truth between agents and API.                                   |
| ORM                    | **SQLAlchemy 2.0** (async)                                                                                                        | §6 — works against SQLite today; Postgres-ready models for v2 migration                                                                                                                                          |
| Migrations             | **Alembic**                                                                                                                       | §6 — autogenerates from SQLAlchemy models; same migrations work against either engine                                                                                                                            |
| Database (local dev)   | **SQLite**                                                                                                                        | §6.1 — zero ops, anyone can clone and run, evals are deterministic                                                                                                                                               |
| Database (deployed)    | **SQLite on Fly Volume**                                                                                                          | §6.1, §9.3 — same engine as local; single-writer pattern fits v1 scale; defensible production choice                                                                                                             |
| CRM                    | **HubSpot** (`hubspot-api-client`) + stub fallback                                                                                | §4.6 — real API in production, stub via `CRM_PROVIDER=stub` for evals and offline dev                                                                                                                            |
| Observability          | **Structured logs** (`structlog`) + in-app trace panel + per-message DB metrics. Optional LangSmith hook via `LANGSMITH_API_KEY`. | §4.5, §7, §10 — every node traced in the trace panel, every LLM call costed and persisted. LangSmith is wired but off-by-default; promoting it to a production dependency (dashboards, alerts) is v2.            |
| Resilience             | `asyncio.wait_for` timeouts, `tenacity` retries, custom circuit breaker                                                           | §4.6 — applied to the HubSpot SDK client; same patterns ready for future external systems                                                                                                                        |
| Testing                | **pytest** + **pytest-asyncio**                                                                                                   | Repo CRUD, conversation API, title generation (LLM mocked), routing, schemas, stub CRM, HubSpot circuit breaker. LLM-touching tests live in `evals/`, not the unit suite.                                        |

**Deliberately not picked:**

- ❌ **Django / Flask** — Django is too much, Flask lacks async-first patterns. FastAPI is the right tier.
- ❌ **Poetry / Pipenv / Rye** — `uv` won this race in 2025; using anything else now is friction without payoff.
- ❌ **Pydantic v1** — v2 has been stable for over a year and the perf difference matters at synthesis latency.
- ❌ **Raw SQL** — SQLAlchemy 2.0's typed API is good enough that hand-written SQL would be a regression.
- ❌ **MongoDB / DynamoDB** — relational data, relational queries, no scale that needs NoSQL.
- ❌ **Celery / Redis queues** — the orchestrator is synchronous from the learner's perspective; background jobs are a v2 conversation.

**Why this combination is deliberate:**

1. Every choice has a clear technical reason — none of it is "X because I know X."
2. The combination is current-idiomatic for AI engineering in 2026: stable, not aging, not bleeding edge.
3. The cuts (no Celery, no Django, no Poetry) are as informative as the picks.

### 4.1 Shape: single orchestrator with a routing layer

Four shapes considered:

1. **Single mega-prompt** — one LLM call, all context dumped in. Cheap, fast, but unmaintainable past 2 agents and impossible to eval per-agent.
2. **Pure router** — classifier picks one agent; that agent answers alone. Doesn't handle compound questions ("program AND jobs") which is literally the example in the brief. **Disqualified.**
3. **Multi-agent with orchestrator** ← **chosen**. Orchestrator plans, dispatches in parallel where possible, synthesizes.
4. **Fully autonomous swarm** (agents talking to agents). Over-engineered for v1, hard to debug, hard to eval, expensive.

**Choice: #3.** The brief's example question is compound. A pure router cannot serve it. A swarm is overkill. An orchestrator with explicit routing logic is the right complexity tier for 10k learners and matches a multi-agent pattern the author has shipped to production previously.

### 4.2 Component diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI app                            │
│                                                              │
│  POST /chat  ──►  Orchestrator (LangGraph state machine)     │
│                        │                                     │
│                        ▼                                     │
│              ┌─────────────────────┐                         │
│              │  1. Load context    │ ◄── CRM (HubSpot/stub)  │
│              │     (CRM lookup)    │     (learner state)     │
│              └─────────┬───────────┘                         │
│                        ▼                                     │
│              ┌─────────────────────┐                         │
│              │  2. Plan / route    │ ◄── LLM (gpt-4o-mini)   │
│              │  → which agents?    │     intent classifier   │
│              └─────────┬───────────┘                         │
│                        ▼                                     │
│        ┌───────────────┼───────────────┐                     │
│        ▼               ▼               ▼                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │Discovery │   │ Career   │   │ (more in │                  │
│  │  Agent   │   │  Agent   │   │   v2)    │                  │
│  └─────┬────┘   └─────┬────┘   └──────────┘                  │
│        └───────┬──────┘                                      │
│                ▼                                             │
│        ┌─────────────────┐                                   │
│        │  3. Synthesize  │ ◄── LLM (gpt-4o)                  │
│        │  one response   │     unifies agent outputs         │
│        └────────┬────────┘                                   │
│                 ▼                                            │
│        ┌─────────────────┐                                   │
│        │  4. Persist     │ ──► SQLite (conversation log)     │
│        └────────┬────────┘     + trace store                 │
│                 ▼                                            │
│              Response                                        │
│                                                              │
│   (async, off-wire: title generator names the conversation)  │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 State machine (LangGraph)

Six registered nodes in `server/app/orchestrator/graph.py`:

- `load_context` → pulls learner record from CRM (HubSpot or stub)
- `plan` → LLM call: classifies intent into `{discovery, career, both, neither}`; outputs structured plan
- `discovery_agent` → conditional, runs if plan includes discovery
- `career_agent` → conditional, runs if plan includes career
- `synthesize` → unifies outputs into one coherent response (or echoes single-agent output if only one ran)
- `persist` → write conversation message + trace metadata to SQLite

Plus an **async title task** that fires after the response is delivered: when a conversation has no title yet, an LLM call generates a short label from the first user message + assistant reply. Runs off the SSE wire — the learner has already received the full response by the time it executes, so it never blocks streaming latency. Implemented as a background task rather than a graph node specifically because it isn't on the orchestration critical path.

Routing edges from `plan` are conditional on the plan output. Discovery and Career run **in parallel** when both are needed (LangGraph supports this natively via `Send` API). This matters for latency at scale.

### 4.4 Why LangGraph specifically (build vs buy)

| Option                        | Verdict                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LangGraph**                 | ✅ **Chosen.** State-machine model fits orchestration naturally. Built-in checkpointing for conversation state. Native parallelism via `Send` API. `astream_events(version="v2")` exposes node lifecycle events natively — which is what makes the streaming event protocol in §4.7 tractable. Production-ready tracing via LangSmith available when needed (v2). |
| Vanilla LangChain agents      | ❌ ReAct-style agents are non-deterministic in routing; harder to eval.                                                                                                                                                                                                                                                                                           |
| CrewAI                        | ⚠️ Higher-level abstraction, less control over routing logic. Good for autonomous swarms, less good for explicit orchestration.                                                                                                                                                                                                                                   |
| AutoGen                       | ⚠️ Same concern. Also Microsoft-flavored which is a stack mismatch.                                                                                                                                                                                                                                                                                               |
| Roll my own                   | ❌ Significant plumbing work without proportional payload; LangGraph already provides the primitives.                                                                                                                                                                                                                                                             |
| OpenAI Swarm / Assistants API | ⚠️ Vendor lock-in, weaker observability story, harder to swap models.                                                                                                                                                                                                                                                                                             |

**The principle in one line:** state machines are the right mental model for orchestration with deterministic routing — not just a trendy choice.

### 4.5 Model choices

| Step                  | Model               | Why                                                                                                          |
| --------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------ |
| Intent classification | `gpt-4o-mini` (T=0) | Cheap, fast, classification is easy. ~$0.0002/call. Temperature 0 for deterministic routing.                 |
| Discovery agent       | `gpt-4o-mini`       | Recommendation from a small program catalog — doesn't need frontier reasoning.                               |
| Career agent          | `gpt-4o-mini`       | Same — career advice grounded in retrieved job data.                                                         |
| Synthesis             | `gpt-4o` (T=0.4)    | Quality of final response matters most; this is what the learner reads. Small temperature for natural prose. |

Model choices are config values per role (`MODEL_PLANNER`, `MODEL_AGENT`, `MODEL_SYNTHESIZER`), not hardcoded — picked up by the LLM factory in `server/app/clients/llm.py`. Today the factory only returns `ChatOpenAI`; swapping the provider (Anthropic Claude, Bedrock) is a small extension to the factory rather than a model-name change, and is flagged as a v2 add.

**Cost back-of-envelope (per request, both agents firing):**

- Classify: ~$0.0002
- 2× agent calls: ~$0.001
- Synthesize: ~$0.005
- **~$0.006/request.** At 10k learners × 5 queries/month = 50k req/month ≈ **$300/month** in LLM costs. Trivially affordable.

### 4.6 CRM integration (live HubSpot + stub fallback)

The `CRMClient` interface is the architectural seam:

```python
class CRMClient(Protocol):
    async def get_learner(self, learner_id: str) -> LearnerProfile: ...
```

Two implementations, swappable via `CRM_PROVIDER` env var:

- **`HubSpotCRMClient`** — the production path, used by the deployed app. Uses the official `hubspot-api-client` Python SDK against a HubSpot developer account dedicated to this project.
- **`StubCRMClient`** — used for: (a) eval runs, (b) offline development, (c) demo fallback if HubSpot has an incident on demo day. Same interface, fake data.

`LearnerProfile` is a Pydantic model — the canonical shape the orchestrator consumes:

```python
class LearnerProfile(BaseModel):
    learner_id: str
    name: str
    email: str
    enrolment_status: Literal["prospect", "applied", "enrolled", "graduated"]
    program: Optional[str]            # e.g., "BBA Data Analytics"
    interests: list[str]              # e.g., ["data", "marketing"]
    career_goals: list[str]
    country: Optional[str]
```

**HubSpot field mapping** (lives in `server/app/clients/crm/hubspot.py`, documented inline):

| `LearnerProfile` field | HubSpot Contact property                                                                     |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| `learner_id`           | `hs_object_id` (HubSpot internal ID)                                                         |
| `name`                 | `firstname` + `lastname`                                                                     |
| `email`                | `email`                                                                                      |
| `enrolment_status`     | custom property: `meridian_enrolment_status` (dropdown: prospect/applied/enrolled/graduated) |
| `program`              | custom property: `meridian_program` (single-line text)                                       |
| `interests`            | custom property: `meridian_interests` (multi-checkbox, comma-separated)                      |
| `career_goals`         | custom property: `meridian_career_goals` (multi-line text)                                   |
| `country`              | `country` (standard property)                                                                |

**HubSpot setup (one-time, ~45 min):**

1. Free HubSpot developer account → create test portal
2. Create the 4 custom properties listed above on the Contact object
3. Seed 3–5 test contacts representing different lifecycle stages (prospect, applied, enrolled, graduated)
4. Generate a private app access token with `crm.objects.contacts.read` scope
5. Add token to `.env` and to the deployment environment (Fly.io secrets)

**Resilience patterns in `HubSpotCRMClient`:**

- 5-second timeout on every call via `asyncio.wait_for` (HubSpot p99 is ~1s but tail latency exists)
- Retry with exponential backoff on 429 (rate limit) and 5xx via `tenacity`, max 2 retries
- Circuit breaker: after 3 consecutive failures, fall through to a degraded mode. On the `/chat` path, the orchestrator proceeds with minimal context and notes "couldn't load profile" in the response — it never 500s the chat request. On `/learner/{id}`, the degraded mode returns 503, since there is no orchestrator context to fall back to and the learner card is the direct subject of the request.
- Structured logs on every HubSpot interaction: failure mode, circuit state, retry attempt. (Full per-call timing + status histograms are a v2 observability add — see §10.)

**Why this still uses the repository pattern even though we're going live:**
The `CRM_PROVIDER` env var lets the eval harness run against the stub (deterministic, no network, no rate limits), while production uses HubSpot. Same interface, both implementations live in the repo. This is the production pattern, not a workaround.

This is the single most important architecture decision for "productionization potential" scoring.

### 4.7 Streaming: live orchestration events

End-to-end orchestration (CRM lookup + plan + 2 parallel agents + synthesis) runs ~6–10 seconds. Sitting in a typing indicator that long during a demo _feels_ broken even when it isn't. More important: a credible AI product in 2026 streams. A non-streaming chat shipped to learners would feel dated on day one.

The chosen pattern is **lock-step orchestration events + token streaming**, not just token streaming. The UI exposes the architecture as it runs.

#### What the learner sees

Type the compound question → 200ms later, the trace panel starts populating _live_:

```
●  Loading your profile from HubSpot...           ✓ (180ms)
●  Planning route...                              ✓ (340ms)
●  Discovery agent thinking...        ┐
●  Career agent thinking...           │  in parallel
                                       ┘ ✓ (2.1s, 1.9s)
●  Synthesizing response...
   "Based on your interest in data and..." ← tokens streaming
```

The orchestration is the _show_, not just plumbing. The viewer sees Discovery and Career run in parallel because the UI literally renders them in parallel.

#### Event protocol (server-sent events)

The FastAPI `/chat` endpoint returns `StreamingResponse` emitting newline-delimited JSON events. Five event types:

| Event    | Emitted when                     | Payload                                                                     |
| -------- | -------------------------------- | --------------------------------------------------------------------------- |
| `status` | Each LangGraph node enters/exits | `{node, status: "started"\|"finished", duration_ms?}`                       |
| `delta`  | Synthesis LLM yields a token     | `{content: "...token..."}`                                                  |
| `error`  | Anything blows up                | `{message, recoverable}`                                                    |
| `final`  | End of run                       | `{agents_invoked, total_latency_ms, cost_usd, conversation_id, message_id}` |
| `done`   | Stream complete                  | (terminator, no payload)                                                    |

The `final` event carries everything the trace panel needs that _only_ exists once the run is complete. The `delta` stream is just the synthesis output — discovery/career agent calls are non-streaming (they're internal, the learner never sees their raw output).

#### LangGraph wiring

LangGraph's `astream_events(version="v2")` surfaces node lifecycle events natively. The pattern:

```python
async def chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        if kind == "on_chain_start" and event["name"] in NODE_NAMES:
            yield sse("status", {"node": event["name"], "status": "started"})
        elif kind == "on_chain_end" and event["name"] in NODE_NAMES:
            yield sse("status", {"node": event["name"], "status": "finished",
                                 "duration_ms": ...})
        elif kind == "on_chat_model_stream" and event["metadata"].get("node") == "synthesize":
            yield sse("delta", {"content": event["data"]["chunk"].content})
    yield sse("final", {...computed from final state...})
    yield sse("done", {})
```

The key trick: only synthesis tokens stream to the client. Internal agent LLM calls produce structured outputs the orchestrator consumes — they don't get piped to the learner.

#### Frontend consumption

The frontend consumes the SSE stream with a custom parser built on native `fetch` + `ReadableStream` rather than the Vercel AI SDK's `useChat`. Two reasons:

1. The five-event protocol above isn't a shape `useChat` understands natively — `status`/`final`/`error` events would need to be smuggled through `useChat`'s extension hooks, which costs more clarity than a custom parser saves.
2. Building the parser directly gives explicit control over event routing into two separate stores (messages vs trace) without fighting `useChat`'s assumptions about what a "message" is.

Two state stores on the FE:

- **Messages** — local state on the chat shell, contains the streamed assistant text built from `delta` events.
- **Trace** — Zustand store, populated from `status` events as they arrive, finalized by the `final` event. Mapped by `message_id` so each message has its own trace state.

Trace data also persists server-side per message (`agents_invoked` + `step_durations` on the `messages` row), so reloading a past conversation re-hydrates the trace panel from the DB rather than requiring the run to re-execute.

#### Why this matters more than "it streams faster"

The streaming pattern _is the product_. Watching agents fire in parallel, in real time, in the UI, while tokens stream is qualitatively different from "I sent a request and a response came back 8 seconds later" — same backend, completely different perceived experience. For an AI product in 2026, the latter feels dated; the former feels current.

This is also a forcing function for clean architecture. Streaming surfaces every latency bug, every blocking await, every mistakenly-sequential agent call. If it streams well, the orchestration is genuinely parallel.

---

## 5. Frontend

### 5.0 Frontend stack at a glance

Pulled together here so the full stack is visible in one place. Each choice is justified in the subsection where it lives architecturally; this table is the index.

| Layer              | Choice                                                         | Defended in                                                                                                       |
| ------------------ | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Framework          | **Next.js 16** (App Router) + **React 19**                     | §5.1 — daily driver, server-side route handlers handle the SSE proxy cleanly                                      |
| Language           | **TypeScript 5** (strict mode)                                 | Used everywhere; types mirror the FastAPI Pydantic schemas via a shared `lib/types.ts`                            |
| Styling            | **Tailwind CSS v4**                                            | §5.1 — utility-first speed with full token customization via CSS variables                                        |
| Components         | **shadcn/ui** (Radix primitives)                               | §5.1 — modern React conventions, copy-in primitives (not a runtime dependency)                                    |
| Chat state         | **Local component state + custom SSE parser**                  | §4.7 — native `fetch` + `ReadableStream` gives full control over the five-event protocol                          |
| Trace state        | **Zustand**                                                    | §4.7, §5.1 — side-channel store for orchestration events that don't fit the message model; mapped by `message_id` |
| Sidebar state      | **Zustand**                                                    | Mobile drawer open/close, kept separate from trace store for clarity                                              |
| Icons              | **lucide-react**                                               | shadcn default, tree-shakable                                                                                     |
| Data fetching      | **Native `fetch` in route handlers + React Server Components** | No SWR/React Query needed at this scope — endpoints are read-on-mount or driven by SSE                            |
| Runtime validation | **Zod**                                                        | Validates SSE event payloads on the client before they hit Zustand; same `LearnerProfile` shape as backend        |
| Linting            | **ESLint** + **Prettier**                                      | Next.js defaults                                                                                                  |
| Testing            | **Playwright** (e2e happy-path)                                | Cross-stack happy-path coverage (load → send → trace → reload → rename → delete → mobile + 404)                   |
| Pkg manager        | **pnpm**                                                       | Faster than npm, strict by default                                                                                |

**Deliberately not picked:**

- ❌ **Vercel AI SDK (`useChat`)** — considered and discarded. The five-event SSE protocol (§4.7) is richer than `useChat`'s message model. A custom parser is clearer than fighting the SDK's assumptions about what a message is.
- ❌ **Redux / Redux Toolkit** — Zustand is the right tier for two side-channel stores; Redux is over-engineered here.
- ❌ **React Query / SWR / TanStack Query** — only two endpoint families, both either read-on-mount or driven by SSE. The infrastructure isn't earning its keep.
- ❌ **styled-components / Emotion / vanilla-extract** — Tailwind covers everything; runtime CSS-in-JS is a perf regression for no gain.
- ❌ **Storybook** — useful at scale, theatre at this scope. The components live in one app and are used in one place.
- ❌ **Framer Motion** — shadcn's built-in CSS transitions cover the trace-panel animations; importing Framer for a few state transitions is overkill.
- ❌ **A separate component library / design system package** — there's one app. Premature abstraction.
- ❌ **Server Actions for the chat endpoint** — Server Actions don't support SSE streaming cleanly; a route handler is the right primitive here.

**Why this combination is deliberate:**

1. The picks are 2026-idiomatic without being trendy. Tailwind v4 + shadcn + custom SSE is the current default modern AI-product stack.
2. The cuts (no Storybook, no Redux, no React Query, no Vercel AI SDK) reflect actual scope — they would all be earned additions at larger scale, but here they would be infrastructure without payload.
3. The Zustand-for-trace decision encodes separation of concerns: chat state and orchestration state are different state machines, and treating them as one creates coupling.

### 5.1 Why a real frontend (not Swagger or curl)

A learner-facing frontend is core to the goal, not optional:

1. **Role fit.** A learner-facing product is something a user opens, not an endpoint they POST to. The brief uses _learner-facing_ repeatedly — this is not demonstrable through Swagger.
2. **Demo legibility.** A chat interface lets stakeholders _feel_ the product. JSON in Swagger requires translation work from the audience.
3. **Architecture visibility.** The live trace panel (see §4.7 and §5.2) makes the orchestration _visible_ — it's the difference between _claiming_ parallel agent execution and _showing_ it.
4. **Visual craft as signal.** The author's primary professional craft is senior frontend engineering, including design-system work. A take-home frontend that ships raw shadcn defaults would underrepresent that craft. Meridian's UI is built with the same considered visual discipline applied to production frontend work: a coherent dark aesthetic, intentional type ramp, semantic color tokens, mobile-first responsive layout. The visual craft is part of the architecture's value, not decoration over it.

The remaining trap to avoid: visual craft is not the _primary_ evaluation axis — orchestration quality and evals are. Visual polish is allowed to be _good_, not allowed to _consume_ time better spent on orchestration depth.

### 5.2 The three FE elements that actually score points

Everything else (input box, message bubbles, send button) is table-stakes. These three are what turn the UI from "chat app" into **orchestration cockpit**:

1. **Live agent trace panel** — collapsible, per-message, **animates in real-time**. Each LangGraph node pushes a `status` event as it starts and finishes (see §4.7). The panel renders these live: Discovery and Career agents appearing side-by-side, ticking from "thinking..." to "✓ 2.1s" as they finish. Trace data persists server-side per message (`agents_invoked` + `step_durations`), so reloading a past conversation re-hydrates the panel from the DB. This is the most architecturally visible component in the product.
2. **Learner context card** — small panel at the top of the chat. Renders the CRM lookup: name, enrolment status, program, interests. Without it, the CRM integration is invisible plumbing. With it, the orchestrator visibly _uses_ external state.
3. **Streamed synthesis with stage-aware indicator** — the assistant response streams token-by-token via the custom SSE parser, with a typing indicator that surfaces the _current orchestration stage_ ("Synthesizing response...") rather than a generic spinner. The product feels alive; the architecture stays legible.

These three directly map to the "Productionization potential", "Thoughtfulness of solution", and "Communication" evaluation criteria. They are not decoration — they are how the architecture becomes visible to a non-technical stakeholder.

### 5.3 Component inventory

```
app/
  page.tsx                # Server component — fetches learner + conversations
  layout.tsx              # Root layout + fonts
  error.tsx               # Route-segment error boundary
  global-error.tsx        # Layout-level error boundary
  not-found.tsx           # Styled 404
  globals.css             # Tailwind v4 + design tokens
  api/
    chat/route.ts                       # SSE proxy → FastAPI
    conversations/route.ts              # list per learner
    conversations/[id]/route.ts         # get / patch / delete
components/
  chat/
    chat-shell.tsx        # holds SSE consumer + message state
    message-list.tsx
    message-bubble.tsx    # user vs assistant variants
    composer.tsx          # input + send
    agent-trace.tsx       # the cockpit panel — collapsible, live-animating
    trace-step.tsx        # single agent row (pending/running/done states)
    cost-badge.tsx        # latency + cost pill on each assistant message
  conversations/
    sidebar.tsx           # per-learner conversation history
    conversation-item.tsx # inline rename + delete
    mobile-toggle.tsx     # hamburger → drawer (<md)
  learner/
    learner-picker.tsx    # header dropdown, switches ?learner=…
    learner-context-card.tsx  # top-of-page CRM card
  ui/                     # shadcn primitives (button, card, badge, collapsible, etc.)
lib/
  api.ts                  # fetchLearner / fetchConversations / fetchConversation
  stream.ts               # SSE block parser + async iterator
  trace-store.ts          # Zustand: per-message trace + final telemetry
  sidebar-store.ts        # Zustand: mobile drawer open/close
  types.ts                # TS types mirroring server Pydantic shapes
```

### 5.4 Frontend scope cuts (deliberate)

**In scope** (because they earn their cost):

- ✅ **Dark mode as the default aesthetic** — for an AI product in 2026, dark is the visual default (ChatGPT, Claude, Perplexity, v0). Light-mode-only reads as dated.
- ✅ **Mobile-responsive layout** — built mobile-first, breakpoints up to desktop. The sidebar collapses to a drawer below `md`. Learner-facing implies mobile reality; phones are where most online-university learners check things.
- ✅ **Design-system discipline** — semantic color tokens (`--color-bg-elevated`, `--color-text-muted`, etc.) layered on Tailwind v4's CSS variables; intentional type ramp; consistent spacing scale. Shadcn primitives styled through this token system, not directly.
- ✅ **Trace-step transitions** — CSS-only state transitions (pending → running → done) on the live trace panel.
- ✅ **Per-learner conversation history with rename and delete** — the DB persists everything; surfacing it as a sidebar is cheap and useful. Mobile collapses to a drawer.
- ✅ **Error + 404 boundaries** — `app/error.tsx`, `app/global-error.tsx`, and a styled `app/not-found.tsx`. Costs little, signals attention to operational edges.

**Out of scope** (cut deliberately):

- ❌ Auth screen (single demo learner ID from URL param or env).
- ❌ Settings page, model picker UI, admin dashboard.
- ❌ Light-mode toggle — dark is the only theme in v1. A light variant is one CSS variable layer away if needed later.
- ❌ Custom design-system package or multi-app token export — there's one app; tokens live inline in `globals.css`.
- ❌ Animations beyond CSS transitions — Framer Motion would be overkill.

These cuts are defensible additions at production scale. At v1 scope, they would be infrastructure without payload.

### 5.5 Visual language

A short brief to keep styling deliberate up front:

| Layer               | Choice                                                                                                                                 |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Base palette**    | Deep slate background (`oklch(0.18 0.02 250)` or similar), elevated surfaces one step lighter, single accent for active/running states |
| **Accent**          | Cool blue-violet for orchestration events (running agents, streaming indicators) — distinct from a generic "primary action" CTA color  |
| **Type ramp**       | Inter for UI, JetBrains Mono for code/cost values/IDs. Three sizes (body, small, micro) — no h1/h2/h3 in a chat UI                     |
| **Spacing**         | Tailwind's default 4pt grid; chat messages use generous vertical rhythm (16-20px between turns)                                        |
| **Borders / depth** | 1px subtle borders on surfaces, no shadows (dark UI shadows look muddy); subtle hover lift on the trace panel only                     |
| **Radius**          | shadcn defaults (`--radius: 0.5rem`); the chat composer rounds more for a tactile feel                                                 |
| **Loading states**  | Skeleton (shadcn) for the learner card on initial load; pulsing dot for an active streaming agent                                      |
| **Iconography**     | lucide-react, 16px throughout, stroke-width consistent at 1.75                                                                         |

This is a one-pass styling brief, not a design system. The point is to make the visual decisions deliberate up front so they don't accumulate into inconsistency.

---

## 6. Data layer

### 6.1 SQLite in both environments; Postgres as a v2 migration path

Meridian uses SQLite locally **and** in deployment. The architectural choice is defended in §9.3; this section covers the implementation.

- **Local development:** SQLite file at `./server/data/meridian.db`. Zero setup; a fresh clone runs with no database installation required.
- **Deployed:** SQLite file at `/data/meridian.db` on a 1 GB Fly Volume mounted into the API container. Volume snapshots provide v1-grade backup.

SQLAlchemy 2.0 + Alembic are used regardless. The motivation isn't "we need an ORM today" — it's that the data-access layer is shaped for the Postgres migration whenever scale warrants it. The repository pattern (`ConversationRepo`, `MessageRepo`, `EvalRepo`) means swapping the connection string is a one-line change at the engine boundary; query code is engine-agnostic.

**The v2 migration to Postgres** is documented as a step-by-step procedure in §10:

1. Provision Postgres (Supabase, Neon, or self-hosted)
2. Run existing Alembic migrations against the new database
3. Migrate data with `sqlite3` dump → `pg_restore` (one-time, no application code change)
4. Change `DB_URL` in Fly secrets
5. Redeploy

Nothing in the application code changes. That's the productionization-potential signal — not "we already use Postgres in v1."

### 6.2 Schema

```
conversations
  id          UUID PK
  learner_id  TEXT
  title       TEXT          -- generated from first user message
  created_at  TIMESTAMP
  updated_at  TIMESTAMP

messages
  id              UUID PK
  conversation_id UUID FK
  role            TEXT  -- 'user' | 'assistant'
  content         TEXT
  agents_invoked  JSON  -- ['discovery', 'career']
  step_durations  JSON  -- {load_context: 180, plan: 340, discovery: 2100, …}
  latency_ms      INT
  tokens_in       INT
  tokens_out      INT
  cost_usd        NUMERIC
  created_at      TIMESTAMP

eval_runs
  id           UUID PK
  dataset      TEXT
  test_case_id TEXT
  passed       BOOL
  score        NUMERIC
  notes        TEXT
  extra        JSON       -- judge reasoning, routing decision, latency
  created_at   TIMESTAMP
```

Three reasons to log per-message metadata from day one:

1. The evals layer reads it for offline analysis and regression detection.
2. The same fields support production monitoring without schema migration — `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms` per message are exactly what an observability dashboard would chart.
3. The trace panel re-hydrates from `agents_invoked` + `step_durations` on conversation reload — the architecture is visible even on historical conversations, not just live runs.

---

## 7. Evals approach

The brief asks: _"How would you know the system is getting better or worse?"_ Meridian answers it with a small but real eval harness rather than skipping the question.

### 7.1 What v1 builds

- A `golden_dataset.jsonl` with **15 hand-written test cases**:
  - 5 discovery-only queries
  - 5 career-only queries
  - 3 compound queries (both agents)
  - 2 edge cases: off-topic query + ambiguous query (testing routing robustness)
- A `run_evals.py` script that:
  1. Loops every test case
  2. Calls the orchestrator (against the stub CRM for determinism)
  3. Checks: **(a) routing correctness** (did the right agents fire?) and **(b) response quality** (LLM-as-judge with a rubric, scored 1–5, temp=0 for reproducibility)
  4. Writes results to `eval_runs` table + a markdown summary
- CLI exit code: non-zero when routing accuracy falls below a `--min-routing-accuracy` threshold — usable as a CI gate.

**Current v1 numbers (15-case golden dataset):** routing accuracy **87%**, mean response quality **4.60 / 5**. Two persistent misses, both documented in `evals/results/` with one-line v2 fixes: one labelling ambiguity on program-comparison queries, one conservative routing on bare job-title prompts.

### 7.2 What production would add

- **Human review queue** — sample 5% of real traffic for manual scoring; routing classifier improves from this data.
- **Regression gate** — evals run in CI; merging blocked if routing accuracy drops >3pp.
- **Online metrics** — thumbs-up/down on responses, captured in DB, fed back into eval set.
- **Per-agent evals** — isolate each agent's quality independently of the orchestrator.
- **Drift detection** — if a model provider silently updates `gpt-4o`, do quality scores change? Weekly canary run.

### 7.3 Success metrics

3 metrics, with 30/90/steady targets:

| Metric                                                           | 30 days | 90 days | Steady state |
| ---------------------------------------------------------------- | ------- | ------- | ------------ |
| **Routing accuracy** (% queries hitting correct agent set)       | ≥ 85%   | ≥ 92%   | ≥ 95%        |
| **Response coherence** (LLM-judge + 5% human-sampled, 1–5 scale) | ≥ 3.8   | ≥ 4.2   | ≥ 4.5        |
| **P95 latency** (end-to-end orchestrator call)                   | < 8s    | < 5s    | < 3s         |

Why these three: routing accuracy = does the system work as designed; coherence = does the learner actually get value; latency = is it usable. Cost is tracked but not a _target_ metric — it's a constraint to stay under.

---

## 8. Top three risks

The brief's risk categories are: cost, latency, hallucination, privacy, integration brittleness. The three below are the ones most likely to materially affect production deployment.

### Risk 1: Hallucination on program/career facts

**Why it matters:** A learner is making a real life decision. If the Career agent confidently says "BBA grads earn $80k average in Lagos" and that number is invented, that's a credibility-destroying moment AND potentially a regulatory issue for a university.

**Mitigation:**

- Ground responses in retrieved data (RAG over the institution's actual program catalog + verified career data sources, not the LLM's training data).
- Output structured citations: every factual claim must have a source ID from retrieval.
- LLM-as-judge eval specifically tests for ungrounded claims.
- Explicit prompt: "If you don't have data, say so. Don't estimate."

### Risk 2: Routing brittleness on ambiguous queries

**Why it matters:** _"What's my next step?"_ — is that discovery, career, or admin? If routing fails silently (picks the wrong agent, returns a confident wrong answer), the learner has no signal that anything went wrong.

**Mitigation:**

- Plan step outputs `confidence` alongside the route. Low confidence → fallback to a clarifying question instead of guessing.
- Eval set explicitly includes ambiguous queries with multiple acceptable routings.
- Trace every routing decision; weekly review of low-confidence routes feeds prompt refinements.

### Risk 3: Integration brittleness with HubSpot (and future systems)

**Why it matters:** this is the _real_ risk the orchestration pattern is trying to solve — agents on different stacks not talking to each other. If the orchestrator becomes the new tight coupling, the problem has been moved, not solved.

**Mitigation:**

- Every external system behind a `Client` interface (`CRMClient` exists, future `LMSClient`, `BillingClient` follow the same pattern). The HubSpot integration is real _and_ swappable — same interface, different implementation behind `CRM_PROVIDER`.
- Treat each agent as a service with a defined contract (input schema, output schema). Agents are not allowed to know about each other — they only know about the orchestrator.
- Timeouts (5s), exponential backoff retries via `tenacity` (max 2), circuit breaker (3 consecutive failures → degraded mode). On `/chat`, the orchestrator proceeds with empty context and notes "couldn't load profile" — chat never 500s. The direct `/learner/{id}` endpoint returns 503 in degraded mode (no orchestrator to fall back to).
- The fact that this prototype runs against real HubSpot with real network conditions is itself the mitigation: the patterns are tested against reality, not assumptions.

**Cost and privacy** are real concerns but secondary at this scale. LLM costs at 10k learners × 5 queries/month run ~$300/month — small enough to be a constraint, not a target. Privacy is more policy than architecture for v1 (no PII redaction yet — flagged for v2 in §10).

---

## 9. Deployment

The product ships at a live URL ([https://meridian-one-mu.vercel.app](https://meridian-one-mu.vercel.app)). Local development remains the canonical path for engineering work (predictable, low-latency, debugger-attached), but the deployed environment is the operational reference.

### 9.1 Stack

| Tier     | Service                          | Why                                                                                                                                              |
| -------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Frontend | **Vercel**                       | Native Next.js host, free tier, automatic deploys on push, SSE-friendly route handlers                                                           |
| API      | **Fly.io** (Frankfurt)           | Dockerfile-native, free tier covers this scale, Frankfurt region for EU learners, persistent secrets; container binds port 8080                  |
| Database | **SQLite on Fly Volume**         | Same engine local and deployed → true parity. 1 GB volume mounted at `/data`. Single-instance deployment is appropriate for v1 scale (see §9.3). |
| CRM      | **HubSpot** (developer portal)   | Free for dev portals, full API surface; 5 seeded test contacts across all lifecycle stages                                                       |
| Secrets  | Fly.io secrets + Vercel env vars | Standard pattern; no secret manager service at this scale                                                                                        |

### 9.2 Deployment topology

```
                   Vercel
            ┌─────────────────┐
            │  Next.js (web)  │  ◄── learner browser
            └────────┬────────┘
                     │ HTTPS (server-side, no CORS)
                     ▼
                   Fly.io  ─── HubSpot API ──► HubSpot
            ┌─────────────────┐
            │ FastAPI (api)   │  port 8080
            └────────┬────────┘
                     │
                     ▼ (mounted volume at /data)
            ┌─────────────────┐
            │ SQLite (file)   │
            └─────────────────┘
```

The Next.js `/api/chat` route handler proxies to the Fly.io URL server-side — no CORS, no API URL leaked to the client, no auth complexity in v1. The SQLite file persists across deploys via the Fly Volume.

### 9.3 On choosing SQLite (and accepting its constraints)

SQLite is a deliberate v1 choice, not a placeholder. The constraints it imposes and why each is acceptable at this scale:

- **Single-instance only.** SQLite does not tolerate concurrent writers across instances. The API runs as a single Fly machine. At the design target (50k writes/month from conversation logging), one instance handles the load with substantial headroom.
- **No horizontal autoscaling.** Acceptable because the orchestrator is I/O-bound on LLM calls, not CPU-bound. Vertical scaling on Fly is one command if a single machine ever saturates.
- **Backups are file-level, not transactional.** Acceptable for v1 scope; documented in §10 as a v2 concern.

**Why this isn't "SQLite in production is wrong":** For workloads that fit a single writer, SQLite in production is a well-established pattern — see [Litestream](https://litestream.io) for replication and the broader "small data" movement. The Postgres migration is documented in §10 as a v2 step because at full institution scale (multi-region, partner schools, row-level security per tenant), Postgres earns its keep — not because SQLite is broken at v1 scale.

**Why this isn't a corner-cutting choice:** the architectural pattern that earns "productionization potential" — `DB_URL` env var, SQLAlchemy + Alembic models that work against either engine, the `CRMClient`-style abstraction at the data layer — is preserved. The v2 migration is a connection string change, not a re-architecture.

### 9.4 Deployment scope cuts

- No custom domain (`*.fly.dev` and `*.vercel.app` are fine for v1)
- No CDN beyond Vercel/Fly defaults
- No staging environment (one production environment for v1 scope)
- No CI/CD beyond Vercel's automatic deploys (no GitHub Actions yet)
- No monitoring/alerting (Fly's built-in health checks suffice; Sentry is a v2 add)
- No backup strategy beyond Fly's volume snapshots (Litestream is the v2 answer)
- No load testing (10k learners is the _design target_, not the v1 audience)

### 9.5 Operational safety

1. **Local + deployed parity.** Same Docker image runs locally and on Fly.io. Same SQLite engine in both places. No engine-specific bugs that only surface in production. (Note: local dev uses port 8000, the Fly container uses 8080 — different bind, same code.)
2. **Stub fallback.** `CRM_PROVIDER=stub` is one env var away if HubSpot has an incident, in either environment.
3. **Pre-demo smoke test.** A short checklist run before any external demo verifies both local and deployed paths.
4. **Backup recording.** A short pre-recorded run of the canonical flow exists as a last-resort fallback.

---

## 10. Productionization at platform scale

Meridian's orchestration runs against real HubSpot end-to-end on a deployed FastAPI with persistent storage. The orchestration architecture is production-shaped. The gaps for institution-grade operations are scale, security, durability, and operational maturity, not foundational re-architecture:

> **From v1 to platform scale (10k learners, growing):** The orchestration layer and CRM integration are production-shaped already. The migration steps are: (1) **Migrate SQLite → Postgres** (Supabase, Neon, or self-hosted) — run existing Alembic migrations against the new DB, dump-and-restore data, change `DB_URL`; application code unchanged. This unlocks horizontal autoscaling, transactional backups, and row-level security for multi-tenancy. (2) **Add Redis** for conversation context caching, intent-classifier result caching for repeat queries, and HubSpot response caching to stay well under rate limits. (3) **Promote LangSmith to a hard production dependency** — the env-var hook exists in v1 (set `LANGSMITH_API_KEY` to enable); v2 adds dashboards, alerting on routing-accuracy drift, and team-shared traces. Add **Sentry** for error tracking and alerting. (4) **CI eval gate** (GitHub Actions) so routing-accuracy regressions block merges. (5) **PII redaction** at the client boundary before any data hits LLM providers. (6) **Authentication** via Auth0 or Supabase Auth with row-level security on `conversations` and `messages`. (7) **Per-tenant rate limiting** for institutions serving partner schools. (8) **Replace Fly free tier** with a paid org, autoscaling rules tied to request volume, stage environment plus canary deploys. (9) **Durability upgrade**: Litestream (if staying on SQLite for any service) or managed-Postgres backups, point-in-time recovery, multi-region replicas. Total path-to-production effort: estimated 2–3 weeks for one engineer, mostly security hardening and observability — the orchestration architecture itself is production-shaped already.

---

## 11. Repo structure

Two services in one repo (monorepo-light).

```
meridian/
├── README.md                  # operator-facing: run, architecture, productionization, AI disclosure
├── docs/
│   └── rfc.md                 # this document
│
├── server/                    # FastAPI + LangGraph + evals
│   ├── pyproject.toml         # uv-managed
│   ├── Dockerfile             # binds port 8080 (Fly target)
│   ├── fly.toml               # Fly.io deployment config
│   ├── alembic/               # migrations
│   ├── app/
│   │   ├── main.py            # FastAPI entry: /chat, /health, /learner/{id}, /learners, /conversations
│   │   ├── config.py          # pydantic-settings
│   │   ├── api/
│   │   │   └── sse.py         # LangGraph events → SSE wire protocol
│   │   ├── orchestrator/
│   │   │   ├── graph.py       # LangGraph state machine + routing
│   │   │   ├── state.py       # OrchestratorState TypedDict + reducers
│   │   │   ├── nodes/
│   │   │   │   ├── load_context.py
│   │   │   │   ├── plan.py
│   │   │   │   ├── synthesize.py
│   │   │   │   ├── persist.py
│   │   │   │   └── title.py   # async post-response title generation (not on graph)
│   │   │   └── agents/
│   │   │       ├── discovery.py
│   │   │       └── career.py
│   │   ├── clients/
│   │   │   ├── llm.py         # ChatOpenAI factory + cost estimation
│   │   │   └── crm/
│   │   │       ├── base.py    # CRMClient interface + provider factory
│   │   │       ├── stub.py    # StubCRMClient with seeded learner records
│   │   │       └── hubspot.py # HubSpotCRMClient + circuit breaker
│   │   ├── schemas/           # Pydantic: LearnerProfile, ChatRequest, SSE events
│   │   ├── data/
│   │   │   ├── programs.json  # program catalog (sample data)
│   │   │   ├── careers.json   # career outcome stub data
│   │   │   └── learners.json  # CRM stub data
│   │   ├── db/
│   │   │   ├── models.py      # SQLAlchemy
│   │   │   ├── repository.py  # ConversationRepo, MessageRepo, EvalRepo
│   │   │   └── session.py
│   │   └── observability/
│   │       └── tracing.py     # structlog + optional LangSmith via env var
│   ├── evals/
│   │   ├── golden_dataset.jsonl
│   │   ├── run_evals.py
│   │   └── results/           # gitkeep, populated at runtime
│   └── tests/
│       ├── test_stub_crm.py
│       ├── test_hubspot_circuit_breaker.py
│       ├── test_routing.py
│       ├── test_schemas.py
│       ├── test_conversation_repo.py
│       ├── test_conversations_api.py
│       └── test_title_generation.py
│
└── client/                    # Next.js 16 chat UI
    ├── package.json
    ├── tsconfig.json
    ├── components.json        # shadcn config
    ├── playwright.config.ts
    ├── .env.example
    ├── app/                   # See §5.3 component inventory
    ├── components/            # chat/, conversations/, learner/, ui/
    ├── lib/                   # api.ts, stream.ts, trace-store.ts, sidebar-store.ts, types.ts
    └── tests/e2e/             # Playwright happy-path suite
```

Why this structure: a senior engineer can navigate it in 30 seconds. The `server/` vs `client/` split is the same boundary that would be cut at production scale (two deployable services). The boundary between `orchestrator/` and `clients/` inside `server/app/` is the same boundary that lets the prototype scale.

---

## 12. Implementation plan (phases & exit criteria)

No hour budgets. With Claude Code agents driving scaffolding and SKILL.md-shaped work, time estimates are theater. What matters is **phase ordering** and **exit criteria** — what "done" looks like at each checkpoint, so the agent doesn't drift and I don't either.

**The two non-negotiable rules:**

1. **Each phase must hit its exit criterion before the next phase starts.** Debugging two layers at once is how time disappears.
2. **The cut order (§12.6) is rehearsed, not improvised.** If anything slips, drop from the bottom, not from whatever feels hardest.

### 12.1 Phase 1 — HubSpot foundation

Setting up real HubSpot is the only piece that _can't_ be parallelized with anything else. Do it first so any account/setup friction surfaces immediately, not on day three.

**Tasks:** Create HubSpot dev portal → create 4 custom Contact properties (`meridian_enrolment_status`, `meridian_program`, `meridian_interests`, `meridian_career_goals`) → seed 5 test contacts across all lifecycle stages → generate private app token with `crm.objects.contacts.read` scope.

**Exit criterion:** Hit the HubSpot API from a Python REPL, pull a contact, see the custom properties populated. Token in `.env`. No code yet — just verified API access.

### 12.2 Phase 2 — Backend core

**Tasks:** Repo scaffold (`server/` + `client/`). Python deps via `uv`. `CRMClient` interface, both `StubCRMClient` and `HubSpotCRMClient` implementations. Resilience patterns on the HubSpot client (timeout, retry, circuit breaker). SQLAlchemy models + Alembic migration. LangGraph state machine wired with `print` statements first, _then_ real LLM calls. Structured Pydantic outputs from the planner. `/chat` (streaming SSE per §4.7), `/health`, `/learner/{id}` endpoints. Persistence + cost/latency observability. SSE event emitter wired via `astream_events(version="v2")`.

**Exit criterion:** `curl POST /chat` with the compound learner question, against real HubSpot, returns an SSE stream containing `status` events for each node, `delta` events streaming synthesis tokens, and a `final` event with metadata. Both `CRM_PROVIDER=stub` and `CRM_PROVIDER=hubspot` paths verified working. Test with `curl -N` and visually inspect the event sequence. If this isn't done, **no frontend work begins** — the FE on a broken backend just hides the problem.

### 12.3 Phase 3 — Evals

**Tasks:** 15 hand-written cases in `golden_dataset.jsonl` (5 discovery-only, 5 career-only, 3 compound, 2 edge — off-topic and ambiguous). `run_evals.py` script. LLM-as-judge prompt for response quality (1–5 rubric, judge at temp=0 for reproducibility). Routing accuracy calculation. Results written to DB + markdown summary file.

**Exit criterion:** `python -m evals.run_evals` runs against the stub CRM, completes in under 3 minutes, prints routing accuracy % and mean quality score, writes a results table to `server/evals/results/`. CLI exit code is non-zero when `--min-routing-accuracy` threshold isn't met.

Why before the FE: evals against the stub need a working backend, not a working UI. Running this checkpoint also forces a test of the orchestrator in a way it can't be talked around.

### 12.4 Phase 4 — Frontend

**Tasks:** `create-next-app` in `client/`, Tailwind v4, shadcn init (`button`, `card`, `badge`, `collapsible`, `scroll-area`, `input`, `skeleton`). `lib/stream.ts` SSE parser. `lib/trace-store.ts` Zustand store. Chat shell consuming the `delta` event stream with a side-channel handler routing `status`/`final` events to the trace store. `/api/chat` route handler proxying SSE through to FastAPI. Conversation history sidebar (per-learner, with rename + delete + mobile drawer). Message list, bubble, composer. **The three score-earning elements:** `agent-trace.tsx` with `trace-step.tsx` rows (live-animating pending → running → done), `learner-context-card.tsx` (top-of-page CRM card with skeleton loader), and stage-aware typing indicator on the assistant bubble. Cost badge on completed messages. Error + 404 boundaries. Empty/loading/error states.

**Exit criterion:** localhost full stack works end-to-end. Open the page → learner card loads from HubSpot → type the compound question → trace steps animate in live (Discovery + Career appear side-by-side, ticking through pending → running → done) → tokens stream into the assistant bubble → trace finalizes with latency and cost when `final` event arrives → conversation appears in sidebar → reload → trace re-hydrates from persisted DB data.

### 12.5 Phase 5 — Deploy + docs + memo

Three sub-phases in this order:

**5a. Deploy.** Fly.io: `fly launch` for `server/`, create 1 GB Fly Volume at `/data`, mount it to the API container, configure secrets (OpenAI key, HubSpot token, `DB_URL=sqlite:////data/meridian.db`), deploy in Frankfurt region. Run Alembic migrations against the deployed SQLite. Vercel: deploy `client/`, set `API_URL` to Fly.io URL.

> **Exit criterion 5a:** the deployed Vercel URL serves a real conversation that hits the deployed Fly.io API, which calls real HubSpot and persists to the mounted SQLite volume. Smoke-test the full flow with three different learner profiles. Verify volume persistence by redeploying — conversations from before the redeploy must still be queryable.

**5b. README.** Live URLs at the top. Run instructions for both local and deployed. Architecture section with a Mermaid diagram. Stubbed-vs-real boundary (almost everything is real — only auth is not). The productionization paragraph (§10). The AI-assisted development note (§13). The "what was cut" list.

> **Exit criterion 5b:** a senior engineer who has never seen the repo can clone, run locally, hit the deployed URL, and understand the architecture inside 10 minutes.

**5c. Memo.** Written last, with the actually-built product as evidence rather than aspirations. Strict 2 pages.

> **Exit criterion 5c:** memo PDF exists, fits 2 pages, hits all five required sections (architecture; build vs. buy vs. partner; success metrics; top 3 risks; what was cut), and the "what was cut" section reads as deliberate deprioritization rather than tasks that didn't get done.

### 12.6 Cut order (rehearsed)

If time runs tight, cuts happen in this exact order — not panicked freelance decisions:

1. **README screenshots** — text-only ships fine.
2. **FE micro-polish** — hover states, focus rings, micro-transitions, empty-state copy. The visual baseline (dark theme, mobile-responsive layout, semantic tokens) stays; only the last 10% niceties get cut.
3. **Mobile responsiveness past 640px breakpoint** — keep mobile + desktop, drop tablet-specific tuning.
4. **Cost badge component** — trace panel and learner card stay; those carry the architecture signal.
5. **Conversation history sidebar** — falls back to single-conversation-per-session UX. DB schema and endpoints stay.
6. **Live-animating trace steps** — degrade trace panel to "fills in after stream completes" instead of live-updating. The `final` event still drives it. Saves the Zustand wiring complexity. Demo loses some sizzle but architecture is intact.
7. **Streaming entirely** — backend returns a single JSON response, FE shows a typing indicator. Slowest cut to make because backend code already exists; only revert if Phase 4 is collapsing.
8. **Eval cases: 15 → 10** — still covers all three routing categories.
9. **Deploy entirely** — submit localhost-only with README documenting deployment-ready architecture; live URL added after submission as v1.1.
10. **Agent trace panel** — demo through Swagger or basic chat shell only.

If cut 9 lands — deployment dropped — the framing changes from "a live product" to "a prototype with a documented deployment plan." Still defensible, less powerful.

### 12.7 Time discipline guardrails

No hour budgets, but not unbounded either:

- **End of each day:** if the day's phase isn't done, stop and replan rather than push through tired. Tired decisions are the ones that show up later as bugs or weak demo moments.
- **Day 2 morning checkpoint:** if Phase 2 (backend core) isn't done, Day 2 becomes "finish Phase 2." No FE that day.
- **24 hours before demo:** submission goes out, regardless. If something's missing, the README documents it as a deliberate cut and explains the trade.

---

## 13. AI-assisted development note

The canonical version of this note lives in the repo's [`README.md`](../README.md) under the "AI assistance disclosure" heading. The short version, repeated here so the design doc and the operator doc tell the same story:

> The architecture and design decisions in this RFC — scenario choice, orchestrator shape, model split, CRM resilience pattern, scope cuts, productionization plan, success metrics — are mine. The implementation was paired with Claude Code (Opus 4.7) as a fast-fingers collaborator: I drove the design and judgment calls; Claude drafted code from my specs, ran the toolchain, and surfaced issues I then resolved.

Hand-authored: this RFC, all architecture decisions, the eval rubric, the SSE event protocol, the CRM circuit-breaker contract, the model-per-role split, scope cuts. AI-drafted then reviewed: LangGraph wiring, FastAPI route handlers, SQLAlchemy models + repos, Alembic migrations, Pydantic schemas, the conversation history sidebar (React + Zustand), the chat shell SSE consumer, the agent-trace panel, the eval harness, pytest + Playwright happy-path tests.

Most production engineering today is a collaboration like this. The point of disclosing it is so the reviewer can see exactly where my judgment ended and the assistant's drafting began.

---

## 14. Open questions / future RFCs

Decisions deliberately deferred:

- **Conversation memory beyond a single session**: messages persist per-conversation today, but cross-conversation memory (a learner-profile-builder agent that summarizes long-term context) is v2.
- **Self-correction loops**: orchestrator could re-route if synthesis quality is low. Interesting but adds latency and complexity; v2 if metrics show it's needed.
- **More agents**: the brief implies a Career Advisor and a Discovery agent. In production there are obviously more (Financial Aid, Technical Support, Alumni Network). The architecture supports adding them by writing a new node and one routing rule — a single-PR change, not an architecture change.
- **A/B testing of synthesis prompts**: traffic-splitting at the synthesis node with metric capture per variant. v2 once there's enough traffic to learn from.

---

## 15. Project walkthrough (15-minute version)

A pre-built run-of-show for presenting Meridian to stakeholders — useful for technical interviews, internal demos, or showing the project to anyone evaluating the architecture. Two framings to lead with:

> _"The brief asked for a prototype. Meridian is a product."_

> _"Everything visible is real — real HubSpot CRM, real persistent storage, real deployed URLs. The only stub is the program catalog, since a real institution's catalog isn't public sample data."_

**The walkthrough runs from localhost** for predictable performance and debugger access. **The deployed URL sits at the top of the README** as proof of production-readiness, not as the walkthrough runtime.

### Run of show

1. **Minute 0–2 — The problem.** The disconnected-agents problem in its own words. The compound query. Why a router alone fails. The chat page opens with the learner context card already populated from HubSpot — instant visible signal that the CRM is integrated.
2. **Minute 2–5 — The architecture.** Show the diagram (Mermaid in the README, or §4.2 in this RFC). Why LangGraph (state machines for orchestration with deterministic routing). Why an orchestrator with routing layer, not a pure router and not a swarm. What's stubbed (only the program catalog) and what's real (everything else).
3. **Minute 5–10 — Live demo through the UI:**
   - **Single-intent query** ("which program is right for me?") → trace panel animates live (Plan → Discovery only) → tokens stream into the response → trace finalizes with latency.
   - **Compound query** (the brief's canonical example) → trace panel shows **Discovery and Career rendering side-by-side, both ticking through pending → running → done in parallel** → synthesis tokens stream → final metadata. This is the architectural payoff. Pause on it.
   - Point at the cost badge — production thinking made visible.
   - Switch to a terminal: `cd server && uv run python -m evals.run_evals` → show routing accuracy + quality table.
4. **Minute 10–13 — Productionization story.** Open `server/app/clients/crm/base.py` → show the `CRMClient` interface. Show `hubspot.py` next to it → emphasize that `CRM_PROVIDER` swaps them at runtime. Open `server/Dockerfile` and `server/fly.toml` → walk through the deploy path: Fly machine, mounted Volume at `/data`, secrets configured, single-command redeploy. Walk through §10's productionization paragraph: what's already real, what's missing for institution-grade production.
5. **Minute 13–15 — Risks, cuts, extensions.** Top 3 risks from §8. What was deliberately deprioritized (auth, Redis, light-mode toggle, custom domain) and why. What two more weeks would add.

### Anticipated extensions

The cheapest live extension is adding a third agent (e.g., Financial Aid). ~10 minutes of work — new node file + one routing rule in the planner prompt + new entry in the `agents_invoked` enum. The FE trace panel renders the new agent automatically because it's data-driven from the SSE event stream.

### Failure plan

- **If localhost fails:** switch to the deployed URL. Both stacks share the same UI and event protocol.
- **If both fail:** narrate the architecture from the diagram, walk through the code, follow up with a working flow over email. Don't burn time debugging in front of an audience.

---

## Sign-off

This RFC is the design contract for Meridian. By the time implementation starts, every architectural decision is already made and defensible. The code is the consequence; the design is the work.
