# Phase 34 — Edge-Case Checklist (plan §40)

Each of the plan's 12 cases, deliberately inspected before finalizing, with
the evidence that pins the behavior. Re-verified on the post-§33 pipeline.

| # | Case | Behavior / Evidence | Status |
|---|---|---|---|
| 1 | Image directly above caption (caption below image) | The dominant NCERT layout — **all 24 matched captions** in ch01/05/12 sit below their images (re-verified geometrically: caption `y0 ≥ image y1` for every pair). Pins: `TestStrictMatchesHold`, `TestFallbackRescues`. | ✓ |
| 2 | Image directly below caption (caption above image) | Supported within the (§33-corrected) 60 pt above-window — unit-pinned: `TestWindows::test_caption_above_within_window`, `test_window_edges_inclusive`. No genuine instance occurs in the target chapters (the two historical "above" matches were §33's false-mapping trap, now rejected). | ✓ |
| 3 | Caption begins `Fig.` | The universal NCERT form — every fixture pin uses it: `Fig. 5.1`, `Fig. 1.6`, `Fig. 12.6`, `Fig.12.13` (no space) — `_NUMBERING_STRONG_RE` covers all spacings. | ✓ |
| 4 | Caption begins `Figure` | `fig(?:ure)?` in all three numbering regexes + keyword lists; pinned by `test_features` ("Figure 3.1 something" → 1.0) and `test_matching` ("Figure 4.1" caption). | ✓ |
| 5 | Caption without figure keyword | Zero-evidence escape: geometry-only scores cap at 0.75 < escape 0.78, so name-labels (`H. R. Hertz`, `Megaphone`) never match; fallback disables the escape entirely. Pinned: `TestFallbackDiscipline::test_zero_evidence_never_matches_even_in_fallback`, `TestCaptionlessFigures` (portrait traps). | ✓ |
| 6 | Two adjacent images | Fig 5.1/5.2 (side by side, own captions) and the stacked Fig 12.12 pair — each occurrence scored separately; only an actual shared winner triggers §17 series passthrough (below-inheriting figures excluded). `TestSeriesPassthrough`. | ✓ |
| 7 | Two images sharing a caption region | Fig 1.6 (a/b stacked), Fig 1.10 (side-by-side), Fig 12.12 — both occurrences get the same full caption. `TestSharedAndStackedFigures`, `test_fig_1_10_shared`, `test_fig_12_12_stacked`. | ✓ |
| 8 | Image without a caption | `caption_not_found` + `caption=None` + `no_reliable_candidate` — never an invented caption (§2.4). 7 real instances verified visually (decorative art / name-plates): `TestCaptionlessFigures`, `test_hertz_portrait_not_forced`. | ✓ |
| 9 | Multi-column pages | Every fixture page is two-column; same-column geometry enforced via horizontal-overlap features (≥20 % overlap or ≤40 pt slack) — cross-column blocks never become candidates. Pinned throughout `test_candidates` / `test_features`. | ✓ |
| 10 | OCR necessary | Full engine path (render page → PaddleOCR → boxes in PDF points): real-inference integration test **run for this checklist** (`CAPTIONX_OCR_TEST=1`, 1 passed, 4 s — PP-OCRv5 mobile det/rec from the vendored models). Pipeline-level synthetic OCR tests: `test_pipeline` / `test_ocr`. | ✓ |
| 11 | Tiny decorative graphics | Sliver-tile storm filtered by min-dimension/aspect/area ratio: ch12 p10 carries **247 raster xrefs → 4 figures**; p3 carries 77 slivers → 1 figure. `test_images` (hairline/decoration filters), visible in every chapter's counts. | ✓ |
| 12 | Same image appears twice | §18 no-dedup: every occurrence is a separate record — Fig 1.2 ×3, Fig 1.6 ×2, Fig 1.10 ×2 all present in output with separate `image_id`s. `test_no_deduplication_same_image_twice` / `test_no_deduplication_two_occurrences_distinct` (and the ch01 pin showing three `page_02_image_0X` rows). | ✓ |

## Additional edge behaviors verified during §32–§33

- **Split captions** (PDF breaks a caption into consecutive blocks) — re-joined
  before scoring; full printed text preserved (`TestMergeSplitCaptions`).
- **Far-above caption decoys** — never forced onto a portrait
  (`test_far_above_caption_never_lands_on_portrait`).
- **Running headers/footers/page numbers** — filtered as page furniture.
- **Corrupt/broken xrefs** — skipped with a warning, extraction continues.
- **Missing/corrupt PDFs** — `input`/`pdf_parse` stage failures with
  `status.json` messages (§30), never a crash.
