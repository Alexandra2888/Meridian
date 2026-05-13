"use client";

import { useState } from "react";

import { Composer } from "@/components/chat/composer";
import {
  MessageList,
  type ChatMessageView,
} from "@/components/chat/message-list";

interface ChatShellProps {
  /** Optional CRM card or other header content rendered above the message list. */
  header?: React.ReactNode;
  /** Empty-state slot when no messages have been sent yet. */
  emptyState?: React.ReactNode;
}

/**
 * Holds the local message state in v1 so the design renders standalone. When
 * the FastAPI `/chat` endpoint is wired (RFC §4.7), swap this for the AI SDK
 * `useChat` + an SSE event router that fans `delta` events here and
 * `status`/`final` events into `lib/trace-store.ts`.
 */
export function ChatShell({ header, emptyState }: ChatShellProps) {
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [pending, setPending] = useState(false);

  const handleSubmit = (text: string) => {
    const userId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: text },
    ]);
    // Backend not wired yet — surface a placeholder assistant turn so the
    // empty trace panel and streaming indicator are visible in v1.
    setPending(true);
    const assistantId = crypto.randomUUID();
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          turnId: assistantId,
          isStreaming: false,
        },
      ]);
      setPending(false);
    }, 200);
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {header ? (
        <div className="border-b border-border-subtle bg-surface-sunken/60">
          <div className="mx-auto w-full max-w-3xl px-4 py-4 md:px-6">
            {header}
          </div>
        </div>
      ) : null}

      <MessageList messages={messages} emptyState={emptyState} />

      <div className="border-t border-border-subtle bg-surface-sunken/60">
        <Composer onSubmit={handleSubmit} disabled={pending} />
      </div>
    </div>
  );
}
