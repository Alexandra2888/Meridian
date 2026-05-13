import { z } from "zod";

import type { SseEvent } from "@/lib/types";

/**
 * SSE parser for the orchestrator stream. The FastAPI `/chat` endpoint emits
 * newline-delimited JSON events; this parser yields one typed event at a time.
 * RFC §4.7.
 */

const orchestratorNodeSchema = z.enum([
  "load_context",
  "plan",
  "discovery_agent",
  "career_agent",
  "synthesize",
  "persist",
]);

const agentNameSchema = z.enum(["discovery", "career"]);

const sseEventSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("status"),
    data: z.object({
      node: orchestratorNodeSchema,
      status: z.enum(["started", "finished"]),
      duration_ms: z.number().optional(),
    }),
  }),
  z.object({
    type: z.literal("delta"),
    data: z.object({ content: z.string() }),
  }),
  z.object({
    type: z.literal("error"),
    data: z.object({ message: z.string(), recoverable: z.boolean() }),
  }),
  z.object({
    type: z.literal("final"),
    data: z.object({
      agents_invoked: z.array(agentNameSchema),
      total_latency_ms: z.number(),
      cost_usd: z.number(),
      conversation_id: z.string(),
      turn_id: z.string(),
    }),
  }),
  z.object({ type: z.literal("done"), data: z.null() }),
]);

export function parseSseLine(line: string): SseEvent | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith(":")) return null;

  try {
    const parsed = JSON.parse(trimmed);
    const result = sseEventSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

/**
 * Async iterator over a fetch-returned SSE body. Yields each well-formed
 * event in order, ignoring malformed lines (so a single bad event can't kill
 * the stream).
 */
export async function* iterSseEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIdx: number;
      while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        const event = parseSseLine(line);
        if (event) yield event;
      }
    }
    if (buffer) {
      const event = parseSseLine(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
