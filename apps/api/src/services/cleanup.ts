import { readdirSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";

import { config } from "../config";

/**
 * Storage cleanup (plan.md §36 "Temporary files").
 *
 * Uploads, job state and completed results are all kept (§36: originals for
 * debugging, enough state to understand processing). The only litter this
 * system can produce is atomic-write temp files (`*.tmp`) if the process
 * dies between write and rename — swept at boot, best-effort.
 */

/** Recurse `dir` up to `depth` levels, feeding every *.tmp file to `visit`. */
function walkTmpFiles(dir: string, depth: number, visit: (path: string) => void): void {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return; // directory may not exist yet — nothing to sweep
  }
  for (const name of entries) {
    const full = join(dir, name);
    let stat;
    try {
      stat = statSync(full);
    } catch {
      continue; // vanished mid-sweep
    }
    if (stat.isFile() && name.endsWith(".tmp")) {
      visit(full);
    } else if (stat.isDirectory() && depth > 0) {
      walkTmpFiles(full, depth - 1, visit);
    }
  }
}

/**
 * Delete stray `*.tmp` files under data/jobs, data/uploads and data/results
 * (depth 2 covers `data/jobs/<job>/job.json.<pid>.tmp`). Real state is never
 * touched — only files ending in `.tmp`.
 *
 * Returns how many files were removed.
 */
export function cleanupStrayTmpFiles(): number {
  let removed = 0;
  for (const dir of [config.jobsDir, config.uploadsDir, config.resultsDir]) {
    walkTmpFiles(dir, 1, (path) => {
      try {
        unlinkSync(path);
        removed += 1;
      } catch {
        // best effort — a half-written tmp that resists deletion is harmless
      }
    });
  }
  return removed;
}
