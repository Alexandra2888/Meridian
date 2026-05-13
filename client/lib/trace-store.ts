"use client";

import { create } from "zustand";

import type {
  OrchestratorNode,
  TraceStep,
  TraceStepStatus,
  TurnFinalMetadata,
} from "@/lib/types";

/**
 * Per-turn trace state, keyed by turn_id. The chat message list and the
 * trace panel both read from here; SSE event handlers in `lib/stream.ts`
 * write to here. RFC §4.7.
 */
export interface TurnTrace {
  steps: Partial<Record<OrchestratorNode, TraceStep>>;
  final?: TurnFinalMetadata;
}

interface TraceStore {
  turns: Record<string, TurnTrace>;

  startTurn: (turnId: string) => void;
  updateStep: (
    turnId: string,
    node: OrchestratorNode,
    status: TraceStepStatus,
    durationMs?: number,
  ) => void;
  setFinal: (turnId: string, final: TurnFinalMetadata) => void;
  reset: () => void;
}

export const useTraceStore = create<TraceStore>((set) => ({
  turns: {},

  startTurn: (turnId) =>
    set((state) => ({
      turns: { ...state.turns, [turnId]: { steps: {} } },
    })),

  updateStep: (turnId, node, status, durationMs) =>
    set((state) => {
      const existing = state.turns[turnId] ?? { steps: {} };
      const prior = existing.steps[node];
      const now = Date.now();
      const next: TraceStep = {
        node,
        status,
        startedAt:
          prior?.startedAt ?? (status === "running" ? now : undefined),
        finishedAt: status === "done" || status === "error" ? now : undefined,
        durationMs:
          durationMs ??
          (prior?.startedAt && (status === "done" || status === "error")
            ? now - prior.startedAt
            : prior?.durationMs),
      };
      return {
        turns: {
          ...state.turns,
          [turnId]: {
            ...existing,
            steps: { ...existing.steps, [node]: next },
          },
        },
      };
    }),

  setFinal: (turnId, final) =>
    set((state) => {
      const existing = state.turns[turnId] ?? { steps: {} };
      return {
        turns: { ...state.turns, [turnId]: { ...existing, final } },
      };
    }),

  reset: () => set({ turns: {} }),
}));
