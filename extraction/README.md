# Extraction Engine (Python)

PyMuPDF (native PDF images + text) + **PP-DocLayout-S** (document layout
regions) + PaddleOCR (fallback OCR) + spatial/textual caption matching →
`results.json` + `results.csv` + `images/`.

Part of the CaptionX assessment project — see [../plan.md](../plan.md) and
[../assessment/](../assessment) for the frozen-chapter ground truth and the
verified §53 accuracy table.

**Final-plan stack — all three models vendored, zero runtime downloads:**

| model | role | weights |
|---|---|---|
| PyMuPDF | raster + native-text extraction, geometry | (library) |
| PP-DocLayout-S | per-page layout regions: `image`/`figure_title` evidence → caption tagging, OCR targeting, scan handling, coverage audit (~0.33 s/page @150 dpi) | `models/official_models/PP-DocLayout-S/` |
| PaddleOCR PP-OCRv5 mobile | OCR for pages without a usable native text layer | `models/official_models/PP-OCRv5_mobile_{det,rec}/` |

`fetch_models.sh` restores any missing weights byte-exact; the pipeline
degrades gracefully (pre-layout behavior) if they are absent.

## Status

**Phase 2 — Python environment ✅ verified**

| acceptance (plan.md §8.5) | status |
|---|---|
| open PDF | ✅ 3 NCERT Class 9 Science chapters (13/11/16 pages) |
| render page | ✅ 200 dpi pixmap via PyMuPDF |
| OCR text | ✅ PaddleOCR 3.7 PP-OCRv5 mobile models, CPU |
| obtain bounding boxes | ✅ 87–94 boxes/page with conf 0.91–1.00 |

**Phase 3 — internal data model ✅ (72 tests)**

`src/models/schemas.py` defines the §9 structures — `Document`,
`ImageOccurrence` (never deduplicated), `TextRegion` (`native_pdf`/`ocr`),
`CaptionCandidate` (text + bbox + features + score), `MatchResult`
(`matched`/`caption_not_found`) — plus a frozen `BBox` geometry primitive in
PDF page points (top-left origin, y down) with the overlap/gap/alignment
relations the caption-matching features (Phases 7–9) build on. Enum string
values mirror the TypeScript `@captionx/shared` JSON contract; a contract test
guards them.

**Phase 4 — native PDF extraction ✅ (`src/pdf/`)**

- `text.py` — native text blocks via `get_text("blocks")`, exact text +
  bbox in points.
- `images.py` — image *placements* (`get_image_info`) → union-find clusters →
  classify:
  - `standalone` — single real-sized raster; original xref pixels extracted
    (downloadable exactly as embedded), stencil masks fall back to rendering;
  - `composite` — tile-collage / strip-assembly regions (the dominant figure
    encoding in these NCERT chapters — see “Known characteristics” below)
    rendered from the page at 2× zoom, capturing strips + vector art + labels;
  - `decoration` — page-edge furniture, dropped.
- `extractor.py` — one-pass page iteration (§41.5); occurrences numbered in
  reading order; figures keep their PNG bytes + model records together.

Result on the fixtures: **2,551 raw placements → 28 figure occurrences**
(13 + 8 + 7 across chapters 1/5/12), visually spot-checked (cell diagrams,
portraits, experiment setups all correct).

**Phase 11 — fallback matching ✅ (`src/matching/fallback.py`, `matcher.py`)**

Two-pass strategy per §17: strict (Phases 9–10) → unresolved images retry
with broadened windows (below 160 pt / above 260 pt) and keyword/numbering-
dominant weights (.25/.20 vs placement .45); evidence discipline unchanged —
zero figure words can never match (escape disabled), mid-text mentions never
match, same-page only. Plus `series_passthrough`: a winner's "(a)/(b)"
series caption is offered to an unmatched figure directly above it (≤80 pt,
same column) — the stacked-NCERT-experiment case. Final rule (§17/§2.4):
anything left is `caption_not_found`. `match_document()` returns the final
`MatchResult` per image; `scripts/debug_results.py` prints verdicts.

