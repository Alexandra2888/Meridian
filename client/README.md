# Meridian — Client

Next.js 16 (App Router) chat interface for the Meridian orchestrator. Renders the streamed assistant response, the live agent-trace panel, the cost/latency badges, and the per-learner conversation history sidebar.

The server-side is at [`../server/`](../server/) — this app talks to it through Next.js route handlers that proxy `localhost:8000` server-side, so the browser never sees the FastAPI URL (no CORS, no leaked host).

## Stack

| Layer       | Choice                                          |
| ----------- | ----------------------------------------------- |
| Framework   | Next.js 16 (App Router) + React 19              |
| Styling     | Tailwind CSS v4 + shadcn/ui (Radix primitives)  |
| State       | Zustand (per-message trace store, sidebar drawer) |
| Streaming   | Native `fetch` + ReadableStream → SSE parser    |
| Icons       | lucide-react                                    |
| Validation  | zod (SSE event shapes)                          |
| Testing     | Playwright (e2e)                                |
| Pkg manager | pnpm                                            |

## Quick start

```bash
cd client
pnpm install
cp .env.example .env             # API_URL=http://localhost:8000 by default
pnpm dev                          # http://localhost:3000
```

The FastAPI server must be running on the URL in `API_URL` (see [`../server/README.md`](../server/README.md)). Without it, the proxy routes return 502 and the learner-picker stays empty.

## What the UI does

- **Learner picker** — top-right of the header; switches the active learner via `?learner=…`.
- **Sidebar** — per-learner conversation history. New / rename (pencil) / delete (trash). Mobile (`<md`) collapses to a slide-in drawer behind a hamburger.
- **Chat shell** — sends to `POST /api/chat`, parses SSE, streams assistant tokens. After the run completes, the orchestration trace + cost/latency badges render under the bubble.
- **Persistence** — message telemetry (agents invoked, latency, cost, per-step durations) is stored server-side; reloading a conversation hydrates the trace store so the trace panel survives a reload.
- **404 + error boundaries** — styled `app/not-found.tsx` plus `app/error.tsx` + `app/global-error.tsx` for uncaught render errors.

## Endpoints (route handlers)

| Method  | Path                          | Forwards to                                 |
| ------- | ----------------------------- | ------------------------------------------- |
| `POST`  | `/api/chat`                   | `POST {API_URL}/chat` — pipes SSE body      |
| `GET`   | `/api/conversations`          | `GET {API_URL}/conversations?learner_id=…` |
| `GET`   | `/api/conversations/[id]`     | `GET {API_URL}/conversations/{id}`          |
| `PATCH` | `/api/conversations/[id]`     | `PATCH {API_URL}/conversations/{id}`        |
| `DELETE`| `/api/conversations/[id]`     | `DELETE {API_URL}/conversations/{id}`       |

Every route is a thin proxy — auth/CORS/secrets would all attach here when added.

## Tests

```bash
pnpm test:e2e
```

Playwright happy-path suite (`tests/e2e/happy-path.spec.ts`):

1. Initial load — chrome, sidebar, learner card, canonical prompts visible.
2. Send a message → assistant response streams → trace + cost/latency badges visible → sidebar gains the new row.
3. Reload + click the conversation → persisted trace + badges re-hydrate.
4. Rename inline (pencil) → title persists across reload.
5. Delete via inline confirm → row removed.
6. New-conversation button → URL drops `?conversation=`, empty state returns.
7. Mobile drawer toggle (375x760 viewport).
8. `/does-not-exist` returns the styled 404.

Config: [`playwright.config.ts`](playwright.config.ts). The `webServer` array spawns FastAPI + Next.js with `reuseExistingServer: true`, so iterating against an already-running stack is friction-free.

## Layout

```
client/
├── app/
│   ├── page.tsx                       # Server component — fetches learner + conversations
│   ├── layout.tsx                     # Root layout + fonts
│   ├── error.tsx                      # Route-segment error boundary
│   ├── global-error.tsx               # Layout-level error boundary
│   ├── not-found.tsx                  # Styled 404
│   ├── globals.css                    # Tailwind v4 + design tokens
│   └── api/
│       ├── chat/route.ts              # SSE proxy
│       └── conversations/[id]/route.ts
├── components/
│   ├── chat/                          # ChatShell, MessageList, MessageBubble, Composer
│   ├── conversations/                 # Sidebar, item, mobile toggle
│   ├── learner/                       # Picker + context card
│   └── ui/                            # shadcn primitives (button, card, scroll-area, …)
├── lib/
│   ├── api.ts                         # fetchLearner / fetchConversations / fetchConversation
│   ├── stream.ts                      # SSE block parser + async iterator
│   ├── trace-store.ts                 # Zustand: per-message trace + final telemetry
│   ├── sidebar-store.ts               # Zustand: mobile drawer open/close
│   └── types.ts                       # Mirrors server Pydantic shapes
├── tests/e2e/                         # Playwright happy-path
└── playwright.config.ts
```
