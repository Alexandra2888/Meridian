import { z } from "zod";

import type { LearnerProfile, SseEvent } from "@/lib/types";

/**
 * SSE parser for the orchestrator stream.
 *
 * The FastAPI `/chat` endpoint emits proper Server-Sent Events:
 *
 *     event: status
 *     data: {"event":"status","node":"plan","status":"started"}
 *
 *     event: delta
 *     data: {"event":"delta","content":"Based "}
 *
 * Events are separated by a blank line (`\n\n`). Each event has an `event:`
 * line carrying the type and a `data:` line carrying a JSON payload. RFC §4.7.
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

// The data payloads from the server include a redundant `event` field that we
// can safely ignore on the client — the SSE `event:` line is authoritative.
const statusDataSchema = z
  .object({
    node: orchestratorNodeSchema,
    status: z.enum(["started", "finished"]),
    duration_ms: z.number().optional(),
  })
  .passthrough();

const deltaDataSchema = z.object({ content: z.string() }).passthrough();

const errorDataSchema = z
  .object({ message: z.string(), recoverable: z.boolean().default(false) })
  .passthrough();

const finalDataSchema = z
  .object({
    agents_invoked: z.array(agentNameSchema),
    total_latency_ms: z.number(),
    cost_usd: z.number(),
    tokens_in: z.number().optional(),
    tokens_out: z.number().optional(),
    conversation_id: z.string(),
    message_id: z.string(),
    learner: z.unknown().nullable().optional(),
  })
  .passthrough();

/** Parse a single SSE event block (text between `\n\n` delimiters). */
export function parseSseBlock(block: string): SseEvent | null {
  let event: string | null = null;
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (!line || line.startsWith(":")) continue; // empty + comments

    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      // Per spec, `data:` may have a leading space — strip a single one only.
      const v = line.slice(5);
      dataLines.push(v.startsWith(" ") ? v.slice(1) : v);
    }
  }

  if (!event || dataLines.length === 0) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }

  switch (event) {
    case "status": {
      const r = statusDataSchema.safeParse(payload);
      return r.success ? { type: "status", data: r.data } : null;
    }
    case "delta": {
      const r = deltaDataSchema.safeParse(payload);
      return r.success ? { type: "delta", data: r.data } : null;
    }
    case "error": {
      const r = errorDataSchema.safeParse(payload);
      return r.success ? { type: "error", data: r.data } : null;
    }
    case "final": {
      const r = finalDataSchema.safeParse(payload);
      if (!r.success) return null;
      // The learner snapshot is treated as opaque at the wire boundary —
      // the page already has the typed LearnerProfile from the /learner
      // fetch, so we don't need to re-validate it here.
      return {
        type: "final",
        data: {
          ...r.data,
          learner: (r.data.learner ?? null) as LearnerProfile | null,
        },
      };
    }
    case "done":
      return { type: "done", data: null };
    default:
      return null;
  }
}

/**
 * Async iterator over a fetch-returned SSE body. Yields each well-formed
 * event in order; malformed blocks are skipped so a single bad event can't
 * kill the stream.
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

      // Events are separated by a blank line (`\n\n`).
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = parseSseBlock(block);
        if (event) yield event;
      }
    }
    // Flush trailing block, if any.
    if (buffer.trim()) {
      const event = parseSseBlock(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
