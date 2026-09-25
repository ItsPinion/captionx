import { describe, expect, test } from "bun:test";

import "./helpers"; // env setup must run before config-dependent imports
import { createJob, allJobs, loadJob, safeStorageName, updateJobStatus } from "../src/jobs/store";
import { paths } from "../src/config";

describe("job store", () => {
  test("create → load round-trip", () => {
    const job = createJob({ filename: "physics.pdf", source: "upload", file: "/tmp/x.pdf" });
    const loaded = loadJob(job.id);
    expect(loaded).not.toBeNull();
    expect(loaded!.filename).toBe("physics.pdf");
    expect(loaded!.status).toBe("queued");
    expect(loaded!.source).toBe("upload");
    expect(loaded!.file).toBe("/tmp/x.pdf");
  });

  test("status update persists atomically", () => {
    const job = createJob({ filename: "a.pdf", source: "url", file: "/tmp/a.pdf" });
    updateJobStatus(job.id, "processing", { startedAt: "2026-01-01T00:00:00Z" });
    const reloaded = loadJob(job.id)!;
    expect(reloaded.status).toBe("processing");
    expect(reloaded.startedAt).toBe("2026-01-01T00:00:00Z");
    updateJobStatus(job.id, "failed", { error: "boom" });
    expect(loadJob(job.id)!.status).toBe("failed");
    expect(loadJob(job.id)!.error).toBe("boom");
  });

  test("allJobs sorted by createdAt (FIFO order key)", async () => {
    const a = createJob({ filename: "a.pdf", source: "upload", file: "/tmp/a.pdf" });
    await new Promise((r) => setTimeout(r, 5));
    const b = createJob({ filename: "b.pdf", source: "upload", file: "/tmp/b.pdf" });
    const jobs = allJobs();
    const ia = jobs.findIndex((j) => j.id === a.id);
    const ib = jobs.findIndex((j) => j.id === b.id);
    expect(ia).toBeLessThan(ib);
  });

  test("loadJob on missing id returns null", () => {
    expect(loadJob("job_nonexistent")).toBeNull();
  });

  test("safeStorageName strips path parts and odd chars", () => {
    expect(safeStorageName("../../etc/passwd", "j1")).toBe("j1_passwd");
    expect(safeStorageName("my book: ch 1.pdf", "j2")).toBe("j2_my_book_ch_1.pdf");
    expect(safeStorageName("", "j3")).toBe("j3_document.pdf");
  });

  test("job file lives at data/jobs/<id>/job.json", () => {
    const job = createJob({ filename: "x.pdf", source: "upload", file: "/tmp/x.pdf" });
    expect(paths.jobFile(job.id)).toContain(job.id);
  });
});
