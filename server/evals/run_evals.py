"""Routing + response-quality evals for the Meridian orchestrator. RFC §7.

What it does:
  1. Loads `golden_dataset.jsonl` (hand-written test cases).
  2. Runs each case through the real LangGraph orchestrator (stub CRM so the
     run is deterministic + free of HubSpot rate limits).
  3. Scores **routing correctness** — did the expected agent set fire?
  4. Scores **response quality** via an LLM-as-judge rubric (1-5).
  5. Persists results to the `eval_runs` table and prints a markdown summary.

Run:
    uv run python -m evals.run_evals
    uv run python -m evals.run_evals --dataset golden_v1   # tag this run

Exit code is non-zero when routing accuracy < `--min-routing-accuracy`
(default 0.85) — so this script doubles as a CI eval gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

# Force the stub CRM before any app modules import config; evals must stay
# deterministic even when the developer shell has CRM_PROVIDER=hubspot.
os.environ["CRM_PROVIDER"] = "stub"

from app.clients.llm import get_llm
from app.db import EvalRepo, init_db, session_scope
from app.observability import configure_logging, get_logger
from app.orchestrator import get_graph

configure_logging()
log = get_logger(__name__)

DATASET_PATH = Path(__file__).parent / "golden_dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


# ──────────────────────────────────────────────────────────────────────────────
# LLM-as-judge


class JudgeVerdict(BaseModel):
    """Structured output from the judge LLM."""

    score: int = Field(ge=1, le=5, description="Quality on a 1-5 scale.")
    reason: str = Field(description="One sentence justifying the score.")


_JUDGE_SYSTEM = """You evaluate responses from an education-orchestration assistant.
Given a learner question, the rubric for what a great response looks like, and the
actual response produced, score the response 1-5 and give a one-sentence reason.

Score guide:
  5 — meets the rubric fully, grounded, coherent, addresses the question.
  4 — minor gap (slightly generic, or missing one rubric criterion).
  3 — partial answer, plausible but underwhelming.
  2 — off-target or unfounded claims.
  1 — does not answer, hallucinates, or contradicts the rubric.

