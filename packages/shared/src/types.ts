/**
 * Shared domain types for CaptionX.
 *
 * This package is the source of truth for the job/result shapes exchanged
 * between the web dashboard and the Hono API.
 *
 * Notes (plan.md §7.3 / §22):
 * - The Hono RPC contract lives in `@captionx/api` (its route types are the
 *   source of truth for endpoint typing) — it is NOT duplicated here.
 * - Python keeps its own independent dataclasses; do not mirror them here.
 */

/** Lifecycle of a single PDF job in the global FIFO queue. */
export type JobStatus = "queued" | "processing" | "completed" | "failed";

/** Outcome of the image → caption mapping for one extracted image. */
export type ImageStatus = "matched" | "caption_not_found";

/** How a PDF entered the system. */
export type JobSource = "upload" | "url";

/** Pipeline technique that produced the mapping (plan.md §13). */
export type MatchMethod =
  | "native_text"
  | "ocr"
  | "fallback"
  | "no_reliable_candidate";

/** Metadata about the processed document. */
export interface DocumentMetadata {
  filename: string;
  source: JobSource;
  page_count: number;
}

/** A single PDF processing job. */
export interface Job {
  id: string;
  status: JobStatus;
  source: JobSource;
  filename: string;
  /** ISO 8601 timestamp — FIFO order key. */
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  /** Human-readable failure reason, present when status = "failed". */
  error?: string;
}

/** Result for one extracted image occurrence (plan.md §13 / §19). */
export interface ImageResult {
  /** Image filename relative to the result directory. */
  image: string;
  /** 1-based page number. */
  page: number;
  /** Exact caption text, or null when status = "caption_not_found". */
  caption: string | null;
  /** 0..1 mapping confidence. */
  confidence: number;
  status: ImageStatus;
  method: MatchMethod;
  /** PP-DocLayout-S layout evidence (final plan §11) — present when the
   *  page was analyzed and relevant regions overlap this image. */
  layout?: {
    figure?: { label: string; confidence: number; bbox: number[] } | null;
    caption_region?: { label: string; confidence: number; bbox: number[] } | null;
  };
}

/** Full extraction output for one document. */
export interface ExtractionResult {
  document: DocumentMetadata;
  images: ImageResult[];
}
