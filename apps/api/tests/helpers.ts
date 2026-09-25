/**
 * Shared test bootstrap for API tests.
 *
 * Points every CAPTIONX_* path at a fresh temp dir and swaps the Python
 * interpreter for a deterministic stub "engine" (writes result files,
 * exits 0/1) — no real extraction in API tests.
 */
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const testRoot = mkdtempSync(join(tmpdir(), "captionx-api-test-"));

// A tiny valid PDF (header only is enough for the API's magic sniff).
export const TINY_PDF_BYTES = new TextEncoder().encode(
  "%PDF-1.4\n%fake-test-pdf\n%%EOF\n",
);

export const FAIL_PDF_BYTES = new TextEncoder().encode(
  "%PDF-1.4\n%this-one-fails\n%%EOF\n",
);

// The stub engine: writes results + status, fails when the input contains
// "this-one-fails".
const STUB = `#!/usr/bin/env bash
set -u
out=""; status=""; job=""; input=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) out="$2"; shift 2;;
    --status) status="$2"; shift 2;;
    --job-id) job="$2"; shift 2;;
    --input) input="$2"; shift 2;;
    *) shift;;
  esac
done
mkdir -p "$out/images"
if grep -q "this-one-fails" "$input"; then
  printf '{"job_id":"%s","status":"failed","stage":"pdf_parse","message":"stub engine failure"}' "$job" > "$status"
  exit 1
fi
cat > "$out/results.json" <<JSON
{"document":{"filename":"stub.pdf","source":"upload","page_count":1},
 "images":[{"image":"stub_page_01_image_01.png","page":1,"caption":"Fig. 1.1: stub",
            "confidence":0.9,"status":"matched","method":"native_text"}]}
JSON
printf 'image,page,caption,confidence,status,method\\nstub_page_01_image_01.png,1,Fig. 1.1: stub,0.9,matched,native_text\\n' > "$out/results.csv"
printf 'PNGDATA' > "$out/images/stub_page_01_image_01.png"
printf '{"job_id":"%s","status":"processing","stage":"ocr","message":"stub"}' "$job" > "$status"
exit 0
`;

export const stubEngine = join(testRoot, "stub_engine.py");
writeFileSync(stubEngine, STUB);
import { chmodSync } from "node:fs";
chmodSync(stubEngine, 0o755);

process.env.CAPTIONX_UPLOADS_DIR = join(testRoot, "uploads");
process.env.CAPTIONX_JOBS_DIR = join(testRoot, "jobs");
process.env.CAPTIONX_RESULTS_DIR = join(testRoot, "results");
process.env.CAPTIONX_PYTHON_BIN = stubEngine;
process.env.CAPTIONX_MAIN_SCRIPT = "--unused--";

mkdirSync(process.env.CAPTIONX_UPLOADS_DIR, { recursive: true });
mkdirSync(process.env.CAPTIONX_JOBS_DIR, { recursive: true });
mkdirSync(process.env.CAPTIONX_RESULTS_DIR, { recursive: true });

export function makePdfFile(name: string, bytes: Uint8Array): File {
  return new File([bytes as unknown as BlobPart], name, { type: "application/pdf" });
}
