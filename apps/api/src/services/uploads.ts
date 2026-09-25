import { mkdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { config } from "../config";
import { createJob, saveJob, safeStorageName } from "../jobs/store";
import { worker } from "../jobs/worker";

/**
 * File upload flow (plan.md §26):
 *   multipart/form-data → Hono → validate PDF → save to data/uploads/
 *   → create one job per PDF → FIFO queue.
 */

const PDF_MAGIC = "%PDF-";

/** Cheap PDF sniff: .pdf extension plus %PDF- magic on the first bytes. */
export async function looksLikePdf(file: File): Promise<boolean> {
  if (!file.name.toLowerCase().endsWith(".pdf")) return false;
  // (full read is bounded by maxPdfBytes; avoids lib-specific Blob.slice typing)
  const head = new Uint8Array(await file.arrayBuffer()).subarray(0, 5);
  return new TextDecoder().decode(head) === PDF_MAGIC;
}

export function storedFileIsPdf(path: string): boolean {
  return existsSync(path) && new TextDecoder().decode(readFileSync(path).subarray(0, 5)) === PDF_MAGIC;
}

async function storeUpload(file: File, jobId: string): Promise<string> {
  const stored = safeStorageName(file.name, jobId);
  const target = join(config.uploadsDir, stored);
  mkdirSync(config.uploadsDir, { recursive: true });
  await Bun.write(target, file);
  return target;
}

export interface UploadOutcome {
  jobs: Awaited<ReturnType<typeof createJob>>[];
  errors: { filename: string; reason: string }[];
}

export async function createUploadJobs(files: File[]): Promise<UploadOutcome> {
  const errors: UploadOutcome["errors"] = [];
  const jobs: UploadOutcome["jobs"] = [];

  for (const file of files) {
    if (!(await looksLikePdf(file))) {
      errors.push({
        filename: file.name || "(unnamed file)",
        reason: "not a PDF (must have a .pdf extension and %PDF- content)",
      });
      continue;
    }
    if (file.size > config.maxPdfBytes) {
      errors.push({
        filename: file.name,
        reason: `file too large (limit ${config.maxPdfBytes} bytes)`,
      });
      continue;
    }
    const job = createJob({ filename: file.name, source: "upload", file: "" });
    job.file = await storeUpload(file, job.id);
    if (!storedFileIsPdf(job.file)) {
      errors.push({ filename: file.name, reason: "stored file failed PDF verification" });
      continue;
    }
    saveJob(job);
    jobs.push(job);
    worker.enqueue(job);
  }
  return { jobs, errors };
}