**Fixture outcome: 25/31 matched with 0 wrong captions; 6 `caption_not_found`
(all genuinely captionless: two scientist portraits, three Exercises corner
arts, one Group-Activity art).** The integration test pins these verdicts
(`tests/test_matcher_fixtures.py`) so Phase 32 tuning cannot regress them.

**Phases 9+10 — scoring & confidence ✅ (`src/matching/scorer.py`, `confidence.py`)**

Scorer (§15): plan-example weights — proximity .40, alignment .20, keyword
.15, numbering .10, text_shape .10, layout .05 (position+overlap blend) —
plus sub-label demotion (×0.55 for `(a)`/`(ii)`). Confidence (§16):
`0.7·top + 0.3·margin_ratio`; acceptance needs score ≥ 0.45, confidence
≥ 0.55, and the evidence gate: `Fig`-start (strong) accepts; zero figure
words never match on geometry (escape 0.78 > geometry-only max 0.75 — the
measured `H. R. Hertz`-under-portrait trap); mid-text figure *mentions*
("shown in Fig. 12.8 above") never match — they describe, not caption.

**Strict-matcher preview on fixtures: 20 accepted, all true Fig captions,
0 false accepts** (`scripts/debug_match_preview.py`). 11 rejects: 6 correctly
captionless figures → `caption_not_found`; 5 far/above/shared captions are
the Phase 11 fallback's targets (Fig 1.5 @95pt, Fig 1.10 shared, Fig 1.6
stacked pair, Fig 12.12 stacked pair, Fig 12.8 above @138pt).

**Phase 8 — matching features ✅ (`src/matching/features.py`)**

Eight named 0..1 features per `(image, candidate)` pair (§14): `proximity`
(gap/window decay, per-window), `alignment` (x-center delta, 150pt scale),
`overlap` (x-projection ratio vs narrower box), `position` (below 1.0 /
above 0.35), `keyword` (fig/figure/image/plate/diagram — start 1.0, mid-text
0.6, never required), `numbering` (chapter.number at start 1.0, bare `Fig. N`
0.7, mid-text reference 0.4), `sublabel` (standalone `(a)`/`(ii)` flagged for
demotion), `text_shape` (10–200 chars ideal, short floor 0.35, decay beyond;
line-count decay). §14.8 font signals deliberately skipped (documented).
Patterns mined from fixtures: all true captions are `Fig`-prefixed in four
formatting variants. `scripts/debug_features.py` shows features on real
candidates — true captions separate cleanly (`key=1 num=1` vs noise 0/0).

**Phase 7 — caption candidate detection ✅ (`src/matching/candidates.py`)**

Per figure (§13): same-page text blocks → base filters (page numbers, running
footer/header bands, oversized body blocks, figure-internal labels) → primary
below-window / secondary above-window → horizontal relatedness (own column) →
`CaptionCandidate`s, nearest-first, text preserved exactly.

All thresholds measured on the fixtures and documented in `CandidateConfig`:
captions below figures span gaps 4–95 pt (window 100 pt); a genuine
above-caption sits at 138 pt (window 150 pt); the running footer is a short
block in the band 110–70 pt from the page bottom (real captions stop ≥20 pt
below it); horizontal admission = ≥20% overlap or ≤40 pt slack (a real
indented `Fig. 1.4` has only 10.6 pt overlap).

**Fixture validation: candidate recall 20/20** — every `Fig.` caption block
whose figure was extracted lands in at least one candidate window. The only
3 uncaptured `Fig.` captions (1.8, 12.3, 12.5) belong to figures drawn purely
as vector art (zero raster placements — verified), which is the documented
Phase 4 boundary, not a candidate-stage failure. Noise candidates (Activity
boxes, sub-labels like `(a)`, body blocks) are expected — Phases 8–9 scoring
discriminates them.

