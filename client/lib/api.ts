import type { LearnerProfile } from "@/lib/types";

/**
 * Server-side base URL for the FastAPI orchestrator. Read via `API_URL` env;
 * the Next.js route handler proxies through so the browser never talks to
 * Fly.io directly (no CORS, no leaked URL). RFC §9.2.
 */
const API_BASE = process.env.API_URL ?? "http://localhost:8000";

export const apiUrl = (path: string) =>
  `${API_BASE.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;

/** Fetches the learner profile from the FastAPI `/learner/{id}` endpoint. */
export async function fetchLearnerProfile(
  learnerId: string,
  init?: RequestInit,
): Promise<LearnerProfile> {
  const res = await fetch(apiUrl(`/learner/${encodeURIComponent(learnerId)}`), {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(`Failed to load learner ${learnerId}: ${res.status}`);
  }
  return (await res.json()) as LearnerProfile;
}
