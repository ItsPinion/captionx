# Assessment Accuracy Calculation (final plan §41, §53)

Computed by `assessment/calculate_accuracy.py` from
`assessment/ground_truth.csv` (manually verified against page renders) and
each frozen chapter's pipeline `results.json`. Regenerate with:

```bash
extraction/.venv/bin/python assessment/calculate_accuracy.py \
  --ground-truth assessment/ground_truth.csv \
  --results ch05=extraction/results_ncert_class9_science_ch05_cell/results.json \
  --results ch12=extraction/results_ncert_class9_science_ch12_sound/results.json
```

Denominator rules: accuracy uses every legitimate image occurrence that has
a real printed caption (captioned rows only); the **combined** column pools
both chapters into one denominator (never an average of the two
percentages). Coverage counts legitimate occurrences (captioned +
`source_has_no_caption`) that the pipeline extracted.

## §53 Table (verified 2026-09-25)

| Metric | Chapter 1 (ch05 Cell) | Chapter 2 (ch12 Sound) | Combined |
|---|---|---|---|
| Expected legitimate image occurrences | 8 | 9 | 17 |
| Expected captioned image occurrences | 6 | 7 | 13 |
| Correct image → caption mappings | 6 | 7 | 13 |
| Wrong captions | 0 | 0 | 0 |
| Caption not found (vs captioned) | 0 | 0 | 0 |
| Image extraction coverage | 100.00% | 100.00% | 100.00% |
| Image-caption accuracy | 100.00% | 100.00% | 100.00% |
| Minimum correct needed for 95% (ceil) | 6 | 7 | 13 |

Combined **13/13 ≥ 13** → the ≥95% target is met (verified manually against
the PDF pages, then recomputed mechanically by the script above).

```text
Metric                                             Ch1       Ch2  Combined
──────────────────────────────────────────────────────────────────────────
Expected legitimate image occurrences                8         9        17
Expected captioned image occurrences                 6         7        13
Correct image → caption mappings                     6         7        13
Wrong captions                                       0         0         0
Caption not found (vs captioned)                     0         0         0
Image extraction coverage                      100.00%   100.00%   100.00%
Image-caption accuracy                         100.00%   100.00%   100.00%
Min correct needed for 95% (ceil)                    6         7        13
──────────────────────────────────────────────────────────────────────────
combined 13/13 — need ≥ 13 for 95% → TARGET MET
```
