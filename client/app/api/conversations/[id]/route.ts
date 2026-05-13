import type { NextRequest } from "next/server";

import { apiUrl } from "@/lib/api";

type Params = { id: string };

/**
 * Proxies GET/PATCH/DELETE on a single conversation through to FastAPI.
 * The sidebar's rename + delete affordances call these from the browser.
 */

export async function GET(
  _request: NextRequest,
  context: { params: Promise<Params> },
) {
  const { id } = await context.params;
  const upstream = await fetch(apiUrl(`/conversations/${encodeURIComponent(id)}`), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!upstream.ok) {
    return Response.json(
      { error: `Upstream returned ${upstream.status}` },
      { status: upstream.status || 502 },
    );
  }
  return new Response(await upstream.text(), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<Params> },
) {
  const { id } = await context.params;
  const body = await request.text();
  const upstream = await fetch(apiUrl(`/conversations/${encodeURIComponent(id)}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body,
    cache: "no-store",
  });
  if (!upstream.ok) {
    return Response.json(
      { error: `Upstream returned ${upstream.status}` },
      { status: upstream.status || 502 },
    );
  }
  return new Response(await upstream.text(), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<Params> },
) {
  const { id } = await context.params;
  const upstream = await fetch(apiUrl(`/conversations/${encodeURIComponent(id)}`), {
    method: "DELETE",
    cache: "no-store",
  });
  if (upstream.status === 204) {
    return new Response(null, { status: 204 });
  }
  if (!upstream.ok) {
    return Response.json(
      { error: `Upstream returned ${upstream.status}` },
      { status: upstream.status || 502 },
    );
  }
  return new Response(null, { status: 204 });
}
