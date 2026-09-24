# CaptionX — NCERT Image–Caption Extraction Automation

Automated extraction of images and their captions from Grade 9 NCERT PDFs,
with a web dashboard, a global FIFO job queue, and structured JSON/CSV output.

> See [plan.md](./plan.md) for the full phase-by-phase implementation plan.

## Status

**Phase 1 — Monorepo bootstrap** ✅

- Turborepo + Bun workspaces
- `apps/web` — Next.js + React + TypeScript + Tailwind CSS v4 + shadcn/ui
- `apps/api` — Hono on Bun (health endpoint, Hono RPC contract)
- `packages/shared` — shared domain types & constants
- `extraction/` — Python extraction engine (Phases 2+)

## Quick start

```bash
bun install   # install all workspace dependencies
bun run dev   # API on http://localhost:4000 + dashboard on http://localhost:3000
```

Open http://localhost:3000 — the dashboard performs a live API health check
through the Hono RPC client (proxied by a Next.js rewrite: `/api/* → :4000/*`),
so the browser never needs direct access to the API port.

## Structure

```text
apps/web          Next.js dashboard (upload, queue, results, downloads)
apps/api          Hono API + global FIFO worker + Python process launcher
packages/shared   Shared TypeScript domain types & constants
extraction/       Python extraction engine (PyMuPDF + PaddleOCR + matching)
data/             uploads / jobs / results — runtime only, gitignored
```
