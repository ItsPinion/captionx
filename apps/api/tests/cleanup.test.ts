import { describe, expect, test } from "bun:test";
import { mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";

import "./helpers";
import { cleanupStrayTmpFiles } from "../src/services/cleanup";
import { config } from "../src/config";

/** §36: only *.tmp litter is swept; real uploads/jobs/results survive. */
describe("cleanupStrayTmpFiles (§36)", () => {
  test("removes crash-leftover tmp files at depth 2, keeps real state", () => {
    // NOTE: any job.json planted here must be a COMPLETE StoredJob — bun
    // runs test files concurrently in one process, and an incomplete record
    // would blow up allJobs()'s createdAt sort in the other files. It is
    // removed again below regardless of outcome.
    // Stray atomic-write temps in all three roots.
    const jobDir = join(config.jobsDir, "job_tmpfix01");
    mkdirSync(jobDir, { recursive: true });
    writeFileSync(join(jobDir, "job.json.4242.tmp"), '{"status":"queued"');
    writeFileSync(join(config.uploadsDir, "chapter.pdf.77.tmp"), "partial");
    writeFileSync(join(config.resultsDir, "results.json.9.tmp"), "{}");

    // Real state that must survive the sweep — a COMPLETE StoredJob record.
    writeFileSync(
      join(jobDir, "job.json"),
      JSON.stringify({
        id: "job_tmpfix01",
        status: "queued",
        source: "upload",
        filename: "tmpfix.pdf",
        createdAt: "2026-09-25T00:00:00.000Z",
        file: join(config.uploadsDir, "tmpfix.pdf"),
      }),
    );
    writeFileSync(join(config.uploadsDir, "job_x_chapter.pdf"), "%PDF-1.4\n");
    const resultsImg = join(config.resultsDir, "job_x", "images");
    mkdirSync(resultsImg, { recursive: true });
    writeFileSync(join(resultsImg, "page_01_image_01.png"), "PNG");

    const removed = cleanupStrayTmpFiles();

    expect(removed).toBe(3);
    expect(existsSync(join(jobDir, "job.json.4242.tmp"))).toBe(false);
    expect(existsSync(join(config.uploadsDir, "chapter.pdf.77.tmp"))).toBe(false);
    expect(existsSync(join(config.resultsDir, "results.json.9.tmp"))).toBe(false);

    expect(readFileSync(join(jobDir, "job.json"), "utf-8")).toContain("job_tmpfix01");
    expect(readFileSync(join(config.uploadsDir, "job_x_chapter.pdf"), "utf-8")).toContain("%PDF");
    expect(existsSync(join(resultsImg, "page_01_image_01.png"))).toBe(true);

    // Leave no planted state behind (shared dirs — other files read them).
    rmSync(jobDir, { recursive: true, force: true });
    rmSync(join(config.uploadsDir, "job_x_chapter.pdf"), { force: true });
    rmSync(join(config.resultsDir, "job_x"), { recursive: true, force: true });
  });

  test("missing directories are not an error", () => {
    const saved = config.jobsDir;
    try {
      (config as unknown as { jobsDir: string }).jobsDir = "/tmp/captionx-does-not-exist-xyz";
      expect(cleanupStrayTmpFiles()).toBeGreaterThanOrEqual(0);
    } finally {
      (config as unknown as { jobsDir: string }).jobsDir = saved;
    }
  });
});
