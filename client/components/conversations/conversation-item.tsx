"use client";

import { Check, MessageSquare, Pencil, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ConversationSummary } from "@/lib/types";

interface ConversationItemProps {
  conversation: ConversationSummary;
  learnerId: string;
  isActive: boolean;
  /** Called whenever this row triggers a route push — lets the parent close
   * the mobile drawer so the user lands on the conversation, not the menu. */
  onNavigate?: () => void;
}

type Mode = "view" | "editing" | "confirming-delete";

/**
 * One row in the conversation history sidebar. Click loads the conversation;
 * hover surfaces rename + delete affordances. Renaming is inline (Enter to
 * save, Escape to cancel); deletion uses an inline confirm row to keep the
 * action close to the row it operates on.
 */
export function ConversationItem({
  conversation,
  learnerId,
  isActive,
  onNavigate,
}: ConversationItemProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [mode, setMode] = useState<Mode>("view");
  // The draft is only meaningful while editing — when not editing the title
  // is read straight from `conversation.title`, so we seed the draft only on
  // the transition into editing mode.
  const [titleDraft, setTitleDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mode === "editing") inputRef.current?.select();
  }, [mode]);

  const startEditing = () => {
    setTitleDraft(conversation.title ?? "");
    setMode("editing");
  };

  const cancelEditing = () => {
    setMode("view");
    setTitleDraft("");
  };

  const displayTitle = conversation.title?.trim() || "Untitled conversation";

  const navigate = () => {
    if (mode !== "view" || busy) return;
    onNavigate?.();
    startTransition(() => {
      router.push(
        `/?learner=${encodeURIComponent(learnerId)}&conversation=${encodeURIComponent(
          conversation.id,
        )}`,
      );
    });
  };

  const saveTitle = async () => {
    const next = titleDraft.trim();
    if (!next || next === (conversation.title ?? "")) {
      cancelEditing();
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`/api/conversations/${conversation.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: next }),
      });
      if (!res.ok) throw new Error(`status ${res.status}`);
      setMode("view");
      setTitleDraft("");
      router.refresh();
    } catch {
      // Leave the input open so the user can retry; reset draft to current.
      setTitleDraft(conversation.title ?? "");
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      const res = await fetch(`/api/conversations/${conversation.id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) throw new Error(`status ${res.status}`);

      if (isActive) {
        // The active conversation just vanished — drop the query param so
        // the chat resets to a fresh thread.
        onNavigate?.();
        router.push(`/?learner=${encodeURIComponent(learnerId)}`);
      } else {
        router.refresh();
      }
    } catch {
      setMode("view");
    } finally {
      setBusy(false);
    }
  };

  if (mode === "confirming-delete") {
    return (
      <li className="group/item rounded-md border border-border-subtle bg-surface-sunken px-2.5 py-2">
        <p className="mb-1.5 text-micro text-text-muted">Delete this conversation?</p>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={confirmDelete}
            disabled={busy}
            className="rounded px-2 py-0.5 text-micro font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => setMode("view")}
            disabled={busy}
            className="rounded px-2 py-0.5 text-micro text-text-muted hover:bg-card disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </li>
    );
  }

  return (
    <li
      className={cn(
        "group/item flex items-center gap-1.5 rounded-md px-2 py-1.5 transition-colors",
        "hover:bg-surface-sunken",
        isActive && "bg-surface-sunken",
      )}
    >
      <MessageSquare
        size={14}
        strokeWidth={1.75}
        className="shrink-0 text-text-subtle"
      />

      {mode === "editing" ? (
        <Input
          ref={inputRef}
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void saveTitle();
            } else if (e.key === "Escape") {
              e.preventDefault();
              cancelEditing();
            }
          }}
          onBlur={() => void saveTitle()}
          disabled={busy}
          className="h-7 min-w-0 flex-1 px-1.5 text-small"
        />
      ) : (
        <button
          type="button"
          onClick={navigate}
          className={cn(
            "min-w-0 flex-1 truncate text-left text-small",
            isActive ? "text-foreground" : "text-text-muted hover:text-foreground",
          )}
          title={displayTitle}
        >
          {displayTitle}
        </button>
      )}

      <div
        className={cn(
          "flex shrink-0 items-center gap-0.5",
          mode === "editing"
            ? "opacity-100"
            : "opacity-0 group-hover/item:opacity-100 focus-within:opacity-100",
        )}
      >
        {mode === "editing" ? (
          <>
            <IconBtn
              ariaLabel="Save title"
              onClick={() => void saveTitle()}
              disabled={busy}
            >
              <Check size={12} strokeWidth={2} />
            </IconBtn>
            <IconBtn
              ariaLabel="Cancel rename"
              onClick={cancelEditing}
              disabled={busy}
            >
              <X size={12} strokeWidth={2} />
            </IconBtn>
          </>
        ) : (
          <>
            <IconBtn
              ariaLabel="Rename conversation"
              onClick={startEditing}
            >
              <Pencil size={12} strokeWidth={1.75} />
            </IconBtn>
            <IconBtn
              ariaLabel="Delete conversation"
              onClick={() => setMode("confirming-delete")}
              className="hover:text-destructive"
            >
              <Trash2 size={12} strokeWidth={1.75} />
            </IconBtn>
          </>
        )}
      </div>
    </li>
  );
}

function IconBtn({
  children,
  onClick,
  ariaLabel,
  disabled,
  className,
}: {
  children: React.ReactNode;
  onClick: () => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      disabled={disabled}
      className={cn(
        "rounded p-1 text-text-subtle hover:bg-card hover:text-foreground transition-colors disabled:opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}
