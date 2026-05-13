"use client";

import { AgentTrace } from "@/components/chat/agent-trace";
import { CostBadge } from "@/components/chat/cost-badge";
import { useTraceStore } from "@/lib/trace-store";

export type MessageRole = "user" | "assistant";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
  messageId?: string;
  isStreaming?: boolean;
}

/**
 * One chat message. User and assistant variants differ in alignment, surface,
 * and the architectural extras (trace panel + cost badge are assistant-only).
 */
export function MessageBubble({
  role,
  content,
  messageId,
  isStreaming,
}: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85ch] rounded-xl rounded-br-sm border border-border-subtle bg-accent-orchestration-soft px-4 py-2.5 text-foreground">
          {content}
        </div>
      </div>
    );
  }

  return (
    <AssistantBubble
      content={content}
      messageId={messageId}
      isStreaming={isStreaming}
    />
  );
}

function AssistantBubble({
  content,
  messageId,
  isStreaming,
}: {
  content: string;
  messageId?: string;
  isStreaming?: boolean;
}) {
  const final = useTraceStore((s) =>
    messageId ? s.messages[messageId]?.final : undefined,
  );

  return (
    <div className="flex flex-col gap-2 max-w-[85ch]">
      <div className="rounded-xl rounded-bl-sm border border-border-subtle bg-card px-4 py-3 text-foreground">
        {content ? (
          <p className="whitespace-pre-wrap">
            {content}
            {isStreaming ? (
              <span className="ml-0.5 inline-block size-2 translate-y-[1px] pulse-dot rounded-full bg-accent-orchestration align-baseline" />
            ) : null}
          </p>
        ) : (
          <p className="text-text-muted italic text-small">
            Synthesizing response…
          </p>
        )}
      </div>
      {messageId ? (
        <div className="flex flex-wrap items-center gap-2 pl-1">
          <CostBadge final={final} />
        </div>
      ) : null}
      {messageId ? <AgentTrace messageId={messageId} /> : null}
    </div>
  );
}
