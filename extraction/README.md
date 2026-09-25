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

**Phase 3 — internal data model ✅ (46 tests)**

`src/models/schemas.py` defines the §9 structures — `Document`,
`ImageOccurrence` (never deduplicated), `TextRegion` (`native_pdf`/`ocr`),
`CaptionCandidate` (text + bbox + features + score), `MatchResult`
(`matched`/`caption_not_found`) — plus a frozen `BBox` geometry primitive in
PDF page points (top-left origin, y down) with the overlap/gap/alignment
relations the caption-matching features (Phases 7–9) build on. Enum string
values mirror the TypeScript `@captionx/shared` JSON contract; a contract test
guards them.

Run the tests:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```


## Setup

```bash
cd extraction
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# headless servers only (missing libGL.so.1) — see requirements.txt notes:
.venv/bin/pip uninstall -y opencv-contrib-python
.venv/bin/pip install --no-deps --force-reinstall opencv-contrib-python-headless==4.10.0.84 \
  && .venv/bin/pip install --no-deps --force-reinstall opencv-contrib-python==4.10.0.84
```

### OCR models (PP-OCRv5 mobile)

PaddleOCR normally downloads models from Baidu BOS / HuggingFace / ModelScope.
In network-restricted environments **pre-seed the PaddleX cache** instead —
PaddleX uses `~/.paddlex/official_models/<model_name>/` as-is when the
directory exists. Required layout:

```text
~/.paddlex/official_models/
├── PP-OCRv5_mobile_det/   inference.json · inference.pdiparams · inference.yml
└── PP-OCRv5_mobile_rec/   inference.json · inference.pdiparams · inference.yml
```

The models are the official PaddleX packages (a public GitHub repo mirror works:
fetch `backend/models/V5/PP-OCRv5_mobile_{det,rec}_infer/*` from
`YaoFANGUK/video-subtitle-extractor` via the GitHub API and place them as above).

Set `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` to skip the hoster connectivity
probe (the pipeline code does this automatically).

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
