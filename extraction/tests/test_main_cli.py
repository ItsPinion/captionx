"""End-to-end tests for the CLI contract (plan.md §21 / §47).

Runs `main.py` as a real subprocess — exactly how the Hono API will invoke it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pdf_fixtures import add_text, new_page, place_image, solid_png

MAIN = Path(__file__).resolve().parent.parent / "main.py"
FIXTURES = MAIN.parent / "fixtures"
CELL_PDF = FIXTURES / "ncert_class9_science_ch05_cell.pdf"


def make_simple_pdf(tmp_path: Path) -> Path:
    doc, page = new_page()
    place_image(page, (100, 100, 260, 260), solid_png(120, 120, (10, 200, 10)))
    add_text(page, "Fig. 2.1: A green square of note", (100, 280))
    path = tmp_path / "cli_simple.pdf"
    doc.save(path)
    doc.close()
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        capture_output=True,
        text=True,
        timeout=300,
    )


class TestCliSuccess:
    def test_plan_milestone_invocation(self, tmp_path):
        """plan.md §47: the first working milestone command."""
        pdf = make_simple_pdf(tmp_path)
        out_dir = tmp_path / "results" / "sample"
        status = tmp_path / "jobs" / "job_001" / "status.json"

        proc = run_cli(
            "--job-id", "test-001",
            "--input", str(pdf),
            "--output", str(out_dir),
            "--status", str(status),
        )

        assert proc.returncode == 0, proc.stderr
        assert (out_dir / "results.json").is_file()
        assert (out_dir / "results.csv").is_file()
        assert (out_dir / "images").is_dir()
        assert list(out_dir.joinpath("images").glob("*.png"))

        payload = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
        assert payload["images"][0]["caption"] == "Fig. 2.1: A green square of note"

    def test_status_file_reaches_completed(self, tmp_path):
        pdf = make_simple_pdf(tmp_path)
        status = tmp_path / "status.json"
        proc = run_cli(
            "--job-id", "j", "--input", str(pdf),
            "--output", str(tmp_path / "out"), "--status", str(status),
        )
        assert proc.returncode == 0
        final = json.loads(status.read_text(encoding="utf-8"))
        assert final["status"] == "completed"
        assert final["stage"] == "output"
        assert final["job_id"] == "j"

    def test_real_fixture_via_cli(self, tmp_path):
        if not CELL_PDF.exists():
            pytest.skip("fixtures missing")
        out_dir = tmp_path / "cell"
        proc = run_cli(
            "--job-id", "job_cell",
            "--input", str(CELL_PDF),
            "--output", str(out_dir),
            "--source", "upload",
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
        statuses = [i["status"] for i in payload["images"]]
        assert statuses.count("matched") == 6
        assert statuses.count("caption_not_found") == 2


class TestCliFailure:
    def test_missing_input_fails_with_stage(self, tmp_path):
        status = tmp_path / "status.json"
        proc = run_cli(
            "--job-id", "j", "--input", str(tmp_path / "ghost.pdf"),
            "--output", str(tmp_path / "out"), "--status", str(status),
        )
        assert proc.returncode == 1
        final = json.loads(status.read_text(encoding="utf-8"))
        assert final["status"] == "failed"
        assert final["stage"] == "input"
        assert "ghost.pdf" in final["message"]

    def test_corrupt_pdf_fails_nonzero(self, tmp_path):
        fake = tmp_path / "corrupt.pdf"
        fake.write_bytes(b"not a pdf at all")
        status = tmp_path / "status.json"
        proc = run_cli(
            "--job-id", "j", "--input", str(fake),
            "--output", str(tmp_path / "out"), "--status", str(status),
        )
        assert proc.returncode == 1
        final = json.loads(status.read_text(encoding="utf-8"))
        assert final["status"] == "failed"
        assert final["stage"] in ("input", "pdf_parse")

    def test_missing_required_args_rejected(self):
        proc = run_cli("--job-id", "only-job")
        assert proc.returncode == 2  # argparse error

    def test_failure_does_not_create_result_files(self, tmp_path):
        status = tmp_path / "status.json"
        out_dir = tmp_path / "out"
        run_cli(
            "--job-id", "j", "--input", str(tmp_path / "ghost.pdf"),
            "--output", str(out_dir), "--status", str(status),
        )
        assert not (out_dir / "results.json").exists()
