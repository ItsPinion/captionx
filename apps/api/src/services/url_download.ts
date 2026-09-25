import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { config } from "../config";
import { createJob, saveJob, safeStorageName } from "../jobs/store";
import { worker } from "../jobs/worker";
import { storedFileIsPdf } from "./uploads";

/**
 * URL input flow (plan.md §19).
 *
 * For each URL: validate syntax → HTTP request → verify success → verify the
 * content is plausibly a PDF → save to data/uploads/ → create a job → FIFO.
 *
 * The URL is NEVER passed to Python — Hono downloads; the engine only ever
 * reads local files (§19 "Do not").
 */

export interface UrlJobOutcome {
  url: string;
  ok: boolean;
  jobId?: string;
  error?: string;
}

export function validateUrl(raw: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return "invalid URL syntax";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "only http(s) URLs are supported";
  }
  return null;
}

async function downloadPdf(url: string): Promise<{ bytes: Uint8Array; filename: string }> {
  const response = await fetch(url, {
    redirect: "follow",
    signal: AbortSignal.timeout(config.urlDownloadTimeoutMs),
    headers: { "user-agent": "CaptionX/0.1 (+NCERT pdf fetcher)" },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`.trim());
  }
  const declared = Number(response.headers.get("content-length") ?? 0);
  if (declared > config.maxPdfBytes) {
    throw new Error(`content too large (limit ${config.maxPdfBytes} bytes)`);
  }
  const buffer = new Uint8Array(await response.arrayBuffer());
  if (buffer.byteLength > config.maxPdfBytes) {
    throw new Error(`content too large (limit ${config.maxPdfBytes} bytes)`);
  }
  const decoded = new TextDecoder().decode(buffer.subarray(0, 5));
  if (decoded !== "%PDF-") {
    throw new Error("URL did not return a PDF (missing %PDF- header)");
  }

  // Filename: content-disposition basename, else URL basename, else derived.
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^\";]+)"?/i);
  const fromHeader = match?.[1];
  const fromUrl = decodeURIComponent(new URL(url).pathname.split("/").pop() ?? "");
  const filename = (fromHeader || fromUrl || "download.pdf").trim() || "download.pdf";
  return { bytes: buffer, filename };
}

export async function createUrlJobs(urls: string[]): Promise<UrlJobOutcome[]> {
  const outcomes: UrlJobOutcome[] = [];
  for (const url of urls) {
    const syntaxError = validateUrl(url);
    if (syntaxError) {
      outcomes.push({ url, ok: false, error: syntaxError });
      continue;
    }
    try {
      const { bytes, filename } = await downloadPdf(url);
      const job = createJob({ filename, source: "url", file: "" });
      mkdirSync(config.uploadsDir, { recursive: true });
      const target = join(config.uploadsDir, safeStorageName(filename, job.id));
      await Bun.write(target, bytes);
      job.file = target;
      if (!storedFileIsPdf(job.file)) {
        throw new Error("stored file failed PDF verification");
      }
      saveJob(job);
      outcomes.push({ url, ok: true, jobId: job.id });
      worker.enqueue(job);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.name === "TimeoutError" || error.name === "AbortError"
            ? `download timed out after ${config.urlDownloadTimeoutMs} ms`
            : error.message
          : String(error);
      outcomes.push({ url, ok: false, error: message });
    }
  }
  return outcomes;
}
