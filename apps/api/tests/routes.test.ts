import { describe, expect, test } from "bun:test";

import "./helpers";
import { TINY_PDF_BYTES, FAIL_PDF_BYTES, makePdfFile } from "./helpers";
import app from "../src/index";
import { waitForJob } from "../src/jobs/worker";

describe("API routes", () => {
  test("GET /health", async () => {
    const res = await app.request("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("upload → FIFO → completed + engine-failed jobs, full §21 result surface", async () => {
    const form = new FormData();
    form.append("files", makePdfFile("chapter.pdf", TINY_PDF_BYTES));
    // %PDF magic passes upload validation; the stub engine then fails on it.
    form.append("files", makePdfFile("broken.pdf", FAIL_PDF_BYTES));

    const upload = await app.request("/jobs/upload", { method: "POST", body: form });
    expect(upload.status).toBe(201);
    const { jobs, errors } = await upload.json();
    expect(jobs).toHaveLength(2);
    expect(errors).toHaveLength(0);

    const good = jobs[0].filename === "chapter.pdf" ? jobs[0] : jobs[1];
    const bad = jobs[0].filename === "chapter.pdf" ? jobs[1] : jobs[0];

    const doneGood = await waitForJob(good.id);
    expect(doneGood!.status).toBe("completed");
    expect(doneGood!.startedAt).toBeDefined();
    expect(doneGood!.finishedAt).toBeDefined();

    const doneBad = await waitForJob(bad.id);
    expect(doneBad!.status).toBe("failed");
    expect(doneBad!.error).toBe("pdf_parse: stub engine failure");

    // Queue view lists both, FIFO order.
    const list = await (await app.request("/jobs")).json();
    const ids = list.jobs.map((j: { id: string }) => j.id);
    expect(ids).toContain(good.id);
    expect(ids).toContain(bad.id);
    const createdAts = list.jobs.map((j: { createdAt: string }) => j.createdAt);
    const sorted = [...createdAts].sort((a: string, b: string) => a.localeCompare(b));
    expect(createdAts).toEqual(sorted);

    // §21 result surface (authoritative backend results, §29).
    const id = good.id;
    const result = await app.request(`/jobs/${id}/result`);
    expect(result.status).toBe(200);
    const { result: extraction } = await result.json();
    expect(extraction.document.filename).toBe("stub.pdf");
    expect(extraction.images[0].caption).toBe("Fig. 1.1: stub");
    expect(extraction.images[0].status).toBe("matched");

    const json = await app.request(`/jobs/${id}/json`);
    expect(json.status).toBe(200);
    expect(json.headers.get("content-type")).toContain("application/json");

    const csv = await app.request(`/jobs/${id}/csv`);
    expect(csv.status).toBe(200);
    expect(await csv.text()).toContain("native_text");

    const image = await app.request(`/jobs/${id}/image/stub_page_01_image_01.png`);
    expect(image.status).toBe(200);
    expect(image.headers.get("content-type")).toBe("image/png");

    const zip = await app.request(`/jobs/${id}/images.zip`);
    expect(zip.status).toBe(200);
    const zipBytes = new Uint8Array(await zip.arrayBuffer());
    expect(zipBytes[0]).toBe(0x50); // "P" of PK
    expect(zipBytes[1]).toBe(0x4b);

    // Failed job has no results yet → 409 until results exist.
    const badResult = await app.request(`/jobs/${bad.id}/result`);
    expect([409, 500]).toContain(badResult.status);
  });

  test("upload rejects non-PDF files with useful errors", async () => {
    const form = new FormData();
    form.append("files", new File(["plain text"], "notes.txt", { type: "text/plain" }));
    const res = await app.request("/jobs/upload", { method: "POST", body: form });
    expect(res.status).toBe(201);
    const { jobs, errors } = await res.json();
    expect(jobs).toHaveLength(0);
    expect(errors[0].reason).toContain("not a PDF");
  });

  test("unknown job → 404 on detail and result routes", async () => {
    const detail = await app.request("/jobs/job_nope");
    expect(detail.status).toBe(404);
    const result = await app.request("/jobs/job_nope/result");
    expect(result.status).toBe(404);
  });

  test("§30: malformed (traversal) job ids are rejected on every job route", async () => {
    // Route params are user-controlled; a jobId like ../../etc must never
    // reach the filesystem — every route answers 404.
    for (const path of [
      "/jobs/..%2F..%2Fetc",
      "/jobs/..%2F..%2Fetc/result",
      "/jobs/..%2F..%2Fetc/json",
      "/jobs/..%2F..%2Fetc/csv",
      "/jobs/..%2F..%2Fetc/images.zip",
      "/jobs/..%2F..%2Fetc/image/x.png",
    ]) {
      const res = await app.request(path);
      expect(res.status).toBe(404);
    }
  });

  test("§30: unknown job → 404 with useful error on download routes too", async () => {
    for (const path of [
      "/jobs/job_unknown123/json",
      "/jobs/job_unknown123/csv",
      "/jobs/job_unknown123/images.zip",
      "/jobs/job_unknown123/image/x.png",
    ]) {
      const res = await app.request(path);
      expect(res.status).toBe(404);
      const body = await res.json();
      expect(typeof body.error).toBe("string");
    }
  });

  test("§30: upload with no files → 400 with useful error", async () => {
    const res = await app.request("/jobs/upload", {
      method: "POST",
      body: new FormData(),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toContain("no files");
  });

  test("image route blocks path traversal", async () => {
    const form = new FormData();
    form.append("files", makePdfFile("trav.pdf", TINY_PDF_BYTES));
    const { jobs } = await (await app.request("/jobs/upload", { method: "POST", body: form })).json();
    await waitForJob(jobs[0].id);

    const evil = await app.request(`/jobs/${jobs[0].id}/image/..%2F..%2Fjob.json`);
    expect(evil.status).toBe(404);
  });

  test("URL flow: happy path via local HTTP server + per-URL errors (§19)", async () => {
    // A tiny origin server that serves a PDF, exactly like ncert.nic.in would.
    const server = Bun.serve({
      port: 0,
      fetch: (req) => {
        const url = new URL(req.url);
        if (url.pathname === "/real.pdf") {
          return new Response(TINY_PDF_BYTES as unknown as BodyInit, {
            headers: {
              "content-type": "application/pdf",
              "content-disposition": 'attachment; filename="real.pdf"',
            },
          });
        }
        if (url.pathname === "/notapdf") {
          return new Response("<html>hello</html>", { headers: { "content-type": "text/html" } });
        }
        return new Response("nope", { status: 404 });
      },
    });
    try {
      const base = `http://127.0.0.1:${server.port}`;
      const res = await app.request("/jobs/url", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          urls: [`${base}/real.pdf`, `${base}/notapdf`, `${base}/gone.pdf`, "ftp://x/y.pdf", "::not a url"],
        }),
      });
      expect(res.status).toBe(201);
      const { jobs, results } = await res.json();

      expect(jobs).toHaveLength(1);
      expect(jobs[0].source).toBe("url");
      expect(jobs[0].filename).toBe("real.pdf");

      expect(results).toHaveLength(5);
      expect(results[0].ok).toBe(true);
      expect(results[1].ok).toBe(false);
      expect(results[1].error).toContain("did not return a PDF");
      expect(results[2].ok).toBe(false);
      expect(results[2].error).toContain("404");
      expect(results[3].ok).toBe(false);
      expect(results[3].error).toContain("http(s)");
      expect(results[4].ok).toBe(false);
      expect(results[4].error).toContain("invalid URL syntax");

      // The URL job also runs the FIFO queue through to completion.
      const done = await waitForJob(jobs[0].id);
      expect(done!.status).toBe("completed");
      expect(done!.file).toContain("/uploads/");
    } finally {
      server.stop(true);
    }
  });

  test("URL route rejects empty and malformed bodies", async () => {
    const empty = await app.request("/jobs/url", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ urls: [] }),
    });
    expect(empty.status).toBe(400);

    const bad = await app.request("/jobs/url", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "not json",
    });
    expect(bad.status).toBe(400);
  });
});
