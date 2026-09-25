import { describe, expect, spyOn, test } from "bun:test";
import { hc } from "hono/client";

/**
 * Regression (real-dashboard bug): the dashboard's upload must actually put
 * the files on the wire. hono's RPC client `{ form }` expects a PLAIN OBJECT
 * — it rebuilds the multipart body from `Object.entries(args.form)`, and a
 * FormData instance has no enumerable entries, so the old call shape sent an
 * EMPTY body and the API rejected it with 400 "no files uploaded" (only in
 * the browser — plain curl always worked).
 */
describe("upload form shape (hono RPC wire contract)", () => {
  test("plain-object form carries the files as multipart parts", async () => {
    const captured: { input: unknown; init?: RequestInit }[] = [];
    const spy = spyOn(globalThis, "fetch").mockImplementation(
      (async (input: RequestInfo | URL, init?: RequestInit) => {
        captured.push({ input, init });
        return new Response("{}", { status: 201 });
      }) as unknown as typeof fetch,
    );

    const client = hc("http://localhost/api");
    const file = new File([new Uint8Array(4)], "a.pdf", {
      type: "application/pdf",
    });
    await (
      client as unknown as {
        jobs: {
          upload: { $post: (args: unknown) => Promise<Response> };
        };
      }
    ).jobs.upload.$post({ form: { files: [file] } });

    spy.mockRestore();
    expect(captured).toHaveLength(1);

    // The hono client either passes (url, init) or a Request — handle both.
    let form: FormData;
    const { input, init } = captured[0];
    if (init?.body instanceof FormData) {
      form = init.body;
    } else {
      form = await (input as Request).formData();
    }
    const entries = [...form.entries()];
    expect(entries).toHaveLength(1);
    const [field, value] = entries[0] as unknown as [string, File];
    expect(field).toBe("files");
    expect(value.name).toBe("a.pdf");
    expect(value.size).toBe(4);
  });

  test("a FormData-instance form would arrive EMPTY (the trap itself)", async () => {
    const form = new FormData();
    form.append("files", new File([new Uint8Array(4)], "a.pdf"));
    // The exact mechanism that broke the dashboard: Object.entries sees none
    // of the appended parts.
    expect(Object.entries(form)).toHaveLength(0);
  });
});
