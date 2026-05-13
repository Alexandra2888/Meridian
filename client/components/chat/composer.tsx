"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ComposerProps {
  onSubmit: (text: string) => void | Promise<void>;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * The chat input. Auto-grows on multi-line, submits on Enter, newline on
 * Shift+Enter. Visually rounded more than the rest of the surfaces for the
 * "tactile feel" called out in RFC §5.5.
 */
export function Composer({
  onSubmit,
  disabled,
  placeholder = "Ask anything about programs, careers, or your enrolment…",
}: ComposerProps) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    setValue("");
    void onSubmit(trimmed);
  };

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      onSubmit={handleFormSubmit}
      className={cn(
        "mx-auto w-full max-w-3xl px-4 pb-4 md:px-6 md:pb-6",
      )}
    >
      <div className="relative rounded-2xl border border-border-subtle bg-card focus-within:border-accent-orchestration/60 focus-within:ring-2 focus-within:ring-accent-orchestration/30 transition-colors">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder}
          disabled={disabled}
          className={cn(
            "block w-full resize-none rounded-2xl bg-transparent px-4 py-3 pr-12",
            "text-body placeholder:text-text-subtle",
            "outline-none disabled:opacity-50",
            "min-h-[48px] max-h-40 overflow-auto",
          )}
        />
        <Button
          type="submit"
          size="icon"
          disabled={disabled || !value.trim()}
          aria-label="Send"
          className="absolute right-2 bottom-2 size-8 rounded-full bg-accent-orchestration text-primary-foreground hover:bg-accent-orchestration/90 disabled:opacity-40"
        >
          <ArrowUp size={16} strokeWidth={1.75} />
        </Button>
      </div>
    </form>
  );
}
