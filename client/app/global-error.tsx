"use client";

import { useEffect } from "react";

/**
 * Last-resort error boundary — catches errors in the root layout itself,
 * where `app/error.tsx` cannot mount (it lives *inside* the layout). Must
 * render its own `<html>` + `<body>` since the layout has bailed out.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error boundary caught:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          fontFamily: "system-ui, -apple-system, sans-serif",
          backgroundColor: "#0a0a0a",
          color: "#f5f5f5",
        }}
      >
        <div
          style={{
            maxWidth: "28rem",
            width: "100%",
            textAlign: "center",
            border: "1px solid rgba(239, 68, 68, 0.4)",
            borderRadius: "0.5rem",
            padding: "1.5rem",
            backgroundColor: "#1a1a1a",
          }}
        >
          <h2 style={{ fontWeight: 500, fontSize: "1rem" }}>
            Meridian crashed while loading
          </h2>
          <p style={{ marginTop: "0.5rem", color: "#a0a0a0", fontSize: "0.875rem" }}>
            {error.message || "An unexpected error prevented the app from starting."}
          </p>
          {error.digest ? (
            <p
              style={{
                marginTop: "0.5rem",
                fontFamily: "monospace",
                fontSize: "0.75rem",
                color: "#737373",
              }}
            >
              ref: {error.digest}
            </p>
          ) : null}
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 0.75rem",
              borderRadius: "0.375rem",
              border: "1px solid #404040",
              backgroundColor: "#262626",
              color: "#f5f5f5",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
