import { describe, expect, test } from "bun:test";
import { hc } from "hono/client";

import type { AppType } from "@captionx/api";

import "./helpers";
import { TINY_PDF_BYTES, makePdfFile } from "./helpers";
import app from "../src/index";

/**
 * Regression (real-dashboard bug): the browser uploads through hono's RPC
 * client, and `{ form }` must be a PLAIN OBJECT — the client rebuilds the
 * multipart body from `Object.entries(args.form)`, so a FormData instance
 * produces an EMPTY body and the API answers 400 "no files uploaded".
 * Plain fetch/curl always worked, which is why this only showed in the UI.
 */
describe("upload via hono RPC client (dashboard wire contract)", () => {
  // Route hc's fetch into the app in-process (build a real Request —
  // app.fetch expects a Request object, not (url, init) args).
  const client = hc<AppType>("http://localhost/", {
    fetch: (input, init) =>
      app.fetch(
        init ? new Request(input as string | URL, init) : (input as Request),
      ),
  });

  test("plain-object form carries the files (the shape hooks.ts uses)", async () => {
    const file = makePdfFile("chapter.pdf", TINY_PDF_BYTES);
    const res = await client.jobs.upload.$post({
      form: { files: [file] },
    } as never);
    expect(res.status).toBe(201);
    const body = (await res.json()) as {
      jobs: { filename: string }[];
      errors: unknown[];
    };
    expect(body.jobs).toHaveLength(1);
    expect(body.jobs[0].filename).toBe("chapter.pdf");
    expect(body.errors).toHaveLength(0);
  });

  test("a FormData-instance form arrives EMPTY and is rejected 400 (the trap, documented)", async () => {
    const form = new FormData();
    form.append("files", makePdfFile("x.pdf", TINY_PDF_BYTES));
    const res = await (
      client.jobs.upload as unknown as {
        $post: (args: unknown) => Promise<Response>;
      }
    ).$post({ form });
    expect(res.status).toBe(400);
    expect(((await res.json()) as { error: string }).error).toBe(
      "no files uploaded",
    );
  });
});
