# CaptionX — Final Plan (consolidated)

> This file is the **final plan** as pasted by the user (supersedes all
> earlier plan revisions; the previous long-form draft is preserved in git
> history). Status markers show what is DONE as of 2026-09-25.

## 1. Product

One-place PDF → images + exact captions. Upload a PDF (or give a URL), get
every legitimate figure raster with its printed caption text — exact
characters, never paraphrased — as `results.json`, `captions.csv`, and
`images/`. A web UI (upload / URL queue, live worker status, results table,
CSV + ZIP download) and a CLI share the same pipeline.

Non-negotiables (standing rules):
- FIFO single-PDF worker: one job at a time, oldest first (§23).
- Interrupted jobs re-enter the queue as `queued` on boot (§24).
- Never deduplicate repeated occurrences; each legitimate occurrence is its
  own output row (FIFO/§2.3 scope).
- `caption_not_found` is always preferred over a forced/wrong mapping — a
  false mapping is worse than not finding (§33/§41).
- Caption fidelity §13.4: text is emitted exactly as printed (whitespace
  normalization only for comparison, never for output).
- Raster scope §2.3: embedded raster figures are the extraction target;
  decorative/repeated art is excluded; vector-only figures are out of scope
  (a 0-image vector chapter is a correct result, not a failure).

## 2. Architecture

- `apps/api` — Hono + Node RPC-style API: `/jobs/upload`, `/jobs/url`,
  `/jobs`, `/result|json|csv|images.zip|image/:file`.
- `apps/web` — React + Vite + Tailwind + Radix: 15-chapter NCERT sample
  menu, upload/URL queue, live status, results, accuracy display.
- `packages/shared` — TS contract types (`ImageResult`, `ExtractionResult`).
- `extraction/` — Python 3.11 venv pipeline:
  1. **Extract** (PyMuPDF): page rasters via `get_page_images`, inline/xref
     handling, cluster → classify (standalone/composite/decoration), pixel
     or region-render fallback (§2.3), filename `page_NN_image_MM.png`.
  2. **Layout** (PP-DocLayout-S, final plan §11): 150 dpi page inference,
     `image` + `figure_title` regions → caption-region tagging, OCR
     targeting, scan-page handling, coverage audit. Evidence, not a gate.
  3. **OCR** (PaddleOCR PP-OCRv5 mobile): only when the page lacks a native
     text layer, preferentially on layout caption crops (§12).
  4. **Match**: candidate windows (§13.2 same-page below→above), §13.3
     filters (internal labels, headings), §13.4 exact text, keyword/
     numbering/text-shape features (§14), six-bucket scorer with the
     layout bucket (§15), strict pass → fallback pass, confidence ≥ floor
     else `caption_not_found` (§16–§18). Split captions re-joined before
     matching (§38).
  5. **Output**: `results.json` (additive `layout` evidence per image),
     `captions.csv`, `images/`.

## 3. Performance rules (§41)

- Layout ≈ 0.33 s/page, OCR only on demand, whole 3-chapter benchmark
  ≤ ~15 s. No model download at runtime: weights vendored under
  `extraction/models/official_models/` (+ `extraction/fetch_models.sh` to
  restore them byte-exact).

## 4. Assessment Execution Contract (§40 / §49A)

- Two frozen chapters: Science Grade 9 ch05 "The Fundamental Unit of Life"
  and ch12 "Sound" (pinned editions, SHA-256 in
  `assessment/selected_chapters.md`). Never silently switch them; any
  replacement ⇒ re-run accuracy from scratch.
- Artifacts: `assessment/selected_chapters.md`, `assessment/ground_truth.csv`
  (one row per legitimate occurrence; captioned + `source_has_no_caption`),
  `assessment/errors.md`, `assessment/accuracy.md` (§53 table).
- Accuracy = correct mappings ÷ captioned occurrences, per chapter;
  **combined = pooled denominator** (13 captioned occurrences), never an
  average of the two percentages. ≥95% ⇒ ≥ ceil(0.95 × 13) = 13 correct.
  Never claim ≥95% without manual verification.
- Calculator: `assessment/calculate_accuracy.py` (unit-tested).

## 5. §53 Result (verified 2026-09-25)

| Metric | ch05 Cell | ch12 Sound | Combined |
|---|---|---|---|
| Expected legitimate image occurrences | 8 | 9 | 17 |
| Expected captioned occurrences | 6 | 7 | 13 |
| Correct image → caption mappings | 6 | 7 | 13 |
| Wrong captions / caption_not_found | 0 / 0 | 0 / 0 | 0 / 0 |
| Image extraction coverage | 100.00% | 100.00% | 100.00% |
| Image-caption accuracy | 100.00% | 100.00% | 100.00% |
| Min correct for 95% | 6 | 7 | 13 |

**Combined 13/13 ≥ 13 → target met.** Details: `assessment/accuracy.md`,
`assessment/errors.md`.

## 6. PP-DocLayout-S integration contract (final plan §11/§12)

The layout model must materially serve extraction/matching — not a
checkbox:
1. Caption-region evidence + matching authority: `figure_title` boxes tag
   OCR/native text blocks (§38-merged captions inherit the tag); the scorer
   floors the layout bucket at 0.95 for layout-tagged captions
   (`layout_caption` feature); tagged blocks are admitted beyond the tuned
   windows within sanity bounds; layout `figure` regions bound the
   below-window (soft barriers); near-tie winners are arbitrated toward
   DL-confirmed candidates (`_arbitrate`) — all soft-authority, so a
   missed detection degrades to pre-layout behavior (pinned outputs
   byte-identical).
2. OCR targeting: caption crops (6 pt pad) are OCR'd first on OCR-needed
   pages, whole-page OCR as fallback.
3. Scan handling: a raster covering ≥70% of the page is a page scan — the
   overlapping layout `image` region becomes the effective figure bbox and
   the figure-internal filter is disabled (makes image-only PDFs work
   end-to-end; proven by `tests/test_layout_ocr_e2e.py`).
4. Coverage audit: per-run progress line reports pages analyzed, figure
   regions, and figure regions without raster coverage (vector-scope
   proxy).
5. Output contract: additive per-image `layout` evidence in `results.json`
   (mirrored in `packages/shared/src/types.ts`).
Graceful degradation: if the vendored weights are missing, the pipeline
logs a warning and runs exactly as before (unit-tested via a fake engine).

## 7. Phase 39 — Submission checklist

- [x] Final-plan deltas implemented and verified (layout integration,
      accuracy calculator, assessment artifacts).
- [x] §53 table filled with verified numbers (above + `assessment/`).
- [x] README/DEMO document the stack (PyMuPDF + PP-DocLayout-S +
      PaddleOCR) and the measured accuracy.
- [x] Full battery green: extraction pytest, gated model tests, API/web
      tests, typecheck, benchmark pins.
- [x] CI green on the pushed branch.
- [x] Pushed branch + PR up to date (user squash-merges to main).
