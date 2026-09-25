# CaptionX — NCERT Image–Caption Extraction Automation

[![CI](https://github.com/ItsPinion/captionx/actions/workflows/ci.yml/badge.svg)](https://github.com/ItsPinion/captionx/actions/workflows/ci.yml)

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

**Phases 2–16 — Extraction engine** ✅ (see [extraction/README.md](./extraction/README.md))

**Phases 17–20 — Job infrastructure** ✅

- Global FIFO worker (§23): one PDF at a time across all users, oldest
  `createdAt` first, `queued → processing → completed|failed`.
- Restart recovery (§24): on boot, interrupted `processing` jobs return to
  `queued` and resume; completed/failed jobs are never touched.
- URL input flow (§19): Hono validates, downloads (30 s timeout, 100 MB cap,
  `%PDF-` sniff), stores under `data/uploads/`, then queues — URLs are never
  passed to Python.
- Upload flow (§26): multipart PDFs, `.pdf` extension + `%PDF-` magic + size
  cap, one independent job per PDF.
- Job store: one `job.json` per job under `data/jobs/<id>/`, atomic writes.
- Result surface (§21/§28/§29): `GET /jobs/:id/result|json|csv|image/:f|
  images.zip` — the backend serves authoritative results; ZIP is a
  dependency-free store-method build (PNGs are already compressed).

**Phases 21–29 — Dashboard** ✅

- Single-page dashboard at `apps/web` (§24): header with live API health,
  input-mode tabs (**PDF Files** drag & drop / **PDF URLs** rows), queue
  visualization (§25: processing / waiting / completed / failed), and the
  results view.
- TanStack Query integration (§23): mutations for upload + URL submit;
  status polling at 1.5 s only while jobs are queued/processing — stopped
  once everything is completed/failed.
- Results table (§26): image preview (thumbnail → full dialog), page,
  exact caption, confidence, status badge, method badge.
- Image selection (§27/§28): per-row checkboxes, select all (includes
  `caption_not_found` — the image was still validly extracted), individual
  downloads, and "download selected" zipped client-side with the same
  dependency-free store-method ZIP builder.
- JSON / CSV / images.zip buttons (§29) map straight to the backend's
  generated files — the frontend never reconstructs results.
- All browser calls go through the same-origin Next.js rewrite
  (`/api/* → :4000/*`) using the Hono RPC client (`AppType`).

## Quick start

```bash
bun install   # install all workspace dependencies
bun run dev   # API on http://localhost:4000 + dashboard on http://localhost:3000
```

Open http://localhost:3000 — the dashboard performs a live API health check
through the Hono RPC client (proxied by a Next.js rewrite: `/api/* → :4000/*`),
so the browser never needs direct access to the API port.

## API

```bash
# upload PDFs (one job each)
curl -F "files=@chapter.pdf" http://localhost:4000/jobs/upload

# or submit URLs — Hono downloads; Python never touches the network
curl -X POST http://localhost:4000/jobs/url \
     -H 'content-type: application/json' \
     -d '{"urls":["https://example.org/chapter.pdf"]}'

curl http://localhost:4000/jobs            # queue view (FIFO)
curl http://localhost:4000/jobs/<id>       # one job
curl http://localhost:4000/jobs/<id>/result        # ExtractionResult JSON
curl -o results.json http://localhost:4000/jobs/<id>/json
curl -o results.csv  http://localhost:4000/jobs/<id>/csv
curl -o image.png    "http://localhost:4000/jobs/<id>/image/<file>"
curl -o images.zip   http://localhost:4000/jobs/<id>/images.zip
```

Jobs live in `data/jobs/<id>/job.json`; engine output in
`data/results/<id>/{results.json,results.csv,images/}`. Env overrides:
`CAPTIONX_UPLOADS_DIR`, `CAPTIONX_JOBS_DIR`, `CAPTIONX_RESULTS_DIR`,
`CAPTIONX_PYTHON_BIN`, `CAPTIONX_MAIN_SCRIPT`, `API_PORT`.

## Testing & CI

All suites run locally the same way CI runs them (`.github/workflows/ci.yml`,
badge above — three jobs on every push/PR):

| Suite | Phases | Command |
|---|---|---|
| Typecheck (all workspaces) | 1–29 | `bun run typecheck` |
| API tests — store, FIFO worker, §24 recovery, routes, stub engine | 17–21 | `bun test apps/api` |
| Dashboard tests — queue rendering, tabs, selection, ZIP builder, URL building | 22–29 | `cd apps/web && bun test` |
| Lint + production build | 21–29 | `bun run lint && bun run build` |
| Extraction battery (238 tests) | 2–16 | `cd extraction && .venv/bin/python -m pytest tests -q` |
| §47 CLI milestone + chapter pins | 12–16 | see [extraction/README.md](./extraction/README.md) |

CI also fetches the pinned-edition NCERT fixtures and runs a §47 CLI smoke on
ch05 asserting the exact 8 images / 6 matched / 2 `caption_not_found` pin.

## Structure

```text
apps/web          Next.js dashboard (upload, queue, results, downloads)
apps/api          Hono API + global FIFO worker + Python process launcher
packages/shared   Shared TypeScript domain types & constants
extraction/       Python extraction engine (PyMuPDF + PaddleOCR + matching)
data/             uploads / jobs / results — runtime only, gitignored
```
