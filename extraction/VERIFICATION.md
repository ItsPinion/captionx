# Phase 33 — Manual Accuracy Verification (plan §39)

Per the plan this is **not** an automated benchmark: every extracted image on
the two assessment chapters was rendered and *visually inspected*, asking the
two questions from §39:

> Did we extract the correct image?
> Did we attach the correct caption?

Run on the post-Phase-32 pipeline (`main.py`, ch05 + ch12 fixtures).

## Denominator (stated honestly)

`total_expected_pairs` = printed `Fig.` captions that belong to an **embedded
raster image** — the engine's domain by design (plan §2.3 step 1: "Extract
embedded images"; §2.2: no heavy additions).

**Boundary, documented not hidden:** ch12 also contains 11 captions whose
figures are PDF *vector line drawings* (12.1, 12.2, 12.3, 12.5, 12.9, 12.10,
12.11, 12.15, 12.17, 12.18, 12.19) and two wave-figure components drawn as
hairline raster slivers (12.8). Vector art is invisible to embedded-image
extraction; no plan phase (2–16) specifies vector rendering. These are out of
scope for the accuracy claim, and no caption is forced onto an unrelated raster
because of them (that was the Phase-33 bug below).

## ch05 — Cell (assessment chapter 1)

| image (page) | inspected content | assigned caption | verdict |
|---|---|---|---|
| p01_01 | compound microscope drawing | Fig. 5.1: Compound microscope | correct |
| p01_02 | onion peel cells, blue | Fig. 5.2: Cells of an onion peel | correct |
| p02_01 | cell-type collage (smooth muscle, blood, nerve, ovum…) | Fig. 5.3: Various cells from the human body | correct |
| p06_01 | rod-shaped bacterium with flagella | Fig. 5.4: Prokaryotic cell | correct |
| p07_01 | animal cell cutaway (Golgi, ER, nucleus labels) | Fig. 5.5: Animal cell | correct |
| p08_02 | plant cell cutaway (large vacuole, chloroplast) | Fig. 5.6: Plant cell | correct |
| p08_01 | Robert Hooke portrait (name-plate text cut off in the xref crop) | caption_not_found | honest — no printed Fig caption exists for it |
| p10_01 | decorative "Exercises" art (girl studying) | caption_not_found | honest |

**ch05: 6 correct / 6 expected = 100%**, zero false mappings.

## ch12 — Sound (assessment chapter 2)

| image (page) | inspected content | assigned caption | verdict |
|---|---|---|---|
| p02_01 | man whistling into tin-can setup | Fig. 12.4: A beam of light… | correct — the raster is a component of the composite Fig 12.4 (can + vector beam overlays; verified against the rendered page) |
| p03_01 | bell jar with suspended ball | Fig. 12.6: Bell jar experiment… travel in vacuum. | correct (full caption after the §32 split fix) |
| p04_01 | hand holding slinky | Fig. 12.7: Longitudinal wave in a slinky. | correct |
| p10_01 | boy with megaphone | Fig 12.12: A megaphone and a horn. | correct — upper half of the stacked pair (§17 series passthrough) |
| p10_02 | pink bulb horn | Fig 12.12: A megaphone and a horn. | correct — lower half |
| p10_03 | grey sound-board disc | Fig. 12.14: Curved ceiling of a conference hall. | correct — raster component of the composite Fig 12.14 |
| p10_04 | doctor examining child with stethoscope | Fig.12.13: Stethoscope | correct |
| p05_01 | Heinrich Rudolph Hertz portrait (biography sidebar) | caption_not_found *(after the §33 fix)* | honest — its caption-less state is correct; see below |
| p15_01 | decorative "Exercises" art | caption_not_found | honest |

**ch12: 7 correct / 7 expected = 100%**, zero false mappings.

## The Phase-33 finding (and fix)

Phase 11 "rescued" the p05 portrait by attaching the caption 138 pt *above*
it ("Fig. 12.8: Sound propagates as density or pressure variations…"),
believing that caption belonged to the portrait. Page rendering proves the
caption belongs to the **vector** wave-plot figure above it; the portrait is a
biography sidebar whose real name-plate ("H. R. Hertz") was a decoy the
fallback correctly ignored — the far-above caption was the actual trap. A
false mapping is worse than `caption_not_found` (§2.4).

Fix: the fallback above-window shrank 260 → 80 pt (strict 150 → 60 pt). The
only pair the old windows served was this false one. Bonus: ch01 Fig 1.5 now
matches via the **strict** pass (the distant body block no longer creates a
low-margin competitor).

## Accuracy

```text
correct_image_caption_pairs = 13   (ch05 6 + ch12 7)
total_expected_pairs        = 13   (captioned embedded raster images)

accuracy = 13 / 13 = 100%   ≥ 95% requirement ✓
```

Also verified, same pipeline, ch01 (not an assessment chapter): 11/11 correct
pairs, 3 honest `caption_not_found` (Exercises art, cut-off name-plates).

Global pins after the fix: ch01 14 images / 11 matched, ch05 8 / 6,
ch12 9 / 7 — **31 figures, 24 matched, 7 caption_not_found, 0 false
mappings**. Every not-found image was viewed: decorative art or name-plates
only.

## Claim

> On the two assessment chapters, every extracted embedded image that has a
> printed caption carries its complete, correct caption (13/13 = 100%);
> images without captions are reported as `caption_not_found`. Figures drawn
> as PDF vector art are outside the embedded-image pipeline's scope (plan
> §2.3) and are documented here rather than silently dropped.
