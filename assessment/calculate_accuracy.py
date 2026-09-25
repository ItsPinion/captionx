#!/usr/bin/env python
"""Assessment accuracy calculator (final plan §41 / §53).

Reads `assessment/ground_truth.csv` (the manually verified reference for the
two frozen chapters) and the pipeline's `results.json` per chapter, then
prints the §53 table:

    per-chapter + combined image-caption accuracy (combined denominator,
    never an average of percentages), image-extraction coverage, and the
    minimum number of correct mappings needed for 95% (ceil(0.95 × N)).

Usage:
    .venv/bin/python assessment/calculate_accuracy.py \
        --ground-truth assessment/ground_truth.csv \
        --results ch05=path/to/ch05/results.json \
        --results ch12=path/to/ch12/results.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path


def _norm(text: str | None) -> str:
    """Whitespace-normalized caption text (§13.4: characters untouched)."""
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def load_ground_truth(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_results(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["images"]


def evaluate(gt_rows: list[dict], results_by_doc: dict[str, list[dict]]) -> dict:
    per_doc: dict[str, dict] = {}
    for doc, results in results_by_doc.items():
        rows = [
            r
            for r in gt_rows
            if doc == r["document"] or doc in Path(r["document"]).stem
        ]
        captioned = [r for r in rows if r["caption_status"] == "captioned"]
        uncaptioned = [r for r in rows if r["caption_status"] != "captioned"]

        correct = wrong = missing = 0
        for row in captioned:
            page = int(row["page"])
            expected = _norm(row["expected_caption"])
            page_images = [i for i in results if i["page"] == page]
            if any(
                i["status"] == "matched" and _norm(i["caption"]) == expected
                for i in page_images
            ):
                correct += 1
            elif any(i["status"] == "matched" for i in page_images):
                wrong += 1  # matched something, but not the expected caption
            else:
                missing += 1

        # extraction coverage: every legitimate occurrence (captioned rows +
        # uncaptioned rows) should appear as an extracted image on its page
        extracted = covered = 0
        pages = {int(r["page"]) for r in rows}
        for page in sorted(pages):
            expected_here = sum(1 for r in rows if int(r["page"]) == page)
            found_here = sum(1 for i in results if i["page"] == page)
            covered += min(expected_here, found_here)
            extracted += expected_here

        per_doc[doc] = {
            "expected_captioned": len(captioned),
            "correct": correct,
            "wrong": wrong,
            "caption_not_found": missing,
            "expected_images": extracted,
            "covered_images": covered,
            "uncaptioned_legit": len(uncaptioned),
        }
    return per_doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--results", action="append", required=True, metavar="DOC=PATH")
    args = parser.parse_args()

    gt = load_ground_truth(args.ground_truth)
    results_by_doc = {}
    labels = []
    for spec in args.results:
        label, _, path = spec.partition("=")
        results_by_doc[label] = load_results(Path(path))
        labels.append(label)

    per_doc = evaluate(gt, results_by_doc)
    total_expected = sum(d["expected_captioned"] for d in per_doc.values())
    total_correct = sum(d["correct"] for d in per_doc.values())
    total_wrong = sum(d["wrong"] for d in per_doc.values())
    total_nf = sum(d["caption_not_found"] for d in per_doc.values())
    total_imgs = sum(d["expected_images"] for d in per_doc.values())
    total_cov = sum(d["covered_images"] for d in per_doc.values())
    need = math.ceil(0.95 * total_expected)

    def pct(num: int, den: int) -> str:
        return f"{num / den * 100:.2f}%" if den else "—"

    print(f"{'Metric':<44}{'Ch1':>10}{'Ch2':>10}{'Combined':>10}")
    print("─" * 74)
    docs = list(per_doc.values())
    rows = [
        ("Expected legitimate image occurrences", [d["expected_images"] for d in docs], total_imgs),
        ("Expected captioned image occurrences", [d["expected_captioned"] for d in docs], total_expected),
        ("Correct image → caption mappings", [d["correct"] for d in docs], total_correct),
        ("Wrong captions", [d["wrong"] for d in docs], total_wrong),
        ("Caption not found (vs captioned)", [d["caption_not_found"] for d in docs], total_nf),
        ("Image extraction coverage", [pct(d["covered_images"], d["expected_images"]) for d in docs], pct(total_cov, total_imgs)),
        ("Image-caption accuracy", [pct(d["correct"], d["expected_captioned"]) for d in docs], pct(total_correct, total_expected)),
        ("Min correct needed for 95% (ceil)", [math.ceil(0.95 * d["expected_captioned"]) for d in docs], need),
    ]
    for label, values, combined in rows:
        v1, v2 = (list(values) + ["—", "—"])[:2]
        print(f"{label:<44}{str(v1):>10}{str(v2):>10}{str(combined):>10}")
    print("─" * 74)
    verdict = "TARGET MET" if total_correct >= need else "TARGET NOT MET"
    print(f"combined {total_correct}/{total_expected} — need ≥ {need} for 95% → {verdict}")
    return 0 if total_correct >= need else 1


if __name__ == "__main__":
    raise SystemExit(main())
