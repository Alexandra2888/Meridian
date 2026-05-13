"use client";

import { useEffect, useRef } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";

import { MessageBubble, type MessageRole } from "@/components/chat/message-bubble";

export interface ChatMessageView {
  id: string;
  role: MessageRole;
  content: string;
  messageId?: string;
  isStreaming?: boolean;
}

interface MessageListProps {
  messages: ChatMessageView[];
  emptyState?: React.ReactNode;
}

export function MessageList({ messages, emptyState }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0 && emptyState) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        {emptyState}
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 px-4 md:px-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-6">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            messageId={m.messageId}
            isStreaming={m.isStreaming}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
