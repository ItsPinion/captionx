#!/usr/bin/env python
"""Phase 35 benchmark: per-stage wall times for the fixture chapters.

Wraps `run_pipeline`'s §30 stage reports with timestamps, so each chapter's
cost profile is visible (and regressions show up as a stage going red).
Native-text chapters should complete in seconds; the OCR engine initializes
lazily and only when a page actually needs it (§41.1/§41.2), so this script
never pays the model-load cost on the NCERT fixtures.

Usage:
    .venv/bin/python scripts/benchmark.py [pdf ...]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models import DocumentSource
from src.pipeline import run_pipeline

FIXTURES = ROOT / "fixtures"


def benchmark(pdf: Path) -> float:
    print(f"\n════ {pdf.name} ════")
    stage_starts: dict[str, float] = {}
    stage_deltas: list[tuple[str, str, float]] = []
    t_prev = time.perf_counter()

    def report(stage: str, message: str) -> None:
        nonlocal t_prev
        now = time.perf_counter()
        stage_starts.setdefault(stage, t_prev)
        stage_deltas.append((stage, message, now - t_prev))
        t_prev = now

    out = Path("/tmp") / f"bench-{pdf.stem}"
    t0 = time.perf_counter()
    outcome = run_pipeline(
        pdf,
        out,
        document_id=f"bench-{pdf.stem}",
        source=DocumentSource.UPLOAD,
        report=report,
    )
    total = time.perf_counter() - t0

    for stage, message, delta in stage_deltas:
        print(f"  {stage:>16} +{delta * 1000:7.1f} ms  {message}")
    print(
        f"  {'TOTAL':>16} +{total * 1000:7.1f} ms  "
        f"{outcome.image_count} image(s), peak pixels = one page only (§41.5)"
    )
    return total


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(FIXTURES.glob("*.pdf"))
    grand = 0.0
    for pdf in pdfs:
        grand += benchmark(pdf)
    print(f"\noverall: {grand:.2f}s for {len(pdfs)} chapter(s)")
    print("(§41.7: strictly serial — one PDF at a time, no worker pools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
