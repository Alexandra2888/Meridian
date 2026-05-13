"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { useTraceStore } from "@/lib/trace-store";
import type { OrchestratorNode } from "@/lib/types";

import { TraceStepRow } from "@/components/chat/trace-step";

/** Render order for the panel — matches the LangGraph state machine in RFC §4.3. */
const RENDER_ORDER: OrchestratorNode[] = [
  "load_context",
  "plan",
  "discovery_agent",
  "career_agent",
  "synthesize",
];

interface AgentTraceProps {
  turnId: string;
  defaultOpen?: boolean;
}

/**
 * The orchestration cockpit panel for a single assistant turn — RFC §5.2.
 * Reads from the Zustand trace store; each row animates pending → running →
 * done as `status` events arrive. The Discovery and Career rows render in
 * parallel because the underlying orchestrator runs them in parallel.
 */
export function AgentTrace({ turnId, defaultOpen = true }: AgentTraceProps) {
  const [open, setOpen] = useState(defaultOpen);
  const trace = useTraceStore((s) => s.turns[turnId]);

  if (!trace) return null;

  const visibleNodes = RENDER_ORDER.filter((node) => trace.steps[node]);
  if (visibleNodes.length === 0) return null;

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-md border border-border-subtle bg-surface-sunken/60"
    >
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-2 text-small text-text-muted hover:text-foreground">
        <span className="font-mono text-micro uppercase tracking-wider text-text-subtle">
          trace
        </span>
        <span className="flex-1 text-left">
          {visibleNodes.length} step{visibleNodes.length === 1 ? "" : "s"}
        </span>
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          className={cn(
            "transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="px-3 pb-2">
          {visibleNodes.map((node) => (
            <TraceStepRow key={node} node={node} step={trace.steps[node]} />
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}
