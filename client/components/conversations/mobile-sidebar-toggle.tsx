"use client";

import { PanelLeft } from "lucide-react";

import { useSidebarStore } from "@/lib/sidebar-store";
import { cn } from "@/lib/utils";

interface MobileSidebarToggleProps {
  className?: string;
}

/**
 * Hamburger trigger shown in the header on mobile only. Opens the sidebar
 * drawer; the sidebar itself owns the closing affordances (backdrop tap +
 * its own close button).
 */
export function MobileSidebarToggle({ className }: MobileSidebarToggleProps) {
  const open = useSidebarStore((s) => s.open);
  return (
    <button
      type="button"
      onClick={open}
      aria-label="Open conversations"
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-md text-text-muted",
        "hover:bg-card hover:text-foreground transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orchestration/40",
        "md:hidden",
        className,
      )}
    >
      <PanelLeft size={18} strokeWidth={1.75} />
    </button>
  );
}
