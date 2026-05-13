import { Sparkles } from "lucide-react";

import { ChatShell } from "@/components/chat/chat-shell";
import { LearnerContextCard } from "@/components/learner/learner-context-card";
import { LearnerSelector } from "@/components/learner/learner-selector";
import { fetchLearnerProfile, fetchLearnerSummaries } from "@/lib/api";
import type { LearnerProfile, LearnerSummary } from "@/lib/types";

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
  searchParams: Promise<{ learner?: string }>;
}) {
  const { learner: learnerParam } = await searchParams;

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

  let profile: LearnerProfile | null = null;
  let loadError: string | null = null;
  try {
    profile = await fetchLearnerProfile(learnerId, { cache: "no-store" });
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Failed to load profile";
  }

  return (
    <main className="flex flex-1 flex-col min-h-0">
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
        learnerId={learnerId}
        header={
          <LearnerContextCard
            learner={profile}
            loading={false}
            errorMessage={loadError ?? undefined}
          />
        }
        emptyState={<EmptyState />}
      />
    </main>
  );
}

function Header({ selector }: { selector?: React.ReactNode }) {
  return (
    <header className="border-b border-border-subtle bg-surface-sunken">
      <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 py-3 md:px-6">
        <div
          aria-hidden
          className="flex size-7 items-center justify-center rounded-md bg-accent-orchestration text-primary-foreground"
        >
          <span className="font-mono text-small font-semibold">M</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">Meridian</p>
          <p className="truncate text-micro text-text-subtle font-mono uppercase tracking-wider">
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
