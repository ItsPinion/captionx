# Extraction Engine (Python)

Python extraction pipeline: PyMuPDF (native images/text) + PaddleOCR
(fallback OCR) + spatial/textual caption matching → JSON/CSV + images.

**Setup begins in Phase 2** of [../plan.md](../plan.md) (§8) — a `venv` will be
created in `extraction/.venv/` (gitignored) with `requirements.txt`.

The engine is invoked by the Hono API as a plain process:

```bash
python main.py --job-id <id> --input <pdf-path> --output <result-path>
```
