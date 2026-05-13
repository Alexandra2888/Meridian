/**
 * Shared TS types that mirror the FastAPI / Pydantic schemas on the API side.
 * Source of truth lives in the RFC (§4.6, §4.7). When the API ships, generate
 * these from the OpenAPI schema instead of hand-mirroring.
 */

export type AgentName = "discovery" | "career";

export type EnrolmentStatus =
  | "prospect"
  | "applied"
  | "enrolled"
  | "graduated";

export interface LearnerProfile {
  learner_id: string;
  name: string;
  email: string;
  enrolment_status: EnrolmentStatus;
  program: string | null;
  interests: string[];
  career_goals: string[];
  country: string | null;
}

export interface LearnerSummary {
  learner_id: string;
  name: string;
  enrolment_status: EnrolmentStatus;
  program: string | null;
}

/** A node in the LangGraph orchestrator. Drives the trace panel. */
export type OrchestratorNode =
  | "load_context"
  | "plan"
  | "discovery_agent"
  | "career_agent"
  | "synthesize"
  | "persist";

export type TraceStepStatus = "pending" | "running" | "done" | "error";

export interface TraceStep {
  node: OrchestratorNode;
  status: TraceStepStatus;
  startedAt?: number;
  finishedAt?: number;
  durationMs?: number;
}

export interface ChatMessageHistory {
  role: "user" | "assistant";
  content: string;
}

export interface MessageFinalMetadata {
  messageId: string;
  conversationId: string;
  agentsInvoked: AgentName[];
  totalLatencyMs: number;
  costUsd: number;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  learner_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

/** SSE event protocol — RFC §4.7. */
export type SseEvent =
  | {
      type: "status";
      data: {
        node: OrchestratorNode;
        status: "started" | "finished";
        duration_ms?: number;
      };
    }
  | { type: "delta"; data: { content: string } }
  | { type: "error"; data: { message: string; recoverable: boolean } }
  | {
      type: "final";
      data: {
        agents_invoked: AgentName[];
        total_latency_ms: number;
        cost_usd: number;
        tokens_in?: number;
        tokens_out?: number;
        conversation_id: string;
        message_id: string;
        learner?: LearnerProfile | null;
      };
    }
  | { type: "done"; data: null };
