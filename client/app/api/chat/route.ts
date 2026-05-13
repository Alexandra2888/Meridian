import { apiUrl } from "@/lib/api";

/**
 * Proxies POST /api/chat → FastAPI /chat, piping the SSE body through.
 * RFC §9.2: server-side proxy keeps the API URL off the client and avoids
 * CORS without auth complexity in v1.
 */
export async function POST(request: Request) {
  const body = await request.text();

  const upstream = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body,
    cache: "no-store",
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(
      JSON.stringify({
        error: `Upstream orchestrator returned ${upstream.status}`,
      }),
      {
        status: upstream.status || 502,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
