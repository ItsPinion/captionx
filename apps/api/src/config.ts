import { join } from "node:path";

/**
 * Runtime configuration for the CaptionX API.
 *
 * All roots default to the repository layout from plan.md §5/§16 and can be
 * overridden with environment variables (used by tests and deployments).
 */
const repoRoot = join(import.meta.dir, "..", "..", "..");

export const config = {
  repoRoot,
  /** Uploaded PDFs (originals kept for debugging — plan.md §42). */
  uploadsDir: process.env.CAPTIONX_UPLOADS_DIR ?? join(repoRoot, "data", "uploads"),
  /** Per-job state: <jobId>/job.json + status.json (plan.md §16). */
  jobsDir: process.env.CAPTIONX_JOBS_DIR ?? join(repoRoot, "data", "jobs"),
  /** Completed result directories: <jobId>/results.json|results.csv|images/. */
  resultsDir: process.env.CAPTIONX_RESULTS_DIR ?? join(repoRoot, "data", "results"),
  /** Python interpreter of the extraction venv (Phase 2). */
  pythonBin:
    process.env.CAPTIONX_PYTHON_BIN ?? join(repoRoot, "extraction", ".venv", "bin", "python"),
  /** The engine CLI (plan.md §21 / §47). */
  mainScript: process.env.CAPTIONX_MAIN_SCRIPT ?? join(repoRoot, "extraction", "main.py"),
  /** URL download limits (plan.md §19). */
  urlDownloadTimeoutMs: Number(process.env.CAPTIONX_URL_TIMEOUT_MS ?? 30_000),
  maxPdfBytes: Number(process.env.CAPTIONX_MAX_PDF_BYTES ?? 100 * 1024 * 1024),
};

export function ensureDataDirs(): void {
  const { mkdirSync } = require("node:fs") as typeof import("node:fs");
  for (const dir of [config.uploadsDir, config.jobsDir, config.resultsDir]) {
    mkdirSync(dir, { recursive: true });
  }
}

/**
 * Clear all runtime state (uploads, job dirs, results) — the "fresh start"
 * the dashboard's boot flow offers. `.gitkeep` placeholders are preserved
 * so the empty tree stays in Git. Runs only when explicitly invoked:
 * the API wires it to `CAPTIONX_RESET_DATA=1` at boot (the default `bun
 * run dev` sets it; `bun run dev:keep` preserves state for the §24
 * restart-recovery demo).
 *
 * Returns how many entries were removed.
 */
export function resetDataDirs(): number {
  const { readdirSync, rmSync } = require("node:fs") as typeof import("node:fs");
  ensureDataDirs();
  let removed = 0;
  for (const dir of [config.uploadsDir, config.jobsDir, config.resultsDir]) {
    for (const entry of readdirSync(dir)) {
      if (entry === ".gitkeep") continue;
      rmSync(join(dir, entry), { recursive: true, force: true });
      removed += 1;
    }
  }
  return removed;
}

export const paths = {
  jobDir: (jobId: string) => join(config.jobsDir, jobId),
  jobFile: (jobId: string) => join(config.jobsDir, jobId, "job.json"),
  statusFile: (jobId: string) => join(config.jobsDir, jobId, "status.json"),
  resultDir: (jobId: string) => join(config.resultsDir, jobId),
  resultsJson: (jobId: string) => join(config.resultsDir, jobId, "results.json"),
  resultsCsv: (jobId: string) => join(config.resultsDir, jobId, "results.csv"),
  imagesDir: (jobId: string) => join(config.resultsDir, jobId, "images"),
};
