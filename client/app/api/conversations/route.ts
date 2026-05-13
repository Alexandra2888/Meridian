import type { NextRequest } from "next/server";

import { apiUrl } from "@/lib/api";

/**
 * Proxies GET /api/conversations?learner_id=… → FastAPI /conversations.
 * Mirrors the proxy pattern in `app/api/chat/route.ts` so the browser never
 * talks to the FastAPI host directly. RFC §9.2.
 */
export async function GET(request: NextRequest) {
  const learnerId = request.nextUrl.searchParams.get("learner_id");
  if (!learnerId) {
    return Response.json(
      { error: "learner_id is required" },
      { status: 400 },
    );
  }
  const limit = request.nextUrl.searchParams.get("limit") ?? "50";

  const upstream = await fetch(
    apiUrl(
      `/conversations?learner_id=${encodeURIComponent(learnerId)}&limit=${encodeURIComponent(limit)}`,
    ),
    {
      headers: { Accept: "application/json" },
      cache: "no-store",
    },
  );

  if (!upstream.ok) {
    return Response.json(
      { error: `Upstream returned ${upstream.status}` },
      { status: upstream.status || 502 },
    );
  }
  const body = await upstream.text();
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
