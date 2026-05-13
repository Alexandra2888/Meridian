"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { ConversationItem } from "@/components/conversations/conversation-item";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

interface ConversationSidebarProps {
  learnerId: string;
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
}

/**
 * Left rail listing this learner's prior conversations. "New conversation"
 * drops the `conversation` query param to reset the chat to a fresh thread.
 * Items handle their own rename / delete state.
 */
export function ConversationSidebar({
  learnerId,
  conversations,
  activeConversationId,
}: ConversationSidebarProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const startNew = () => {
    startTransition(() => {
      router.push(`/?learner=${encodeURIComponent(learnerId)}`);
    });
  };

  const isOnNew = !activeConversationId;

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border-subtle bg-surface-sunken/40">
      <div className="border-b border-border-subtle px-3 py-3">
        <button
          type="button"
          onClick={startNew}
          disabled={isPending}
          className={cn(
            "flex w-full items-center gap-2 rounded-md border border-border-subtle bg-card px-2.5 py-1.5",
            "text-small text-foreground transition-colors hover:bg-surface-sunken",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orchestration/40",
            isPending && "opacity-60",
            isOnNew && "border-accent-orchestration/40",
          )}
        >
          <Plus size={14} strokeWidth={1.75} className="text-text-subtle" />
          <span className="flex-1 text-left">New conversation</span>
        </button>
      </div>

      <div className="px-3 py-2">
        <p className="font-mono text-micro uppercase tracking-wider text-text-subtle">
          history
        </p>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 ? (
          <p className="px-2 py-1.5 text-micro text-text-subtle">
            No conversations yet. Ask Meridian something to get started.
          </p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {conversations.map((c) => (
              <ConversationItem
                key={c.id}
                conversation={c}
                learnerId={learnerId}
                isActive={c.id === activeConversationId}
              />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
