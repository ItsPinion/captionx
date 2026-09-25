#!/usr/bin/env python
"""CaptionX extraction engine — CLI entry point (plan.md §21 / §47).

    python main.py --job-id <id> --input <pdf-path> --output <result-path>
                   [--status <status.json>] [--source upload|url] [--filename <display name>]

Behavior (§21):
    1. validates arguments
    2. loads the PDF
    3. updates the status file (if given) through §30 stages
    4. runs extraction (+ OCR fallback + matching)
    5. writes results.json
    6. writes results.csv
    7. exits 0 on success, non-zero on failure

Output layout (§22):

    <output>/results.json
    <output>/results.csv
    <output>/images/<document>_page_NN_image_NN.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models import DocumentSource  # noqa: E402
from src.pipeline import STAGES, StageError, run_pipeline  # noqa: E402


def _write_status(path: Path, payload: dict) -> None:
    """Best-effort atomic status write (never crashes the pipeline)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8"
        )
        with handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(handle.name, path)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="CaptionX image/caption extraction engine for one PDF.",
    )
    parser.add_argument("--job-id", required=True, help="unique job identifier")
    parser.add_argument("--input", required=True, help="path to the source PDF")
    parser.add_argument("--output", required=True, help="result directory to create")
    parser.add_argument(
        "--status",
        help="optional status.json path to update with §30 stage progress",
    )
    parser.add_argument(
        "--source",
        choices=[s.value for s in DocumentSource],
        default=DocumentSource.UPLOAD.value,
        help="how the PDF entered the system (default: upload)",
    )
    parser.add_argument(
        "--filename",
        help="display filename recorded in results (default: input basename)",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_dir = Path(args.output)
    status_path = Path(args.status) if args.status else None

    def report(stage: str, message: str) -> None:
        print(f"[{stage}] {message}", flush=True)
        if status_path is not None:
            _write_status(
                status_path,
                {
                    "job_id": args.job_id,
                    "status": "processing",
                    "stage": stage,
                    "message": message,
                },
            )

    report("input", f"job {args.job_id} starting")
    try:
        outcome = run_pipeline(
            input_path,
            output_dir,
            document_id=args.job_id,
            source=DocumentSource(args.source),
            filename=args.filename,
            report=report,
        )
    except StageError as exc:
        print(f"[{exc.stage}] FAILED: {exc.message}", file=sys.stderr, flush=True)
        if status_path is not None:
            _write_status(
                status_path,
                {
                    "job_id": args.job_id,
                    "status": "failed",
                    "stage": exc.stage,
                    "message": exc.message,
                },
            )
        return 1
    except Exception as exc:  # unexpected — still exit non-zero, no stack to users
        print(f"[output] FAILED: unexpected error: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        if status_path is not None:
            _write_status(
                status_path,
                {
                    "job_id": args.job_id,
                    "status": "failed",
                    "stage": "output",
                    "message": f"unexpected error: {exc}",
                },
            )
        return 1

    if status_path is not None:
        _write_status(
            status_path,
            {
                "job_id": args.job_id,
                "status": "completed",
                "stage": "output",
                "message": (
                    f"{outcome.image_count} image(s), "
                    f"{sum(1 for m in outcome.results.values() if m.status.value == 'matched')}"
                    " caption(s) matched"
                ),
            },
        )
    print(
        f"[done] {outcome.image_count} image(s) → {outcome.output_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
