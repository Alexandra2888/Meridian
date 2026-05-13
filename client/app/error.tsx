"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useEffect } from "react";

/**
 * Route-segment error boundary — Next.js catches uncaught errors thrown
 * during render (or in client effects) inside this segment and mounts this
 * component in place of the page. `reset` retries the segment.
 */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error in the browser console so devs can drill in; the
    // digest is what links to server-side logs in production builds.
    console.error("Page error boundary caught:", error);
  }, [error]);

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md rounded-lg border border-state-error/40 bg-card p-6 text-center">
        <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-full bg-state-error/15 text-state-error">
          <AlertTriangle size={20} strokeWidth={1.75} />
        </div>
        <h2 className="text-foreground font-medium">Something went wrong</h2>
        <p className="mt-1.5 text-small text-text-muted">
          {error.message || "An unexpected error occurred while rendering this page."}
        </p>
        {error.digest ? (
          <p className="mt-2 font-mono text-micro text-text-subtle">
            ref: {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          className="mt-5 inline-flex items-center gap-2 rounded-md border border-border-subtle bg-surface-sunken px-3 py-1.5 text-small text-foreground hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orchestration/40"
        >
          <RotateCcw size={14} strokeWidth={1.75} />
          Try again
        </button>
      </div>
    </main>
  );
}
