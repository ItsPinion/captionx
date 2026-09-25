/**
 * §31 — user-facing error copy: friendly sentences, no stack traces.
 */
import { describe, expect, test } from "bun:test";

import {
  NO_CAPTION_MESSAGE,
  jobFailureDetail,
  jobFailureTitle,
  urlFailureMessage,
} from "@/lib/errors";

describe("error copy (§31)", () => {
  test("caption_not_found uses the plan's wording", () => {
    expect(NO_CAPTION_MESSAGE).toBe(
      "No caption could be confidently identified for this image",
    );
  });

  test("failed job leads with a friendly headline", () => {
    expect(jobFailureTitle()).toBe("Could not process this PDF");
  });

  test("failure detail is optional and never empty-string", () => {
    expect(jobFailureDetail(undefined)).toBeNull();
    expect(jobFailureDetail("")).toBeNull();
    expect(jobFailureDetail("   ")).toBeNull();
    expect(jobFailureDetail("pdf_parse: corrupt xref table")).toBe(
      "pdf_parse: corrupt xref table",
    );
  });

  test("URL failures read as 'Could not download PDF — <reason>'", () => {
    expect(urlFailureMessage("HTTP 404 Not Found")).toBe(
      "Could not download PDF — HTTP 404 Not Found",
    );
  });
});
