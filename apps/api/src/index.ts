import { Hono } from "hono";
import { cors } from "hono/cors";

/**
 * CaptionX API.
 *
 * Phase 1: health endpoint only — proves Hono + Bun + the Hono RPC contract.
 * Later phases add: /jobs/upload, /jobs/url, /jobs/:jobId, /jobs/:jobId/result,
 * /jobs/:jobId/json, /jobs/:jobId/csv, /jobs/:jobId/image/:filename,
 * /jobs/:jobId/images.zip (plan.md §21).
 */
const app = new Hono()
  .use("/*", cors())
  .get("/health", (c) =>
    c.json({
      status: "ok" as const,
      service: "captionx-api",
      time: new Date().toISOString(),
    }),
  );

/**
 * The inferred route type is the single source of truth for the Hono RPC
 * client used by the web app (plan.md §7.3).
 */
export type AppType = typeof app;

export default app;
