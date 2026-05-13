"use client";

import { CheckCircle2, CircleDashed, CircleAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { TraceStep, OrchestratorNode } from "@/lib/types";

const NODE_LABEL: Record<OrchestratorNode, string> = {
  load_context: "Loading profile from HubSpot",
  plan: "Planning route",
  discovery_agent: "Discovery agent",
  career_agent: "Career agent",
  synthesize: "Synthesizing response",
  persist: "Persisting turn",
};

interface TraceStepRowProps {
  node: OrchestratorNode;
  step: TraceStep | undefined;
}

/**
 * Single row in the agent-trace panel. Renders pending → running → done with
 * a CSS-only transition (RFC §5.5: no Framer Motion). The row is data-driven
 * from the trace store so a new agent appears automatically when the planner
 * emits its node.
 */
export function TraceStepRow({ node, step }: TraceStepRowProps) {
  const status = step?.status ?? "pending";

  return (
    <li
      className={cn(
        "flex items-center gap-2 py-1.5 text-small transition-opacity",
        status === "pending" && "opacity-50",
      )}
    >
      <StatusIcon status={status} />
      <span
        className={cn(
          "flex-1 truncate",
          status === "done" && "text-foreground",
          status === "running" && "text-foreground",
          status === "pending" && "text-text-muted",
          status === "error" && "text-state-error",
        )}
      >
        {NODE_LABEL[node]}
      </span>
      {step?.durationMs != null ? (
        <span className="font-mono text-micro text-text-subtle tabular-nums">
          {formatMs(step.durationMs)}
        </span>
      ) : status === "running" ? (
        <span className="font-mono text-micro text-accent-orchestration">
          running…
        </span>
      ) : null}
    </li>
  );
}

function StatusIcon({ status }: { status: TraceStep["status"] }) {
  if (status === "done") {
    return (
      <CheckCircle2
        size={14}
        strokeWidth={1.75}
        className="text-state-success shrink-0"
        aria-label="done"
      />
    );
  }
  if (status === "error") {
    return (
      <CircleAlert
        size={14}
        strokeWidth={1.75}
        className="text-state-error shrink-0"
        aria-label="error"
      />
    );
  }
  if (status === "running") {
    return (
      <span
        className="pulse-dot inline-block size-2 shrink-0 rounded-full bg-accent-orchestration"
        aria-label="running"
      />
    );
  }
  return (
    <CircleDashed
      size={14}
      strokeWidth={1.75}
      className="text-text-subtle shrink-0"
      aria-label="pending"
    />
  );
}

function formatMs(ms: number) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
