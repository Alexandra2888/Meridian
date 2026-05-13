import { Sparkles } from "lucide-react";

import { ChatShell } from "@/components/chat/chat-shell";
import { LearnerContextCard } from "@/components/learner/learner-context-card";
import type { LearnerProfile } from "@/lib/types";

/**
 * Stub learner used until the FastAPI `/learner/{id}` endpoint ships. Once
 * the API is live, replace this with `await fetchLearnerProfile(...)` from
 * `lib/api.ts`. The shape matches `LearnerProfile`, so the UI flips over
 * automatically. RFC §0.1 (stubbed-vs-real boundary).
 */
const STUB_LEARNER: LearnerProfile = {
  learner_id: "stub-001",
  name: "Adaeze Okafor",
  email: "adaeze.o@learner.nexford.org",
  enrolment_status: "applied",
  program: "BBA Data Analytics",
  interests: ["data", "marketing", "product"],
  career_goals: ["data analyst", "product analyst"],
  country: "Nigeria",
};

const CANONICAL_PROMPTS = [
  "What program is right for me, and what jobs does it lead to once I graduate?",
  "Which BBA concentration matches my interests?",
  "What does the career path look like for data analytics graduates?",
];

export default function Page() {
  return (
    <main className="flex flex-1 flex-col min-h-0">
      <Header />
      <ChatShell
        header={<LearnerContextCard learner={STUB_LEARNER} />}
        emptyState={<EmptyState />}
      />
    </main>
  );
}

function Header() {
  return (
    <header className="border-b border-border-subtle bg-surface-sunken">
      <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 py-3 md:px-6">
        <div
          aria-hidden
          className="flex size-7 items-center justify-center rounded-md bg-accent-orchestration text-primary-foreground"
        >
          <span className="font-mono text-small font-semibold">M</span>
        </div>
        <div className="min-w-0">
          <p className="truncate font-medium">Meridian</p>
          <p className="truncate text-micro text-text-subtle font-mono uppercase tracking-wider">
            learner orchestration · v1
          </p>
        </div>
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