Output strict JSON only — no commentary outside the structured schema."""


async def judge_response(query: str, rubric: str, response: str) -> JudgeVerdict:
    """One LLM call per test case. Cheap model, temp=0 for stability."""

    judge = get_llm("agent").with_structured_output(JudgeVerdict, method="json_schema")
    return await judge.ainvoke(
        [
            SystemMessage(content=_JUDGE_SYSTEM),
            HumanMessage(
                content=(
                    f"QUERY:\n{query}\n\n"
                    f"RUBRIC:\n{rubric}\n\n"
                    f"RESPONSE:\n{response.strip() or '(empty)'}"
                )
            ),
        ]
    )


# ──────────────────────────────────────────────────────────────────────────────
# Eval loop


@dataclass
class CaseResult:
    case_id: str
    query: str
    expected_agents: list[str]
    actual_agents: list[str]
    routing_correct: bool
    score: int
    reason: str
    response: str
    latency_ms: int


def _load_dataset() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]


async def _run_case(case: dict[str, Any]) -> CaseResult:
    """Drive one case end-to-end through the orchestrator graph."""

    graph = get_graph()
    t_start = time.monotonic()

    initial_state: dict[str, Any] = {
        "learner_id": case["learner_id"],
        "conversation_id": str(uuid.uuid4()),
        "message_id": str(uuid.uuid4()),
        "trace_id": f"eval-{case['id']}",
        "t_start": t_start,
        "user_message": case["query"],
        "history": [],
        "agents_invoked": [],
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
    }

    final_state = await graph.ainvoke(initial_state)
    latency_ms = int((time.monotonic() - t_start) * 1000)

    actual_agents = sorted(final_state.get("agents_invoked", []) or [])
    expected_agents = sorted(case.get("expected_agents", []))
    routing_correct = actual_agents == expected_agents

    response = final_state.get("final_response", "") or ""
    verdict = await judge_response(case["query"], case["rubric"], response)

    return CaseResult(
        case_id=case["id"],
        query=case["query"],
        expected_agents=expected_agents,
        actual_agents=actual_agents,
        routing_correct=routing_correct,
        score=verdict.score,
        reason=verdict.reason,
        response=response,
        latency_ms=latency_ms,
    )


async def _persist(dataset_tag: str, results: list[CaseResult]) -> None:
    async with session_scope() as session:
        repo = EvalRepo(session)
        for r in results:
            await repo.record(
                dataset=dataset_tag,
                test_case_id=r.case_id,
                # "Passed" = routed correctly AND judged ≥ 3. Routing alone is
                # the deterministic bar; the judge is the soft signal.
                passed=r.routing_correct and r.score >= 3,
                score=float(r.score),
                notes=r.reason,
                extra={
                    "expected_agents": r.expected_agents,
                    "actual_agents": r.actual_agents,
                    "query": r.query,
                    "response": r.response,
                    "latency_ms": r.latency_ms,
                },
            )


def _write_markdown(dataset_tag: str, results: list[CaseResult]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{dataset_tag}-{int(time.time())}.md"

    routing_acc = sum(r.routing_correct for r in results) / len(results)
    mean_score = sum(r.score for r in results) / len(results)
    p95_latency = sorted(r.latency_ms for r in results)[int(0.95 * (len(results) - 1))]

    lines: list[str] = []
    lines.append(f"# Eval run — `{dataset_tag}`\n")
    lines.append(f"- Cases: **{len(results)}**")
    lines.append(f"- Routing accuracy: **{routing_acc:.0%}**")
    lines.append(f"- Mean response quality (1-5): **{mean_score:.2f}**")
    lines.append(f"- p95 latency: **{p95_latency} ms**\n")
    lines.append("| case | expected | actual | routing | score | latency | reason |")
    lines.append("| ---- | -------- | ------ | :-----: | :---: | ------: | ------ |")
    for r in results:
        flag = "✅" if r.routing_correct else "❌"
        exp = ",".join(r.expected_agents) or "—"
        act = ",".join(r.actual_agents) or "—"
        reason = r.reason.replace("|", "\\|")
        lines.append(
            f"| {r.case_id} | `{exp}` | `{act}` | {flag} | {r.score} | "
            f"{r.latency_ms} ms | {reason} |"
        )
    out.write_text("\n".join(lines))
    return out


def _print_summary(results: list[CaseResult]) -> tuple[float, float]:
    routing_acc = sum(r.routing_correct for r in results) / len(results)
    mean_score = sum(r.score for r in results) / len(results)
    print()
    print(f"  cases:            {len(results)}")
    print(f"  routing accuracy: {routing_acc:.0%}")
    print(f"  mean quality:     {mean_score:.2f} / 5")
    for r in results:
        flag = "PASS" if r.routing_correct and r.score >= 3 else "FAIL"
        exp = ",".join(r.expected_agents) or "—"
        act = ",".join(r.actual_agents) or "—"
        print(
            f"  {flag}  {r.case_id:<22}  exp={exp:<20} act={act:<20} "
            f"score={r.score}  ({r.latency_ms} ms)"
        )
    return routing_acc, mean_score


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="golden_v1", help="Run tag for persistence.")
    parser.add_argument(
        "--min-routing-accuracy",
        type=float,
        default=0.85,
        help="CI gate — exit non-zero below this threshold.",
    )
    args = parser.parse_args()

    # Make sure the eval_runs table exists when running against a fresh DB.
    await init_db()

    cases = _load_dataset()
    log.info("evals_start", count=len(cases), dataset=args.dataset)

    # Sequential — keeps OpenAI usage predictable and the markdown table ordered.
    results: list[CaseResult] = []
    for case in cases:
        try:
            res = await _run_case(case)
        except Exception as exc:
            log.exception("eval_case_failed", case_id=case["id"], error=str(exc))
            res = CaseResult(
                case_id=case["id"],
                query=case["query"],
                expected_agents=sorted(case.get("expected_agents", [])),
                actual_agents=[],
                routing_correct=False,
                score=1,
                reason=f"exception: {exc}",
                response="",
                latency_ms=0,
            )
        results.append(res)

    await _persist(args.dataset, results)
    md = _write_markdown(args.dataset, results)
    routing_acc, _ = _print_summary(results)
    print(f"\n  results: {md}")

    return 0 if routing_acc >= args.min_routing_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
