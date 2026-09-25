import app from "./index";
import { worker } from "./jobs/worker";
import { ensureDataDirs, resetDataDirs } from "./config";
import { cleanupStrayTmpFiles } from "./services/cleanup";
import { API_PORT } from "@captionx/shared";

const port = Number(process.env.API_PORT ?? API_PORT);

// Filesystem state + FIFO worker with §24 restart recovery.
// CAPTIONX_RESET_DATA=1 (the default `bun run dev`) starts from a clean
// slate; `bun run dev:keep` preserves uploads/jobs/results across restarts.
if (process.env.CAPTIONX_RESET_DATA === "1") {
  const cleared = resetDataDirs();
  console.log(`[captionx-api] reset data/ — removed ${cleared} entr(y|ies)`);
}
ensureDataDirs();
const swept = cleanupStrayTmpFiles(); // §36: crash-leftover atomic-write temps
if (swept > 0) {
  console.log(`[captionx-api] swept ${swept} stray .tmp file(s) from data/`);
}
worker.start();

// Bind to 0.0.0.0 so the sandbox preview proxy can reach the API.
Bun.serve({
  hostname: "0.0.0.0",
  port,
  fetch: app.fetch,
});

console.log(`[captionx-api] listening on http://0.0.0.0:${port}`);