`scripts/debug_candidates.py` prints per-figure candidates + the recall check.

**Phase 6 — PaddleOCR integration ✅ (`src/ocr/`)**

Engine validated end-to-end on a raster-only page and on a real fixture page
(94 regions, boxes correctly in PDF points, ~45 s init+page on CPU).
`apply_ocr_when_needed` (pipeline.py) completes the §11 output contract:
pages whose native text is unusable get OCR regions merged into
`PageExtraction.text_regions` (each tagged `source`), and the page records
`ocr_used=True` for later method labeling. Models are vendored
(`models/official_models/`) so the engine runs offline;
`setup.sh` bootstraps the whole environment in one command.

**Phase 5 — OCR decision ✅ (`src/ocr/decision.py`)**

Simple rule per §11 (“do not over-engineer”): a page gets OCR only when its
native text layer is unusable (`< 32` chars — scanned/image-only pages).
All fixture pages have rich native text (600–3,700 chars), so OCR stays a
true fallback. `src/ocr/engine.py` implements the §12 engine: PP-OCRv5
mobile models loaded once per process (singleton), pages rendered at 200 dpi
only when needed, OCR pixel boxes scaled back to PDF points, per-line
TextRegions with `source=ocr`, low-confidence lines dropped.

Run the tests:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
# slow, real-OCR integration test:
CAPTIONX_OCR_TEST=1 .venv/bin/python -m pytest tests/test_ocr_engine.py
```


## Setup

```bash
cd extraction && ./setup.sh
```

Creates `.venv`, installs the pinned stack (with the headless-OpenCV fix for
servers without libGL), fetches the sample fixtures, and runs the test suite.

### OCR models (PP-OCRv5 mobile) — vendored, offline-ready

The official PaddleX model packages (det 4.7 MB + rec 16.5 MB) are **vendored**
at `models/official_models/PP-OCRv5_mobile_{det,rec}/` and committed, so
inference needs **no network**. `src/ocr/model_cache.py` points
`PADDLE_PDX_CACHE_HOME` there (override by exporting your own) and skips the
model-hoster connectivity probe. If the directory is ever deleted, regenerate
it with `./fetch_models.sh`.

## Fixtures (sample chapters)

```bash
cd extraction/fixtures && ./download.sh   # not committed to git
```

Downloads Class 9 Science chapters 1, 5, 12 — official `ncert.nic.in` first,
GitHub mirror as fallback for sandboxed networks.

## Verify

```bash
.venv/bin/python scripts/verify_pymupdf.py                 # open PDFs, page counts
.venv/bin/python scripts/verify_ocr.py --page 1            # render → OCR → boxes
.venv/bin/python scripts/verify_ocr.py \
    --input fixtures/ncert_class9_science_ch05_cell.pdf --page 3
```

## Engine invocation — the §47 working milestone ✅ (Phases 13–16)

```bash
.venv/bin/python main.py \
    --job-id test-001 \
    --input fixtures/ncert_class9_science_ch05_cell.pdf \
    --output /tmp/results/sample
