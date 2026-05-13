"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useTransition } from "react";

import { ConversationItem } from "@/components/conversations/conversation-item";
import { useSidebarStore } from "@/lib/sidebar-store";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

interface ConversationSidebarProps {
  learnerId: string;
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
}

/**
 * Left rail listing this learner's prior conversations.
 *
 * Layout strategy:
 *   - Desktop (md+): static, always visible at the page-wide flex row.
 *   - Mobile: slide-in drawer over a tap-to-dismiss backdrop. The hamburger
 *     `MobileSidebarToggle` (rendered in the header) opens it; the backdrop,
 *     close button, or Escape key closes it.
 *
 * "New conversation" drops the `conversation` query param so the chat resets
 * to a fresh thread. Items handle their own rename / delete state.
 */
export function ConversationSidebar({
  learnerId,
  conversations,
  activeConversationId,
}: ConversationSidebarProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const mobileOpen = useSidebarStore((s) => s.mobileOpen);
  const closeMobile = useSidebarStore((s) => s.close);

  // Esc closes the drawer on mobile.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMobile();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen, closeMobile]);

  // Prevent background scroll while the drawer is open on mobile.
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileOpen]);

  const startNew = () => {
    closeMobile();
    startTransition(() => {
      router.push(`/?learner=${encodeURIComponent(learnerId)}`);
    });
  };

  const isOnNew = !activeConversationId;

  return (
    <>
      {/* Backdrop — only rendered (and only clickable) when the drawer is open on mobile. */}
      <div
        aria-hidden
        onClick={closeMobile}
        className={cn(
          "fixed inset-0 z-30 bg-background/70 backdrop-blur-sm transition-opacity md:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={cn(
          // Desktop: static, in-flow.
          "md:static md:z-auto md:translate-x-0 md:transition-none",
          // Mobile: fixed drawer, slides from left.
          "fixed inset-y-0 left-0 z-40 transition-transform duration-200 ease-out",
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          // Shared sizing.
          "flex w-72 max-w-[85vw] shrink-0 flex-col border-r border-border-subtle bg-surface-sunken",
          // On desktop the sidebar shouldn't have its own opacity surface;
          // keep the subtle tone used previously.
          "md:bg-surface-sunken/40",
        )}
        // Hide from the a11y tree when the drawer is closed on mobile.
        aria-hidden={!mobileOpen ? undefined : false}
      >
        <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-3">
          <button
            type="button"
            onClick={startNew}
            disabled={isPending}
            className={cn(
              "flex flex-1 items-center gap-2 rounded-md border border-border-subtle bg-card px-2.5 py-1.5",
              "text-small text-foreground transition-colors hover:bg-surface-sunken",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orchestration/40",
              isPending && "opacity-60",
              isOnNew && "border-accent-orchestration/40",
            )}
          >
            <Plus size={14} strokeWidth={1.75} className="text-text-subtle" />
            <span className="flex-1 text-left">New conversation</span>
          </button>
          <button
            type="button"
            onClick={closeMobile}
            aria-label="Close conversations"
            className={cn(
              "inline-flex size-8 items-center justify-center rounded-md text-text-muted",
              "hover:bg-card hover:text-foreground transition-colors",
              "md:hidden",
            )}
          >
            <X size={16} strokeWidth={1.75} />
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
                  onNavigate={closeMobile}
                />
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
