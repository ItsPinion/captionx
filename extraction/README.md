# Extraction Engine (Python)

PyMuPDF (native PDF images + text) + PaddleOCR (fallback OCR) + spatial/textual
caption matching → `results.json` + `results.csv` + `images/`.

Part of the CaptionX assessment project — see [../plan.md](../plan.md).

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

## Engine invocation (contract, implemented in later phases)

```bash
python main.py --job-id <id> --input <pdf-path> --output <result-path>
```

## Known characteristics of the target NCERT PDFs

- Rich **native** text layer (~200 text blocks/chapter with coordinates) —
  OCR is genuinely a fallback, per plan §2.3/§11.
- Pages are heavily tiled with image xrefs (e.g. 836 xrefs / 11 pages) — many
  are background/graphics tiles, not figures. Phase 4 (image extraction) must
  filter these before treating occurrences as figures.
- PaddlePaddle 3.3.1 CPU + PP-OCRv5 json models: the default oneDNN path fails
  (`ConvertPirAttribute2RuntimeAttribute not supported`) — the pipeline runs
  with `enable_mkldnn=False` (plain CPU kernels, verified working).
