/**
 * One-off runtime-state reset: clears data/uploads, data/jobs, data/results
 * (results.csv / results.json / images / job.json / uploaded PDFs), keeping
 * the .gitkeep placeholders. Same clearing the API boot does when
 * CAPTIONX_RESET_DATA=1 (the default `bun run dev`).
 *
 *   bun run reset          # from the repo root
 */
import { resetDataDirs } from "../src/config";

const removed = resetDataDirs();
console.log(`[captionx] data/ reset — removed ${removed} entr(y|ies)`);
