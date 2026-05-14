import { Sparkles } from "lucide-react";

import { ChatShell, type InitialTraceSeed } from "@/components/chat/chat-shell";
import type { ChatMessageView } from "@/components/chat/message-list";
import { ConversationSidebar } from "@/components/conversations/conversation-sidebar";
import { MobileSidebarToggle } from "@/components/conversations/mobile-sidebar-toggle";
import { LearnerContextCard } from "@/components/learner/learner-context-card";
import { LearnerSelector } from "@/components/learner/learner-selector";
import {
  fetchConversation,
  fetchConversations,
  fetchLearnerProfile,
  fetchLearnerSummaries,
} from "@/lib/api";
import type {
  ConversationDetail,
  ConversationSummary,
  LearnerProfile,
  LearnerSummary,
} from "@/lib/types";

const CANONICAL_PROMPTS = [
  "What program is right for me, and what jobs does it lead to once I graduate?",
  "Which BBA concentration matches my interests?",
  "What does the career path look like for data analytics graduates?",
];

const DEFAULT_LEARNER_ID =
  process.env.NEXT_PUBLIC_DEFAULT_LEARNER_ID ?? "stub-001";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ learner?: string; conversation?: string }>;
}) {
  const { learner: learnerParam, conversation: conversationParam } =
    await searchParams;

  // Pull the picker list first — if `?learner=` isn't set we default to the
  // first learner returned (typically the first HubSpot contact or the first
  // stub) instead of an arbitrary id that may 404.
  let learners: LearnerSummary[] = [];
  try {
    learners = await fetchLearnerSummaries({ cache: "no-store" });
  } catch {
    /* selector just hides itself if the list fetch fails */
  }

  const learnerId =
    learnerParam?.trim() || learners[0]?.learner_id || DEFAULT_LEARNER_ID;

  // Profile + conversation list are independent — fetch in parallel.
  const [profileResult, conversationsResult] = await Promise.allSettled([
    fetchLearnerProfile(learnerId, { cache: "no-store" }),
    fetchConversations(learnerId, { cache: "no-store" }),
  ]);

  const profile: LearnerProfile | null =
    profileResult.status === "fulfilled" ? profileResult.value : null;
  const loadError: string | null =
    profileResult.status === "rejected"
      ? profileResult.reason instanceof Error
        ? profileResult.reason.message
        : "Failed to load profile"
      : null;
  const conversations: ConversationSummary[] =
    conversationsResult.status === "fulfilled" ? conversationsResult.value : [];

  // If a conversation is selected via `?conversation=`, hydrate its messages
  // so the chat shell renders the full thread on mount.
  let activeConversation: ConversationDetail | null = null;
  if (conversationParam) {
    try {
      activeConversation = await fetchConversation(conversationParam, {
        cache: "no-store",
      });
      // Guard against a learner switch that leaves a stale conversation id
      // in the URL — fall back to a fresh thread for the new learner.
      if (activeConversation.learner_id !== learnerId) {
        activeConversation = null;
      }
    } catch {
      activeConversation = null;
    }
  }

  const initialMessages: ChatMessageView[] | undefined = activeConversation
    ? activeConversation.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        messageId: m.role === "assistant" ? m.id : undefined,
        isStreaming: false,
      }))
    : undefined;

  // Pre-shaped trace data for the assistant messages so the agent-trace panel
  // + cost/latency badges render on first paint after reload.
  const initialTrace: InitialTraceSeed[] | undefined = activeConversation
    ? activeConversation.messages
        .filter((m) => m.role === "assistant")
        .map((m) => ({
          messageId: m.id,
          stepDurations: m.step_durations ?? {},
          final: {
            messageId: m.id,
            conversationId: activeConversation.id,
            agentsInvoked: m.agents_invoked ?? [],
            totalLatencyMs: m.latency_ms ?? 0,
            costUsd: m.cost_usd ?? 0,
          },
        }))
    : undefined;

  const activeConversationId = activeConversation?.id ?? null;

  return (
    <main className="flex flex-1 min-h-0">
      <ConversationSidebar
        learnerId={learnerId}
        conversations={conversations}
        activeConversationId={activeConversationId}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          selector={
            learners.length > 0 ? (
              <LearnerSelector
                learners={learners}
                currentLearnerId={learnerId}
              />
            ) : null
          }
        />
        <ChatShell
          key={`${learnerId}:${activeConversationId ?? "new"}`}
          learnerId={learnerId}
          initialConversationId={activeConversationId}
          initialMessages={initialMessages}
          initialTrace={initialTrace}
          header={
            <LearnerContextCard
              learner={profile}
              loading={false}
              errorMessage={loadError ?? undefined}
            />
          }
          emptyState={<EmptyState />}
        />
      </div>
    </main>
  );
}

function Header({ selector }: { selector?: React.ReactNode }) {
  return (
    <header className="border-b border-border-subtle bg-surface-sunken">
      <div className="mx-auto flex w-full max-w-5xl items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4 sm:py-3 md:px-6">
        <MobileSidebarToggle />
        <div
          aria-hidden
          className="flex size-7 shrink-0 items-center justify-center rounded-md bg-accent-orchestration text-primary-foreground"
        >
          <span className="font-mono text-small font-semibold">M</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">Meridian</p>
          <p className="hidden truncate text-micro text-text-subtle font-mono uppercase tracking-wider sm:block">
            learner orchestration · v1
          </p>
        </div>
        {selector ? <div className="shrink-0">{selector}</div> : null}
      </div>
    </header>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-accent-orchestration-soft text-accent-orchestration">
        <Sparkles size={20} strokeWidth={1.75} />
      </div>
      <div className="space-y-2">
        <p className="text-foreground">One question. One coherent answer.</p>
        <p className="text-small text-text-muted">
          Meridian routes between discovery, career, and your CRM context — and
          synthesizes a single response. Try one of the canonical questions
          below to see the orchestration run.
        </p>
      </div>
      <ul className="flex w-full max-w-xl flex-col gap-2">
        {CANONICAL_PROMPTS.map((prompt) => (
          <li
            key={prompt}
            className="rounded-md border border-border-subtle bg-card px-3 py-2 text-left text-small text-text-muted"
          >
            {prompt}
          </li>
        ))}
      </ul>
    </div>
  );
}
