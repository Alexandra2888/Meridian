import { Clock, Coins } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MessageFinalMetadata } from "@/lib/types";

interface CostBadgeProps {
  final: MessageFinalMetadata | undefined;
  className?: string;
}

/**
 * Latency + cost pill that appears on completed assistant messages. The
 * RFC frames this as "production thinking made visible" — a small token of
 * the cost-tracking story without dedicating UI space to it.
 */
export function CostBadge({ final, className }: CostBadgeProps) {
  if (!final) return null;

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <Badge
        variant="outline"
        className="gap-1 px-1.5 py-0 font-mono text-micro text-text-muted tabular-nums"
      >
        <Clock size={10} strokeWidth={1.75} />
        {formatLatency(final.totalLatencyMs)}
      </Badge>
      <Badge
        variant="outline"
        className="gap-1 px-1.5 py-0 font-mono text-micro text-text-muted tabular-nums"
      >
        <Coins size={10} strokeWidth={1.75} />
        {formatCost(final.costUsd)}
      </Badge>
    </div>
  );
}

function formatLatency(ms: number) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatCost(usd: number) {
  if (usd < 0.01) return `$${(usd * 1000).toFixed(2)}m`;
  return `$${usd.toFixed(3)}`;
}
