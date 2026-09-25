import { describe, expect, test } from "bun:test";
import { mkdirSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

import "./helpers";
import { config, resetDataDirs } from "../src/config";

/** `resetDataDirs` — the CAPTIONX_RESET_DATA=1 boot behavior (fresh dev start). */
describe("resetDataDirs", () => {
  test("clears uploads/jobs/results but keeps .gitkeep placeholders", () => {
    // .gitkeep placeholders exist in the repo tree; mirror that here so the
    // preservation assertion is meaningful in the shared tmp dirs too.
    for (const dir of [config.uploadsDir, config.jobsDir, config.resultsDir]) {
      mkdirSync(dir, { recursive: true });
      writeFileSync(join(dir, ".gitkeep"), "");
    }
    // Plant state in all three trees.
    const jobDir = join(config.jobsDir, "job_reset01");
    mkdirSync(jobDir, { recursive: true });
    writeFileSync(join(jobDir, "job.json"), '{"id":"job_reset01"}');
    writeFileSync(join(config.uploadsDir, "job_reset01_ch.pdf"), "%PDF-1.4");
    const resDir = join(config.resultsDir, "job_reset01", "images");
    mkdirSync(resDir, { recursive: true });
    writeFileSync(join(config.resultsDir, "job_reset01", "results.csv"), "image\n");
    writeFileSync(join(resDir, "page_01_image_01.png"), "PNG");

    // resetDataDirs counts top-level entries per tree (uploads + jobs +
    // results), not recursive files — the two result files live inside the
    // results/job_reset01 dir. Exactly one planted entry per tree → 3 when
    // isolated; ≥3 also tolerates leftover entries from sibling test files.
    const removed = resetDataDirs();

    expect(removed).toBeGreaterThanOrEqual(3);
    expect(existsSync(jobDir)).toBe(false);
    expect(existsSync(join(config.uploadsDir, "job_reset01_ch.pdf"))).toBe(false);
    expect(existsSync(join(config.resultsDir, "job_reset01"))).toBe(false);

    // Dirs still exist (recreated) and .gitkeep placeholders survive.
    for (const dir of [config.uploadsDir, config.jobsDir, config.resultsDir]) {
      expect(existsSync(dir)).toBe(true);
      expect(existsSync(join(dir, ".gitkeep"))).toBe(true);
      expect(readdirSync(dir).filter((e) => e !== ".gitkeep")).toHaveLength(0);
    }
  });

  test("is idempotent on an already-empty tree", () => {
    resetDataDirs();
    expect(resetDataDirs()).toBe(0);
  });
});
