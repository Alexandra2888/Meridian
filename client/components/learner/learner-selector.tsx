"use client";

import { ChevronDown, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { cn } from "@/lib/utils";
import type { LearnerSummary } from "@/lib/types";

interface LearnerSelectorProps {
  learners: LearnerSummary[];
  currentLearnerId: string;
}

/**
 * Demo affordance — switch the active learner by setting `?learner=<id>`.
 * Uses a native `<select>` for accessibility + zero new deps. Wrapping the
 * navigation in `useTransition` keeps the page interactive while the next
 * server render fetches the new profile from HubSpot.
 */
export function LearnerSelector({
  learners,
  currentLearnerId,
}: LearnerSelectorProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  if (learners.length === 0) return null;

  const onChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (!value || value === currentLearnerId) return;
    startTransition(() => {
      router.push(`/?learner=${encodeURIComponent(value)}`);
    });
  };

  return (
    <label
      className={cn(
        "relative inline-flex items-center gap-2 rounded-md border border-border-subtle bg-card pl-2.5 pr-8 py-1.5",
        "text-small text-text-muted hover:text-foreground transition-colors",
        "focus-within:border-accent-orchestration/60 focus-within:ring-2 focus-within:ring-accent-orchestration/30",
        isPending && "opacity-60",
      )}
    >
      <Users size={14} strokeWidth={1.75} className="text-text-subtle" />
      <span className="font-mono text-micro uppercase tracking-wider text-text-subtle">
        learner
      </span>
      <select
        value={currentLearnerId}
        onChange={onChange}
        disabled={isPending}
        className={cn(
          "appearance-none bg-transparent outline-none",
          "text-small text-foreground cursor-pointer",
          "max-w-[180px] truncate",
        )}
      >
        {/* If currentLearnerId isn't in the list (e.g. arbitrary ?learner= param),
            still surface it so the select reflects the URL. */}
        {!learners.some((l) => l.learner_id === currentLearnerId) && (
          <option value={currentLearnerId}>
            {currentLearnerId} (custom)
          </option>
        )}
        {learners.map((l) => (
          <option key={l.learner_id} value={l.learner_id}>
            {l.name} · {l.enrolment_status}
          </option>
        ))}
      </select>
      <ChevronDown
        size={14}
        strokeWidth={1.75}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-text-subtle"
      />
    </label>
  );
}
