"use client";

import { create } from "zustand";

import type {
  MessageFinalMetadata,
  OrchestratorNode,
  TraceStep,
  TraceStepStatus,
} from "@/lib/types";

/**
 * Per-message trace state, keyed by message_id. The chat message list and the
 * trace panel both read from here; SSE event handlers in `lib/stream.ts`
 * write to here. RFC §4.7.
 */
export interface MessageTrace {
  steps: Partial<Record<OrchestratorNode, TraceStep>>;
  final?: MessageFinalMetadata;
}

interface TraceStore {
  messages: Record<string, MessageTrace>;

  startMessage: (messageId: string) => void;
  updateStep: (
    messageId: string,
    node: OrchestratorNode,
    status: TraceStepStatus,
    durationMs?: number,
  ) => void;
  setFinal: (messageId: string, final: MessageFinalMetadata) => void;
  /**
   * Hydrate a completed message's trace from persisted server data, so the
   * agent-trace panel + cost/latency badges survive a reload. Steps are
   * recorded as already-`done` since the run finished before this seed.
   */
  seedMessage: (
    messageId: string,
    stepDurations: Partial<Record<OrchestratorNode, number>>,
    final: MessageFinalMetadata,
  ) => void;
  reset: () => void;
}

export const useTraceStore = create<TraceStore>((set) => ({
  messages: {},

  startMessage: (messageId) =>
    set((state) => ({
      messages: { ...state.messages, [messageId]: { steps: {} } },
    })),

  updateStep: (messageId, node, status, durationMs) =>
    set((state) => {
      const existing = state.messages[messageId] ?? { steps: {} };
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
        messages: {
          ...state.messages,
          [messageId]: {
            ...existing,
            steps: { ...existing.steps, [node]: next },
          },
        },
      };
    }),

  setFinal: (messageId, final) =>
    set((state) => {
      const existing = state.messages[messageId] ?? { steps: {} };
      return {
        messages: { ...state.messages, [messageId]: { ...existing, final } },
      };
    }),

  seedMessage: (messageId, stepDurations, final) =>
    set((state) => {
      const steps: Partial<Record<OrchestratorNode, TraceStep>> = {};
      for (const [node, durationMs] of Object.entries(stepDurations)) {
        if (typeof durationMs !== "number") continue;
        steps[node as OrchestratorNode] = {
          node: node as OrchestratorNode,
          status: "done",
          durationMs,
        };
      }
      return {
        messages: { ...state.messages, [messageId]: { steps, final } },
      };
    }),

  reset: () => set({ messages: {} }),
}));
