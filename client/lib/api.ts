import type {
  ConversationDetail,
  ConversationSummary,
  LearnerProfile,
  LearnerSummary,
} from "@/lib/types";

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

/** Fetches the picker list from the FastAPI `/learners` endpoint. */
export async function fetchLearnerSummaries(
  init?: RequestInit,
): Promise<LearnerSummary[]> {
  const res = await fetch(apiUrl(`/learners`), {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(`Failed to load learners: ${res.status}`);
  }
  return (await res.json()) as LearnerSummary[];
}

/** Sidebar list — conversations belonging to `learnerId`, recency-ordered. */
export async function fetchConversations(
  learnerId: string,
  init?: RequestInit,
): Promise<ConversationSummary[]> {
  const res = await fetch(
    apiUrl(`/conversations?learner_id=${encodeURIComponent(learnerId)}`),
    {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to load conversations: ${res.status}`);
  }
  return (await res.json()) as ConversationSummary[];
}

/** Full conversation with ordered messages, used to seed the chat shell. */
export async function fetchConversation(
  conversationId: string,
  init?: RequestInit,
): Promise<ConversationDetail> {
  const res = await fetch(
    apiUrl(`/conversations/${encodeURIComponent(conversationId)}`),
    {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to load conversation ${conversationId}: ${res.status}`);
  }
  return (await res.json()) as ConversationDetail;
}
