/// <reference types="bun" />
import { Hono } from "hono";
import { cors } from "hono/cors";

import type { ExtractionResult } from "@captionx/shared";

import { ensureDataDirs, paths } from "./config";
import { allJobs, loadJob } from "./jobs/store";
import { worker } from "./jobs/worker";
import { createUploadJobs } from "./services/uploads";
import { createUrlJobs, validateUrl } from "./services/url_download";
import {
  buildImagesZip,
  imageFilePath,
  listImageFiles,
  resultsCsvPath,
  resultsJsonPath,
} from "./services/results";

/**
 * CaptionX API (plan.md §21 route layout).
 *
 *   POST /jobs/upload              multipart PDFs → one job per PDF (§26)
 *   POST /jobs/url                 {urls: [...]}  → one job per URL (§19)
 *   GET  /jobs                     all jobs, FIFO order (§25 queue view)
 *   GET  /jobs/:jobId              one job
 *   GET  /jobs/:jobId/result       ExtractionResult JSON (authoritative)
 *   GET  /jobs/:jobId/json         results.json download
 *   GET  /jobs/:jobId/csv          results.csv download
 *   GET  /jobs/:jobId/image/:f     single image download
 *   GET  /jobs/:jobId/images.zip   all extracted images zipped (§28)
 *   GET  /health
 */

import type { Context } from "hono";

/**
 * NOTE: handler return paths must never be `any` — an `any`-returning
 * handler makes Hono's RPC client silently drop the route from its
 * inferred type map (learned the hard way; keep this helper typed).
 */
function notFound(c: Context, message: string) {
  return c.json({ error: message }, 404);
}

const app = new Hono()
  .use("/*", cors())
  .get("/health", (c) =>
    c.json({
      status: "ok" as const,
      service: "captionx-api",
      time: new Date().toISOString(),
    }),
  )
  .post("/jobs/upload", async (c) => {
    ensureDataDirs();
    let body: Record<string, string | File | (string | File)[]>;
    try {
      body = (await c.req.parseBody({ all: true })) as typeof body;
    } catch {
      return c.json({ error: "expected multipart/form-data with PDF files" }, 400);
    }
    const files: File[] = Object.values(body)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter((value): value is File => value instanceof File);

    if (files.length === 0) {
      return c.json({ error: "no files uploaded" }, 400);
    }
    const outcome = await createUploadJobs(files);
    return c.json({ jobs: outcome.jobs, errors: outcome.errors }, 201);
  })
  .post("/jobs/url", async (c) => {
    ensureDataDirs();
    let body: { urls?: unknown };
    try {
      body = await c.req.json();
    } catch {
      return c.json({ error: "expected JSON body {urls: string[]}" }, 400);
    }
    const urls = Array.isArray(body.urls) ? body.urls.filter((u): u is string => typeof u === "string") : [];
    if (urls.length === 0) {
      return c.json({ error: "urls must be a non-empty array of strings" }, 400);
    }
    if (urls.length > 20) {
      return c.json({ error: "at most 20 URLs per submission" }, 400);
    }
    const outcomes = await createUrlJobs(urls);
    const jobs = outcomes
      .filter((o) => o.ok && o.jobId)
      .map((o) => loadJob(o.jobId!))
      .filter((job) => job !== null);
    return c.json(
      {
        jobs,
        results: outcomes.map((o) => ({ url: o.url, ok: o.ok, error: o.error })),
      },
      201,
    );
  })
  .get("/jobs", (c) => {
    ensureDataDirs();
    return c.json({ jobs: allJobs(), current: worker.current?.id ?? null });
  })
  .get("/jobs/:jobId", (c) => {
    const job = loadJob(c.req.param("jobId"));
    if (!job) return notFound(c, "job not found");
    return c.json({ job });
  })
  .get("/jobs/:jobId/result", async (c) => {
    const jobId = c.req.param("jobId");
    const job = loadJob(jobId);
    if (!job) return notFound(c, "job not found");
    const jsonPath = resultsJsonPath(jobId);
    if (!jsonPath) {
      return c.json(
        { error: `result not available (job status: ${job.status})` },
        job.status === "completed" ? 500 : 409,
      );
    }
    try {
      const result = JSON.parse(await Bun.file(jsonPath).text()) as ExtractionResult;
      return c.json({ job, result });
    } catch {
      return c.json({ error: "stored result is unreadable" }, 500);
    }
  })
  .get("/jobs/:jobId/json", async (c) => {
    const jobId = c.req.param("jobId");
    if (!loadJob(jobId)) return notFound(c, "job not found");
    const jsonPath = resultsJsonPath(jobId);
    if (!jsonPath) return notFound(c, "result not available");
    const text = await Bun.file(jsonPath).text();
    return c.body(text, 200, {
      "content-type": "application/json; charset=utf-8",
      "content-disposition": `attachment; filename="${jobId}_results.json"`,
    });
  })
  .get("/jobs/:jobId/csv", async (c) => {
    const jobId = c.req.param("jobId");
    if (!loadJob(jobId)) return notFound(c, "job not found");
    const csvPath = resultsCsvPath(jobId);
    if (!csvPath) return notFound(c, "result not available");
    const text = await Bun.file(csvPath).text();
    return c.body(text, 200, {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="${jobId}_results.csv"`,
    });
  })
  .get("/jobs/:jobId/image/:filename", async (c) => {
    const jobId = c.req.param("jobId");
    if (!loadJob(jobId)) return notFound(c, "job not found");
    const imagePath = imageFilePath(jobId, c.req.param("filename"));
    if (!imagePath) return notFound(c, "image not found");
    const bytes = await Bun.file(imagePath).arrayBuffer();
    return c.body(bytes, 200, { "content-type": "image/png" });
  })
  .get("/jobs/:jobId/images.zip", (c) => {
    const jobId = c.req.param("jobId");
    if (!loadJob(jobId)) return notFound(c, "job not found");
    const images = listImageFiles(jobId);
    if (images.length === 0) return notFound(c, "no images available");
    const zip = buildImagesZip(jobId);
    return c.body(new Uint8Array(zip), 200, {
      "content-type": "application/zip",
      "content-disposition": `attachment; filename="${jobId}_images.zip"`,
    });
  });

/**
 * The inferred route type is the single source of truth for the Hono RPC
 * client used by the web app (plan.md §7.3).
 */
export type AppType = typeof app;

export default app;
