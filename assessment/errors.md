# Assessment Error Log (final plan §41 / §49A)

One row per incorrectly matched image occurrence on the frozen chapters
(`ground_truth.csv` captioned rows), from the final assessment run.

## Final run — 0 errors

| # | document | page | expected | assigned | status | root cause |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | no mismatches: 13/13 captioned occurrences correct, 0 wrong captions, 0 missed captions |

Both chapters also have 2 legitimate occurrences with **no printed caption**
each (a cut-off name-plate portrait and decorative Exercises art). The
pipeline reports `caption_not_found` for all four — the honest outcome per
the "false mapping is worse than not_found" rule — and they are excluded
from the accuracy denominator by design (they are counted in coverage).

## Reviewer notes from the tuning history (resolved)

1. **ch12 p05 portrait (Hertz)** — an early phase "rescued" it by attaching
   the Fig 12.8 caption 138 pt above it; page rendering proved that caption
   belongs to a vector wave-plot figure. Fix: distance-based escape rules +
   honest `caption_not_found`. Verified correct in the final run.
2. **ch05 p08 portrait (Hooke)** — the xref crop clips the name-plate text,
   and no `Fig.` caption exists for it anywhere on the page.
   `caption_not_found` is correct.
3. **Decorative Exercises art** (both chapters) — excluded from the
   denominator entirely: §2.3 scope excludes decorative/repeated art, so
   these occurrences are legitimate images but caption-less by design.
4. **Shared captions** — ch12 p10 carries two rasters under one caption
   (Fig 12.12). Both occurrences are separate ground-truth rows with the
   same expected caption; both are matched correctly.

## Known limitations (documented, not errors)

- **Vector-only figures** (no raster component) are outside the raster
  pipeline's scope: a page whose figure is pure vector art reports 0 images,
  which is correct for this scope (verified on the current official Maths
  chapters). The PP-DocLayout-S coverage audit line ("K without raster")
  makes this visible per run.
- Layout evidence (`figure` / `caption_region` boxes in `results.json`) is
  auxiliary; the matcher treats PP-DocLayout-S output as evidence (a
  scoring floor + OCR targeting + scan handling), never as a hard gate, so
  a missed detection degrades gracefully to the pre-layout behavior.
