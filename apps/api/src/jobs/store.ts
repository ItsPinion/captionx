import { mkdirSync, readFileSync, renameSync, existsSync, readdirSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

import type { Job, JobStatus, JobSource } from "@captionx/shared";

import { config, paths } from "../config";

/**
 * Filesystem job persistence (plan.md §16 / §24).
 *
 * Layout:
 *   data/jobs/<jobId>/job.json     — the job record (source of truth)
 *   data/jobs/<jobId>/status.json  — engine progress while processing (§30)
 *
 * Every mutation is persisted atomically (tmp + rename), so a crash leaves
 * the previous complete state on disk for restart recovery (§24).
 */

/** A stored job = the shared `Job` plus internal file bookkeeping. */
export interface StoredJob extends Job {
  /** Absolute path of the stored PDF in data/uploads/. */
  file: string;
}

/** Internal id generator: sortable by time, unique across processes. */
export function newJobId(): string {
  const time = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 6);
  return `job_${time}_${rand}`;
}

function atomicWriteJson(path: string, data: unknown): void {
  mkdirSync(join(path, ".."), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
  renameSync(tmp, path);
}

export function saveJob(job: StoredJob): void {
  atomicWriteJson(paths.jobFile(job.id), job);
}

export function loadJob(jobId: string): StoredJob | null {
  const file = paths.jobFile(jobId);
  if (!existsSync(file)) return null;
  try {
    return JSON.parse(readFileSync(file, "utf-8")) as StoredJob;
  } catch {
    return null;
  }
}

export function updateJobStatus(
  jobId: string,
  status: JobStatus,
  patch: Partial<Pick<Job, "startedAt" | "finishedAt" | "error">> = {},
): StoredJob | null {
  const job = loadJob(jobId);
  if (!job) return null;
  job.status = status;
  Object.assign(job, patch);
  saveJob(job);
  return job;
}

export function allJobs(): StoredJob[] {
  let entries: string[] = [];
  try {
    entries = readdirSync(config.jobsDir);
  } catch {
    return [];
  }
  const jobs: StoredJob[] = [];
  for (const entry of entries) {
    const job = loadJob(entry);
    if (job) jobs.push(job);
  }
  // FIFO order key (plan.md §23): oldest first.
  jobs.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return jobs;
}

/** Sanitize a client-supplied filename for storage. */
export function safeStorageName(filename: string, jobId: string): string {
  const base = basename(filename).replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^\.+/, "");
  const safe = base.length > 0 ? base.slice(-120) : "document.pdf";
  return `${jobId}_${safe}`;
}

/** Create + persist a queued job for an already-stored PDF. */
export function createJob(params: {
  filename: string;
  source: JobSource;
  file: string;
}): StoredJob {
  const job: StoredJob = {
    id: newJobId(),
    status: "queued",
    source: params.source,
    filename: params.filename,
    createdAt: new Date().toISOString(),
    file: params.file,
  };
  mkdirSync(paths.jobDir(job.id), { recursive: true });
  saveJob(job);
  return job;
}
