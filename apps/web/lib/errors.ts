/**
 * User-facing error copy (plan.md §31).
 *
 * Errors must be clear and human — never stack traces. Detailed technical
 * information stays in server logs and the job's status file; the UI leads
 * with a friendly sentence and may show the engine's one-line stage message
 * as secondary detail.
 */

/** §31 example copy for caption_not_found rows (plan §2.4 wording). */
export const NO_CAPTION_MESSAGE =
  "No caption could be confidently identified for this image";

/** Headline for a job that failed somewhere in the pipeline. */
export function jobFailureTitle(): string {
  return "Could not process this PDF";
}

/** Optional secondary detail line (engine stage + message). */
export function jobFailureDetail(error?: string): string | null {
  return error && error.trim().length > 0 ? error : null;
}

/** §31 example copy for a URL that could not be fetched. */
export function urlFailureMessage(error: string): string {
  return `Could not download PDF — ${error}`;
}
