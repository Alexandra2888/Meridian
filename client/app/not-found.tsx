import { ArrowLeft, Compass } from "lucide-react";
import Link from "next/link";

/**
 * 404 fallback — Next.js routes any `notFound()` call or unknown URL here.
 * Visually mirrors `app/error.tsx` so the failure modes feel like one family.
 */
export default function NotFound() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md rounded-lg border border-border-subtle bg-card p-6 text-center">
        <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-full bg-accent-orchestration-soft text-accent-orchestration">
          <Compass size={20} strokeWidth={1.75} />
        </div>
        <p className="font-mono text-micro uppercase tracking-wider text-text-subtle">
          404
        </p>
        <h2 className="mt-1 text-foreground font-medium">Page not found</h2>
        <p className="mt-1.5 text-small text-text-muted">
          The URL you followed doesn&apos;t match any Meridian route. It may
          have been moved, or the link was mistyped.
        </p>
        <Link
          href="/"
          className="mt-5 inline-flex items-center gap-2 rounded-md border border-border-subtle bg-surface-sunken px-3 py-1.5 text-small text-foreground hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-orchestration/40"
        >
          <ArrowLeft size={14} strokeWidth={1.75} />
          Back to chat
        </Link>
      </div>
    </main>
  );
}
