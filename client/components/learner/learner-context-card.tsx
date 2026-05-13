import { GraduationCap, MapPin, Target } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EnrolmentStatus, LearnerProfile } from "@/lib/types";

interface LearnerContextCardProps {
  learner: LearnerProfile | null;
  loading?: boolean;
}

const STATUS_STYLES: Record<EnrolmentStatus, string> = {
  prospect: "bg-state-warning/15 text-state-warning border-state-warning/30",
  applied: "bg-accent-orchestration/15 text-accent-orchestration border-accent-orchestration/30",
  enrolled: "bg-state-success/15 text-state-success border-state-success/30",
  graduated: "bg-muted text-text-muted border-border-subtle",
};

/**
 * Top-of-page CRM card — RFC §5.2 element #2. Renders the learner profile the
 * orchestrator's `load_context` node looked up from HubSpot. Without it, the
 * CRM integration is invisible plumbing; with it, the orchestrator visibly
 * uses external state.
 */
export function LearnerContextCard({
  learner,
  loading,
}: LearnerContextCardProps) {
  if (loading || !learner) {
    return (
      <Card className="border-border-subtle bg-card p-4">
        <div className="flex items-center gap-3">
          <Skeleton className="size-9 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-2.5 w-48" />
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-border-subtle bg-card p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div
            aria-hidden
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent-orchestration-soft text-accent-orchestration font-mono text-small"
          >
            {learner.name
              .split(" ")
              .map((p) => p[0])
              .slice(0, 2)
              .join("")
              .toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium text-foreground">
              {learner.name}
            </p>
            <p className="truncate text-small text-text-muted font-mono">
              {learner.email}
            </p>
          </div>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "uppercase text-micro tracking-wider font-mono",
            STATUS_STYLES[learner.enrolment_status],
          )}
        >
          {learner.enrolment_status}
        </Badge>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field icon={GraduationCap} label="Program">
          {learner.program ?? <span className="text-text-subtle">—</span>}
        </Field>
        <Field icon={Target} label="Interests">
          {learner.interests.length > 0 ? (
            <span className="flex flex-wrap gap-1">
              {learner.interests.map((i) => (
                <span
                  key={i}
                  className="rounded-sm bg-muted px-1.5 py-0.5 text-micro text-text-muted"
                >
                  {i}
                </span>
              ))}
            </span>
          ) : (
            <span className="text-text-subtle">—</span>
          )}
        </Field>
        <Field icon={MapPin} label="Country">
          {learner.country ?? <span className="text-text-subtle">—</span>}
        </Field>
      </dl>
    </Card>
  );
}

function Field({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-micro uppercase tracking-wider font-mono text-text-subtle">
        <Icon size={12} strokeWidth={1.75} />
        {label}
      </dt>
      <dd className="mt-1 text-small text-foreground">{children}</dd>
    </div>
  );
}
