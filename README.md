# NCERT Image–Caption Extraction Automation

**CaptionX** — extract every image from Grade 9 NCERT Science PDFs and map it
to its exact printed caption, with a web dashboard, a global FIFO queue, and
structured `results.json` / `results.csv` output.

[![CI](https://github.com/ItsPinion/captionx/actions/workflows/ci.yml/badge.svg)](https://github.com/ItsPinion/captionx/actions/workflows/ci.yml)

> Phase-by-phase plan: [plan.md](./plan.md) · Engine details:
> [extraction/README.md](./extraction/README.md) · Assessment demo script:
> [DEMO.md](./DEMO.md)

## 1. Problem statement

Build a web application that accepts one or more Grade 9 NCERT PDF documents
and automatically: extracts the native image objects; saves every relevant
image occurrence as an individual file; extracts text with positional
information; uses OCR **only** where native PDF text is insufficient;
identifies the likely caption for each image and maps image → caption with a
confidence score; falls back to a lightweight matcher for low-confidence
cases; marks `caption_not_found` instead of inventing a caption when nothing
reliable exists; produces `results.json`, `results.csv` and the image files;
and presents everything in a single-page dashboard with PDF-upload and
PDF-URL modes, multiple PDFs per submission, one-PDF-at-a-time global
processing with FIFO queueing, per-image selection and select-all/JSON/CSV
downloads.

Quality bar: ≈95% correct image→caption mappings on the chosen chapters,
**personally verified** — and a wrong mapping is treated as worse than no
mapping.

## 2. Solution overview

```text
PyMuPDF  — embedded raster extraction + text blocks with exact geometry
+ PaddleOCR (PP-OCRv5, vendored models) — only for pages without usable native text
+ spatial/textual matching — candidate windows → weighted features → thresholds
```

Native-first: each page is checked (`needs_ocr`) and OCR runs only when the
native text layer is unusable. Captions are matched by geometry and wording
against the image's own column, never by page position alone. Everything runs
locally on CPU — no paid APIs, no network calls at extraction time.

## 3. Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                 Next.js dashboard  (localhost:3000)          │
│   upload / URL tabs · live queue view · results table ·      │
│   per-image selection · JSON/CSV/images.zip downloads        │
└──────────────▲───────────────────────────────────────────────┘
               │ Hono RPC client via same-origin /api/* rewrite
┌──────────────┴───────────────────────────────────────────────┐
│                    Hono API  (localhost:4000)                │
│   POST /jobs/upload · POST /jobs/url → validate (magic       │
│   bytes, size cap) → store under data/uploads/ → queue       │
│   GET  /jobs · /jobs/:id/result|json|csv|image|images.zip    │
│   ┌────────────────────────────────────────────────────────┐ │
│   │  Global FIFO worker — ONE PDF at a time, oldest first, │ │
│   │  restart-safe (interrupted → queued on boot)           │ │
│   └───────────┬────────────────────────────────────────────┘ │
└───────────────┼──────────────────────────────────────────────┘
                │ spawn extraction/main.py --job-id --input --output
┌───────────────▼──────────────────────────────────────────────┐
│                Python extraction engine (venv)               │
│  per page: raster extraction → needs_ocr? ── no ─▶ native    │
│     text blocks (exact text, exact bboxes)                   │
│        │ yes                                                 │
│     PaddleOCR PP-OCRv5 (vendored, init once, 200 dpi)        │
│  fused-caption split → candidates below/above the image      │
│     → 6-feature weighted score → dual thresholds             │
│     → fallback pass → series passthrough → caption_not_found │
│  output: results.json · results.csv · images/*.png           │
└──────────────────────────────────────────────────────────────┘
```

All state is filesystem: `data/uploads/`, `data/jobs/<id>/job.json`
(atomic writes), `data/results/<id>/` — the API serves authoritative files;
the frontend never reconstructs results.

## 4. Why this architecture

- **Local / free.** PyMuPDF (AGPL) + PaddleOCR (Apache-2.0) on CPU; OCR models are
  vendored into the repo (`extraction/models/official_models/`), so nothing
  is downloaded at run time and no paid API is involved anywhere.
- **Lightweight.** Streaming page-by-page pipeline (peak memory ≈ one page's
  pixels), clip-only renders, OCR init once per job: all three pinned
  chapters process in ≈2.5 s on a modest machine.
- **NCERT optimization.** Candidate windows, weights, footer/header bands,
  split-caption re-join and fused-block splitting are all tuned against
  measured NCERT layouts — and validated against *unseen* chapters and
  languages to make sure the tuning is principled, not overfit.
- **Modular pipeline.** Six stages (input → pdf_parse → image_extraction →
  ocr → matching → output), each with its own config dataclass and failure
  reporting (`status.json`); the OCR engine can be swapped without touching
  the matcher.
- **Honesty-first contract.** `caption_not_found` is a first-class outcome —
  the system is built to abstain rather than guess (§2.4 of the plan).

## 5. Setup

**Bun (dashboard + API):**

```bash
bun install         # install all workspace dependencies
```

**Python (extraction engine):**

```bash
cd extraction
./setup.sh          # creates .venv, installs pinned requirements
                    # (incl. the headless-OpenCV fix), downloads the
                    # sample NCERT fixture chapters, runs the test suite
```

`setup.sh` picks a paddle-compatible Python automatically (paddlepaddle's
pinned wheels cover CPython 3.9–3.13). Newer-only systems (e.g. Python 3.14
distros whose apt has no 3.11 package either) are handled two ways: install
[uv](https://docs.astral.sh/uv/) and re-run — it fetches a standalone 3.11
without sudo — or use any other 3.9–3.13 interpreter (deadsnakes PPA on
Ubuntu LTS, brew, pyenv). OCR models are already vendored under
`extraction/models/official_models/` (no network needed for inference).

## 6. Running the system

```bash
bun run dev         # API on http://localhost:4000 + dashboard on http://localhost:3000
```

1. Open **http://localhost:3000** — the header shows a live API health check.
2. Drag & drop PDFs (one job per PDF) or switch to the **PDF URLs** tab and
   paste direct links; the API downloads and validates them.
3. Watch the **queue view** (processing / waiting / completed / failed) —
   polling stops automatically when everything is done.
4. **Inspect results**: image preview dialog, page, exact caption,
   confidence, status and method badges per row.
5. **Download**: per-image, selected-images ZIP, or the backend's
   `results.json` / `results.csv` / `images.zip`.

CLI equivalent (used by the worker internally):

```bash
cd extraction && .venv/bin/python main.py --job-id <id> --input <pdf> --output <dir>
```

```bash
# API without the dashboard
curl -F "files=@chapter.pdf" http://localhost:4000/jobs/upload
curl -X POST http://localhost:4000/jobs/url -H 'content-type: application/json' \
     -d '{"urls":["https://example.org/chapter.pdf"]}'
curl http://localhost:4000/jobs            # queue view (FIFO)
```

## 7. Output

Per job, in `data/results/<job-id>/`:

```text
results.json   {"document": {filename, source, page_count},
                "images": [{image, page, caption, confidence, status, method}]}
results.csv    image,page,caption,confidence,status,method
images/        page_NN_image_NN.png   (one file per image occurrence)
```

`status` is `matched` or `caption_not_found`; `method` is `native_text`,
`ocr` (strict pass), `fallback` (broadened pass / series passthrough), or
`no_reliable_candidate`. The same bytes are served at
`/jobs/:id/json|csv|images.zip|image/:file` and downloaded by the dashboard.

## 8. Matching method

Per image occurrence, on the same page only:

1. **Candidates** — text blocks **below** the image (≤100 pt gap; secondary
   window above ≤60 pt), same column, after base filters: page numbers,
   running headers/footers, oversized body blocks, figure-internal labels.
   Captions fused into other blocks are split at the caption-head line
   ("by sublimation ⌶ Fig. 2.6: …"), and captions broken across consecutive
   blocks are re-joined (gap ≤3.5 pt + x-overlap).
2. **Features** (§14) → **weighted score** (§15):
   `0.40·proximity + 0.20·alignment + 0.15·keyword + 0.10·numbering +
   0.10·text-shape + 0.05·layout`, with standalone sub-labels (`(a)`, `(ii)`)
   demoted ×0.55.
3. **Acceptance** (§16) — score ≥0.45 **and** confidence ≥0.55; a
   zero-evidence escape at ≥0.78 covers captions without figure keywords;
   geometry-only winners cap at 0.75, so placement alone never matches.
4. **Fallback pass** (§17) for the unresolved — broadened windows
   (160 pt below / 80 pt above) with text-dominant weights
   (keyword+numbering = 0.45), thresholds 0.50/0.50, escape disabled.
5. **Series passthrough** — stacked multi-raster figures (one caption for
   parts a/b/c): a figure directly above (≤80 pt, shared column) a series
   winner inherits its caption at ×0.85 confidence.
6. Anything left is **`caption_not_found`** — never a guess.

Caption text is preserved exactly as printed (no normalization); only
scoring sees a normalized copy.

## 9. Limitations

- **Raster scope** (plan §2.3): only embedded raster images are extracted —
  pure vector-drawn figures (e.g. most of ch08 *Motion*) have no embedded
  object to extract or match.
- Pages with no native text rely on OCR; recognition errors can lower
  matching quality. Legacy-encoded non-Unicode text (e.g. Hindi-medium
  editions) is unusable — the system correctly abstains (`caption_not_found`)
  rather than matching garbage.
- Unusual layouts can produce ambiguous matches; the tuner is NCERT-layout
  optimized, and windows are deliberately tight to protect precision.
- Only one PDF is processed at a time (global FIFO) — by design.
- Scanned/image-only PDFs without embedded raster objects yield no images at
  all (nothing is embedded to extract).

## 10. Accuracy

Only personally verified results are reported (full evidence in
[extraction/VERIFICATION.md](./extraction/VERIFICATION.md) and
[extraction/EDGE_CASES.md](./extraction/EDGE_CASES.md)):

| Set | Result |
|---|---|
| **Assessment chapters** — ch05 *Cell* + ch12 *Sound* | **13/13 = 100%** of captioned embedded images matched (6/6 + 7/7), **0 false mappings** — every row visually verified |
| ch01 *Matter* (support) | 11/11 matched, visually verified |
| Exact pins | ch01 14 images/11 matched/3 not-found · ch05 8/6/2 · ch12 9/7/2 — all 7 `caption_not_found` inspected and correct (portraits, Exercises art) |
| **Unseen generalization set** (7 PDFs never used for tuning: NCERT ch02/ch08/ch11, Hindi-medium ch05, 3 degenerate pdf.js test PDFs) | 28 images extracted, 15 matched — **every match visually adjudicated true, 0 false mappings**; all 12 non-matches correct abstentions (Exercises art, vector-scope figures, portraits, non-Unicode text) |

The ≥95% target is met with margin on the verified denominator (captioned
embedded raster images in the pinned chapters).

## Testing & CI

All suites run locally the same way CI runs them (`.github/workflows/ci.yml`,
badge above — three jobs on every push/PR):

| Suite | Phases | Command |
|---|---|---|
| Typecheck (all workspaces) | 1–29 | `bun run typecheck` |
| API tests — store, FIFO worker, §24 recovery, routes, cleanup, stub engine | 17–21, 36 | `bun test apps/api` |
| Dashboard tests — queue rendering, tabs, selection, ZIP builder, URL building | 22–29 | `cd apps/web && bun test` |
| Lint + production build | 21–29 | `bun run lint && bun run build` |
| Extraction battery (251 tests) | 2–16, 32–35 | `cd extraction && .venv/bin/python -m pytest tests -q` |
| §47 CLI milestone + chapter pins | 12–16 | see [extraction/README.md](./extraction/README.md) |

CI also fetches the pinned-edition NCERT fixtures and runs a §47 CLI smoke on
ch05 asserting the exact 8 images / 6 matched / 2 `caption_not_found` pin.

Current totals: **251 extraction + 24 API + 15 web tests**, all green.

## Structure

```text
apps/web          Next.js dashboard (upload, queue, results, downloads)
apps/api          Hono API + global FIFO worker + Python process launcher
packages/shared   Shared TypeScript domain types & constants
extraction/       Python extraction engine (PyMuPDF + PaddleOCR + matching)
data/             uploads / jobs / results — runtime only, gitignored
```

## Phase map

| Phases | Delivered | Evidence |
|---|---|---|
| 1 | Monorepo: dashboard · API · shared types · engine skeleton | this repo |
| 2–16 | Extraction engine: rasters + text, OCR gate (vendored PP-OCRv5), candidates → features → score → confidence → fallback → series, JSON/CSV/PNG output, CLI | [extraction/README.md](./extraction/README.md) |
| 17–20 | Job infrastructure: global FIFO worker, §24 restart recovery, upload/URL validation, result endpoints | `apps/api` |
| 21–29 | Dashboard: input tabs, live queue, results table, selection + ZIP, backend-backed downloads, Hono RPC | `apps/web` |
| 30–31 | Error handling: API error contract, 6-stage `status.json`, friendly UI copy | `apps/api`, `apps/web` |
| 32–33 | Split-caption re-join + mistake table; manual verification **13/13 = 100%** | [VERIFICATION.md](./extraction/VERIFICATION.md) |
| 34 | Edge-case matrix — 12 deliberate cases with evidence | [EDGE_CASES.md](./extraction/EDGE_CASES.md) |
| 35 | Performance: streaming pipeline, §41 checklist, ≈2.5 s / 3 chapters | [extraction/README.md](./extraction/README.md) |
| 36 | Storage rules + boot-time `.tmp` sweep | `apps/api/src/services/cleanup.ts` |
| 37 | This README | — |
| *(bonus)* | Unseen-PDF generalization probe (7 PDFs) → fused-caption split fix, 0 false mappings | §10 Accuracy above |
