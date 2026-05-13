"use client";

import { useCallback, useRef, useState } from "react";

import { Composer } from "@/components/chat/composer";
import {
  MessageList,
  type ChatMessageView,
} from "@/components/chat/message-list";
import { iterSseEvents } from "@/lib/stream";
import { useTraceStore } from "@/lib/trace-store";
import type { ChatTurnHistory, OrchestratorNode } from "@/lib/types";

interface ChatShellProps {
  /** HubSpot contact ID resolved by the page from `?learner=…`. */
  learnerId: string;
  /** Optional CRM card or other header content rendered above the message list. */
  header?: React.ReactNode;
  /** Empty-state slot when no messages have been sent yet. */
  emptyState?: React.ReactNode;
}

/** Maps server-side status names to the trace-store's status vocabulary. */
function mapStatus(status: "started" | "finished") {
  return status === "started" ? "running" : "done";
}

/**
 * Holds chat state + drives the SSE round-trip. For each user turn:
 *   1. POST to `/api/chat` with the running history + conversation id.
 *   2. Iterate the SSE stream — `status` events update the trace store,
 *      `delta` events append to the assistant bubble, `final` finalizes the
 *      turn and persists the conversation id for the next turn.
 *
 * Trace state lives in `useTraceStore` (RFC §4.7) so the agent-trace panel
 * can subscribe by `turnId` without re-rendering the whole shell on each
 * delta.
 */
export function ChatShell({ learnerId, header, emptyState }: ChatShellProps) {
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [pending, setPending] = useState(false);
  const conversationIdRef = useRef<string | null>(null);

  const startTurn = useTraceStore((s) => s.startTurn);
  const updateStep = useTraceStore((s) => s.updateStep);
  const setFinal = useTraceStore((s) => s.setFinal);

  const appendDelta = useCallback((messageId: string, content: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, content: m.content + content } : m,
      ),
    );
  }, []);

  const finalizeMessage = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, isStreaming: false } : m,
      ),
    );
  }, []);

  const handleSubmit = useCallback(
    async (text: string) => {
      const userId = crypto.randomUUID();
      // The assistant's `id` doubles as the local turn key — the trace store
      // is keyed by it until the server's authoritative `turn_id` arrives in
      // the `final` event.
      const assistantId = crypto.randomUUID();

      // Snapshot history BEFORE we append the new user turn so the server
      // doesn't see its own incoming message in `history`.
      const history: ChatTurnHistory[] = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: text },
        {
          id: assistantId,
          role: "assistant",
          content: "",
          turnId: assistantId,
          isStreaming: true,
        },
      ]);
      setPending(true);
      startTurn(assistantId);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            learner_id: learnerId,
            message: text,
            conversation_id: conversationIdRef.current,
            history,
          }),
        });

        if (!res.ok || !res.body) {
          throw new Error(`Chat request failed: ${res.status}`);
        }

        for await (const event of iterSseEvents(res.body)) {
          switch (event.type) {
            case "status": {
              const node = event.data.node as OrchestratorNode;
              updateStep(
                assistantId,
                node,
                mapStatus(event.data.status),
                event.data.duration_ms,
              );
              break;
            }
            case "delta":
              appendDelta(assistantId, event.data.content);
              break;
            case "final":
              conversationIdRef.current = event.data.conversation_id;
              setFinal(assistantId, {
                turnId: event.data.turn_id,
                conversationId: event.data.conversation_id,
                agentsInvoked: event.data.agents_invoked,
                totalLatencyMs: event.data.total_latency_ms,
                costUsd: event.data.cost_usd,
              });
              break;
            case "error":
              appendDelta(
                assistantId,
                `\n\n_Error: ${event.data.message}_`,
              );
              break;
            case "done":
              break;
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "unknown error";
        appendDelta(assistantId, `\n\n_Error: ${msg}_`);
      } finally {
        finalizeMessage(assistantId);
        setPending(false);
      }
    },
    [
      learnerId,
      messages,
      startTurn,
      updateStep,
      setFinal,
      appendDelta,
      finalizeMessage,
    ],
  );

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {header ? (
        <div className="border-b border-border-subtle bg-surface-sunken/60">
          <div className="mx-auto w-full max-w-3xl px-4 py-4 md:px-6">
            {header}
          </div>
        </div>
      ) : null}

      <MessageList messages={messages} emptyState={emptyState} />

      <div className="border-t border-border-subtle bg-surface-sunken/60">
        <Composer onSubmit={handleSubmit} disabled={pending} />
      </div>
    </div>
  );
}