# → /tmp/results/sample/results.json · results.csv · images/*.png
```

Optional flags: `--status <status.json>` (§30 stage progress: input →
pdf_parse → image_extraction → ocr → matching → output, atomic writes,
`completed`/`failed` + stage + message), `--source upload|url`,
`--filename <display name>`. Exit 0 on success, 1 on pipeline failure
(status records the failing stage), 2 on bad arguments.

- Phase 12 (§18 no dedup): satisfied by construction — every occurrence is a
  separate record; pinned by tests.
- Phase 13 (§19): `results.json` — `document` + `images[]` with
  image/page/caption/confidence/status/method, exact caption text.
- Phase 14 (§20): `results.csv` — 6 columns, proper quoting (commas, quotes,
  embedded newlines preserved).
- Phase 15 (§21): CLI contract above — this is what the Hono API executes.
- Phase 16 (§22): layout `<output>/{results.json,results.csv,images/}`.

## Phase 32 — NCERT-specific tuning ✅

Assessment chapters: **ch05 (Cell)** and **ch12 (Sound)** — every extracted
image and mapping manually inspected, plus ch01 for completeness
(`scripts/tuning_report.py` prints the per-figure verdict + window contents).

Mistake table (§38 categories → findings → action):

| error_type | findings | action |
|---|---|---|
| `split_caption` | 5 captions split into consecutive blocks by the PDF (Figs 1.2 ×3 occurrences, 1.5, 1.6 ×2, 12.6, 12.8): continuation sits 1.8–3.0 pt below the head, same column | **fixed** — `merge_split_captions` re-joins head + continuation (gap ≤ 3.5 pt AND x-ranges overlap) before scoring; exact text preserved |
| (near-miss trap for the merge rule) | Fig 5.5's caption has body text 2.8 pt below it in the *neighbouring column* | the x-overlap requirement rejects it (pinned by unit test) |
| `false_image` | 6 `caption_not_found` figures are decorative "Exercises" art (girl studying, ×3 chapters) or cut-off scientist name-plates (Hooke; Bose + Einstein — name baked into image pixels) | correctly not matched; `caption_not_found` is the honest verdict (§2.4) |
| `wrong_nearby_text` | 0 — the no-keyword escape (0.78, above the 0.75 geometry cap) held; the measured `H. R. Hertz`-under-portrait trap stays rejected | none needed |
| `caption_above/below_image`, `shared_caption`, `ocr_error` | 0 on these chapters (above-captions already covered by the §17 fallback window) | none needed |

Result after Phase 32 + 33: ch01 14/11, ch05 8/6, ch12 9/7 — **31 figures,
24 matched, 7 caption_not_found, 0 false mappings**; the five split captions
carry their complete printed text, and several confidences rose (e.g. Fig 1.2
0.74 → 0.80). Pinned by `TestMergeSplitCaptions` (unit) and
`TestSplitCaptionsRejoined` (fixture-gated).

## Phase 33 — Manual accuracy verification ✅

Every extracted image on the assessment chapters was rendered and inspected
(protocol, per-image tables, denominators and the claim:
[VERIFICATION.md](./VERIFICATION.md)). Outcome: **13/13 = 100%** on captioned
embedded images (ch05 6/6, ch12 7/7), 0 false mappings.

§33 also caught the one remaining §2.4 violation: the Phase-11 "rescue" of the
ch12 p5 portrait (caption 138 pt above) — page renders proved that caption
belongs to the vector Fig 12.8 plot, not the H. R. Hertz biography portrait.
Fix: fallback above-window 260 → 80 pt (strict 150 → 60 pt); the portrait is
honestly `caption_not_found` again, and ch01 Fig 1.5 upgraded to the strict
pass. Pinned by `test_hertz_portrait_not_forced` (fixture) and
`test_far_above_caption_never_lands_on_portrait` (unit).

## Phase 35 — Performance ✅ (plan §41)

Checklist, in the plan's order — with measured baselines
(`scripts/benchmark.py`):

| § | Item | Status |
|---|---|---|
| 41.1 | Avoid unnecessary OCR | per-page `needs_ocr` decision; all three chapters run with **0 OCR pages** — native text only |
| 41.2 | Initialize OCR once | process-wide engine singleton + vendored models; **init measured 0.21 s**; never loaded when unneeded |
| 41.3 | One PDF globally | §23 FIFO serial worker (already decided) |
| 41.4 | No huge renders | OCR pages at 200 DPI; composite regions rendered **clip-only at 144 DPI** (zoom 2.0) — never a full page at high DPI |
| 41.5 | Don't hold the PDF in memory | **streaming pipeline**: the document is opened once and processed page-by-page; each page's PNGs are written immediately and the pixel bytes released — peak memory is one page's slice (chapters total 138–563 KB of PNGs) |
| 41.6 | Release temp page images | no temp files exist to delete: renders go straight to PNG bytes → disk; OCR works on in-memory numpy arrays; the doc handle is closed in `finally` |
| 41.7 | Don't parallelize | strictly serial end-to-end: one worker, no pools (verified: no `concurrent.futures`/`multiprocessing` anywhere in `src/`) |

Baselines (this machine, native-text path): ch01 0.45 s · ch05 1.67 s
(composite-heavy) · ch12 0.33 s — **2.45 s for all three chapters**,
dominated by clip-rendering of composite regions. OCR, when a page needs
it, adds the engine init (0.21 s) plus ~per-page inference.

## Final plan — PP-DocLayout-S integration ✅ (live-verified)

`src/ocr/layout.py` wraps the vendored PP-DocLayout-S (PaddleX
`create_model`, PIR weights; `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False`
works around the OneDNN/PIR crash) behind a `LayoutEngine` singleton:

- one 150 dpi inference per page (~0.33 s), keeping `image` +
  `figure_title` regions only (px → pt conversion);
- `_tag_caption_regions`: native/OCR text blocks whose center falls inside
  a `figure_title` box are tagged (`layout_label` + confidence);
- **matcher (DL authority — the model decides, not just floors)**:
  a layout-tagged candidate gets the `layout_caption` feature → the scorer
  floors the §15 layout bucket at 0.95; §38-merged captions inherit the
  head's tag; a tagged block is **admitted beyond the strict windows**
  (within 1.5× the gap, same column — `_layout_admission`); a layout
  `figure` region beyond the image **bounds the below-window** (candidates
  starting at/beyond the next figure are soft-barriered,
  `tag_layout_barriers`); and `_arbitrate` breaks near-ties (≤0.05) toward
  DL-confirmed candidates and (≤0.15) away from barriered ones. All
  soft-authority: pinned outputs on the three chapters are byte-identical
  to the pre-authority run;
- **OCR targeting**: caption crops (6 pt pad, page-clamped) are OCR'd
  before any whole-page fallback (`apply_ocr_when_needed(caption_regions=…)`);
- **scan pages**: a raster covering ≥70% of the page uses its overlapping
  layout figure region as the effective bbox and skips the
  figure-internal filter (`tests/test_layout_ocr_e2e.py` proves a scanned
  page end-to-end: layout → targeted OCR → `matched` via `method=ocr`);
- **coverage audit**: progress line reports pages analyzed, figure
  regions, and figure regions with <30% raster coverage (vector-scope);
- **output**: additive per-image `layout` evidence in `results.json`.

Bench (with layout live, all pins intact): ch01 14/11/3 · ch05 8/6/2 ·
ch12 9/7/2 · overall 12.4 s for 3 chapters.

## Assessment artifacts (`../assessment/`)

- `selected_chapters.md` — the two frozen chapters + pinned editions.
- `ground_truth.csv` — 17 legitimate occurrences (13 captioned + 4
  legitimately uncaptioned), manually verified against page renders.
- `errors.md` — final run has no mismatches; tuning history documented.
- `accuracy.md` + `calculate_accuracy.py` — the §53 table: combined
  **13/13 = 100.00%** (pooled denominator; ≥13 = the 95% bar), coverage
  100% ×3.

## Known characteristics of the target NCERT PDFs

- Rich **native** text layer (~200 text blocks/chapter with coordinates) —
  OCR is genuinely a fallback, per plan §2.3/§11.
- Pages are heavily tiled with image xrefs (e.g. 836 xrefs / 11 pages) — many
  are background/graphics tiles, not figures. Phase 4 (image extraction) must
  filter these before treating occurrences as figures.
- PaddlePaddle 3.3.1 CPU + PP-OCRv5 json models: the default oneDNN path fails
  (`ConvertPirAttribute2RuntimeAttribute not supported`) — the pipeline runs
  with `enable_mkldnn=False` (plain CPU kernels, verified working).
