# Meridian — Design Memo

**Author:** Alexandra Moldovan · **Submitted:** 15 May 2026
**Live app:** https://meridian-one-mu.vercel.app · **Live API docs:** https://meridian-g-q4wg.fly.dev/docs
**Repo:** https://github.com/Alexandra2888/Meridian · **Full design rationale:** `docs/rfc.md`

---

## 1. Architecture

Scenario A. Meridian is an orchestration layer that routes a single learner query across specialist agents and synthesizes one coherent response.

**Shape:** an orchestrator with a routing layer — not a pure router (which picks one agent and so can't serve compound queries like the brief's example), not an autonomous swarm (over-engineered, hard to eval, hard to debug). Built as a **LangGraph state machine**: six registered nodes — `load_context` loads the learner profile from HubSpot, `plan` classifies intent into `{discovery, career, both, neither}`, `discovery_agent` and `career_agent` run **in parallel** when both are needed (LangGraph's `Send` API), `synthesize` unifies their outputs into one voice, `persist` writes the conversation to SQLite. A separate async title task names the conversation after the response is delivered, off the streaming wire.

**The compound query as canonical test** — _"What program is right for me, and what jobs does it lead to once I graduate?"_ — forces every architectural decision: parallel routing, synthesis to one voice, CRM context for personalization. Any architecture that handles it handles the rest.

**Why LangGraph specifically:** state machines are the right mental model for orchestration with deterministic routing. Native parallelism via `Send`, built-in checkpointing for conversation state, and `astream_events(version="v2")` exposes node lifecycle events natively — which is what makes the live orchestration trace in the UI possible. The trace panel is the architecture made visible, not decoration.

## 2. Build vs. buy vs. partner

| Decision           | Choice                        | Why                                                                                                                                               |
| ------------------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Orchestration      | **Build** on LangGraph        | Routing logic is core IP and must be inspectable + evalable. LangGraph provides primitives without forcing a ReAct loop or swarm pattern.         |
| LLM provider       | **Buy** (OpenAI)              | No reason to self-host at this scale; provider abstraction in `clients/llm.py` keeps the door open. Cross-provider (Anthropic, Bedrock) is v2.    |
| CRM                | **Partner** (HubSpot)         | Universities already run on a CRM; the orchestrator integrates rather than replacing. Real HubSpot in production, stub fallback for evals.        |
| Observability      | **Build** v1 + **Buy** v2     | In-app trace panel + structured logs ship now (every node visible, every cost persisted). LangSmith hook wired but off-by-default; promote in v2. |
| Evals              | **Build**                     | 15-case golden dataset + LLM-as-judge runs in <3 min, no external dependency, regression-gateable in CI (judge at temp=0).                        |
| Frontend streaming | **Build** (custom SSE parser) | Vercel AI SDK's `useChat` considered; the five-event SSE protocol exceeds its message model, so a custom parser was clearer than fighting it.     |

## 3. Success metrics

Three metrics with 30 / 90 / steady-state targets:

| Metric                                                           | 30 days | 90 days | Steady state |
| ---------------------------------------------------------------- | ------- | ------- | ------------ |
| **Routing accuracy** (% queries hitting correct agent set)       | ≥ 85%   | ≥ 92%   | ≥ 95%        |
| **Response coherence** (LLM-judge + 5% human-sampled, 1–5 scale) | ≥ 3.8   | ≥ 4.2   | ≥ 4.5        |
| **P95 latency** (end-to-end orchestrator call)                   | < 8s    | < 5s    | < 3s         |

**Today (v1, 15-case golden dataset):** routing accuracy **87%**, mean response quality **4.60 / 5**, run reproducible because the judge is deterministic. Two persistent misses categorized in `evals/results/` — one labelling ambiguity (program-comparison queries can route to either `discovery` or `both`; widen the label) and one conservative routing (planner asks for clarification on bare job titles; bias toward `career` when a job title is named). Both have one-line v2 fixes.

Cost is tracked per message (`tokens_in`, `tokens_out`, `cost_usd`) but is not a target metric — it's a constraint. At ~$0.006/request × 10k learners × 5 queries/month, the LLM bill is ~$300/month, small enough to stay out of the metric set.

## 4. Top three risks

**Hallucination on program / career facts.** A learner is making a real life decision; an invented salary number is credibility-destroying for a regulated educational institution. _Mitigation:_ ground responses in retrieved data (RAG over the actual program catalog + verified career sources, not the LLM's training data), require structured citations on every factual claim, prompt explicitly to refuse rather than estimate when data is missing, and test for ungrounded claims in the LLM-judge eval rubric.

**Routing brittleness on ambiguous queries.** Silent misroutes are worse than visible failures — a learner asking _"what's my next step?"_ could be served by Discovery, Career, or Admissions, and a confident wrong answer gives no signal that anything went wrong. _Mitigation:_ the planner emits `confidence` alongside the route; low confidence triggers a clarifying question instead of guessing. Ambiguous cases are explicitly in the eval set (2 of the 15 cases), and every routing decision is traced — weekly review of low-confidence routes feeds prompt refinements.

**Integration brittleness with HubSpot (and future systems).** The orchestrator must not become the new tight coupling the architecture is trying to solve. _Mitigation:_ every external system behind a `Client` interface (HubSpot is real and swappable today via `CRM_PROVIDER`); `asyncio.wait_for` timeouts (5s), `tenacity` retries with backoff (max 2), custom circuit breaker (3 failures → degraded mode). On `/chat`, the orchestrator proceeds with empty context and notes "couldn't load profile" — chat never 500s. The direct `/learner/{id}` endpoint returns 503 in degraded mode because there's no orchestrator to fall back to. That distinction is deliberate: graceful degradation should preserve the _primary path_, not paper over endpoint-level failures.

Cost and privacy are real but secondary at this scale. Privacy redaction is policy, not architecture, in v1; PII redaction at the LLM-provider boundary is flagged in §10 of the RFC as a v2 add before any institution-grade rollout.

## 5. What's NOT in v1, and why

| Cut                                       | Why                                                                                                                                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Auth**                                  | Biggest deliberate cut — removes ~80% of deployment complexity (login, sessions, JWT, OAuth, RBAC). Single-learner-from-URL is the prototype-scope answer; v2 conversation.                                               |
| **PII redaction pipeline**                | Required before any institution-grade rollout. Flagged in RFC §10 as the first security add. Not in v1 because v1 has no real learner data — only seeded test contacts.                                                   |
| **Redis caching layer**                   | Not justified at 10k learners. LLM costs are ~$300/month; HubSpot rate limits aren't pressing. Earned addition once load justifies it.                                                                                    |
| **Cross-provider LLM abstraction**        | Factory in `clients/llm.py` is wired, but only returns `ChatOpenAI` today. Per-role model config (`MODEL_PLANNER`, `MODEL_AGENT`, `MODEL_SYNTHESIZER`) is live; provider swap is a small factory extension flagged as v2. |
| **Light-mode toggle, design-system pkg**  | Dark-only in v1. A second app to share tokens with is the trigger for a real design system; one app doesn't need one.                                                                                                     |
| **A/B testing infrastructure**            | "Next two weeks" work. Traffic-splitting at the synthesis node + metric capture per variant is straightforward to add once there's real traffic to learn from.                                                            |
| **Multi-tenancy, per-tenant rate limits** | All called out in RFC §10 as the v1→v2 migration path. Estimated 2–3 weeks for one engineer to close the full gap — mostly security and observability hardening.                                                          |

The discipline of cutting these _deliberately_, with each one tied to a v2 trigger, is itself part of the work. The architecture is shaped so each cut is an _addition_ later, not a _re-architecture_.

---

_Implementation paired with Claude Code (Opus 4.7) as a fast-fingers collaborator. Architecture, scope cuts, eval rubric, model split, SSE event protocol, and resilience contracts were authored by me; the assistant drafted code from my specs. Full disclosure in the repo `README.md`._
