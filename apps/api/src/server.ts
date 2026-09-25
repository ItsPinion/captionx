import app from "./index";
import { worker } from "./jobs/worker";
import { ensureDataDirs } from "./config";
import { API_PORT } from "@captionx/shared";

const port = Number(process.env.API_PORT ?? API_PORT);

// Filesystem state + FIFO worker with §24 restart recovery.
ensureDataDirs();
worker.start();

// Bind to 0.0.0.0 so the sandbox preview proxy can reach the API.
Bun.serve({
  hostname: "0.0.0.0",
  port,
  fetch: app.fetch,
});

console.log(`[captionx-api] listening on http://0.0.0.0:${port}`);
