import { existsSync, readFileSync } from "node:fs";

import type { StoredJob } from "./store";
import { allJobs, saveJob, updateJobStatus } from "./store";
import { config, paths } from "../config";

/**
 * Global FIFO worker (plan.md §23 / §24).
 *
 * Exactly ONE PDF is processed at a time, across all users:
 *
 *   queued → processing → completed
 *                      ↘ failed
 *
 * Queue order is `createdAt`, oldest first. On startup, `recover()`
 * implements §24: interrupted `processing` jobs return to `queued`, then
 * the FIFO resumes. Completed/failed jobs are never touched.
 */

export class FifoWorker {
  private queue: StoredJob[] = [];
  private running = false;
  private started = false;
  /** The job currently being processed, if any. */
  current: StoredJob | null = null;

  /** §24: scan data/jobs and re-queue unfinished work. */
  recover(): number {
    const jobs = allJobs().filter(
      (job) => job.status === "queued" || job.status === "processing",
    );
    for (const job of jobs) {
      const requeued: StoredJob = { ...job, status: "queued" };
      if (job.status === "processing") {
        // interrupted mid-flight → back to queued (§24)
        saveJob(requeued);
      }
      this.queue.push(requeued);
    }
    this.queue.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    return jobs.length;
  }

  /** §23: "if worker is busy: enqueue, else start immediately". */
  enqueue(job: StoredJob): void {
    this.queue.push(job);
    this.queue.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    void this.pump();
  }

  /** Boot once per process; further calls are no-ops. */
  start(): void {
    if (this.started) return;
    this.started = true;
    this.recover();
    // Recovered (re-queued) work must actually start draining (§23/§24).
    void this.pump();
  }

  private async pump(): Promise<void> {
    if (this.running) return;
    this.running = true;
    try {
      while (this.queue.length > 0) {
        const job = this.queue.shift()!;
        this.current = job;
        try {
          await this.process(job);
        } catch (error) {
          // Engine crashed / could not spawn: record failure, keep pumping.
          const message = error instanceof Error ? error.message : String(error);
          updateJobStatus(job.id, "failed", {
            finishedAt: new Date().toISOString(),
            error: `worker error: ${message}`,
          });
        }
        this.current = null;
      }
    } finally {
      this.running = false;
    }
  }

  private async process(job: StoredJob): Promise<void> {
    updateJobStatus(job.id, "processing", { startedAt: new Date().toISOString() });

    if (!existsSync(config.pythonBin)) {
      updateJobStatus(job.id, "failed", {
        finishedAt: new Date().toISOString(),
        error: `Python interpreter not found: ${config.pythonBin} (run extraction/setup.sh)`,
      });
      return;
    }
    if (!existsSync(job.file)) {
      updateJobStatus(job.id, "failed", {
        finishedAt: new Date().toISOString(),
        error: `stored PDF missing: ${job.file}`,
      });
      return;
    }

    const proc = Bun.spawn({
      cmd: [
        config.pythonBin,
        config.mainScript,
        "--job-id",
        job.id,
        "--input",
        job.file,
        "--output",
        paths.resultDir(job.id),
        "--status",
        paths.statusFile(job.id),
        "--source",
        job.source,
        "--filename",
        job.filename,
      ],
      stdout: "pipe",
      stderr: "pipe",
    });

    const exitCode = await proc.exited;

    if (exitCode === 0) {
      updateJobStatus(job.id, "completed", { finishedAt: new Date().toISOString() });
      return;
    }

    // Pull the failing stage + message out of the engine status file (§30).
    let error = `extraction failed with exit code ${exitCode}`;
    try {
      const status = JSON.parse(readFileSync(paths.statusFile(job.id), "utf-8")) as {
        stage?: string;
        message?: string;
      };
      if (status.stage || status.message) {
        error = `${status.stage ?? "processing"}: ${status.message ?? error}`;
      }
    } catch {
      // keep the default message
    }
    updateJobStatus(job.id, "failed", {
      finishedAt: new Date().toISOString(),
      error,
    });
  }
}

/** Process-wide singleton (one worker per API process, §23). */
export const worker = new FifoWorker();

/** Wait until a job leaves queued/processing (test helper). */
export async function waitForJob(jobId: string, timeoutMs = 30_000): Promise<StoredJob | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = (await import("./store")).loadJob(jobId);
    if (job && job.status !== "queued" && job.status !== "processing") return job;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return (await import("./store")).loadJob(jobId);
}
