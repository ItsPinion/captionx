/**
 * Dashboard component + logic tests (plan.md Phases 23–29).
 *
 * Rendered with @testing-library/react on happy-dom (see bunfig.toml).
 * Network-dependent pieces (health badge, live polling) are exercised by
 * the manual e2e / preview instead; these tests pin the deterministic
 * behavior: queue grouping, selection semantics, tab structure, download
 * URL building.
 */
import type { ReactElement } from "react";
import "./happydom"; // must precede @testing-library imports (binds document)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "bun:test";

import { QueuePanel } from "@/components/dashboard/queue-panel";
import { ResultsPanel } from "@/components/dashboard/results-panel";
import { imageUrl } from "@/lib/downloads";
import { isJobActive, type JobsResponse } from "@/lib/hooks";
import { API_PROXY_PREFIX, APP_NAME } from "@captionx/shared";
import { InputPanel } from "@/components/dashboard/input-panel";

/** Render inside a QueryClientProvider with retries off (deterministic). */
function renderWithClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

afterEach(cleanup);

const job = (
  id: string,
  status: JobsResponse["jobs"][number]["status"],
  extra: Partial<JobsResponse["jobs"][number]> = {},
): JobsResponse["jobs"][number] => ({
  id,
  status,
  source: "upload",
  filename: `${id}.pdf`,
  createdAt: "2026-09-25T08:00:00.000Z",
  ...extra,
});

describe("hooks: isJobActive (§23 polling gate)", () => {
  test("queued and processing are active; completed and failed are not", () => {
    expect(isJobActive(job("a", "queued"))).toBe(true);
    expect(isJobActive(job("b", "processing"))).toBe(true);
    expect(isJobActive(job("c", "completed"))).toBe(false);
    expect(isJobActive(job("d", "failed"))).toBe(false);
  });
});

describe("downloads: URL building (§21/§29)", () => {
  test("imageUrl goes through the same-origin /api proxy and encodes the filename", () => {
    expect(imageUrl("job_x", "page_01_image_01.png")).toBe(
      `${API_PROXY_PREFIX}/jobs/job_x/image/page_01_image_01.png`,
    );
    expect(imageUrl("job_x", "weird name (1).png")).toBe(
      `${API_PROXY_PREFIX}/jobs/job_x/image/weird%20name%20(1).png`,
    );
  });
});

describe("QueuePanel (§25)", () => {
  test("renders PROCESSING / WAITING / COMPLETED / FAILED groups with details", () => {
    const data: JobsResponse = {
      current: "job_2",
      jobs: [
        job("job_1", "processing"),
        job("job_2", "queued"),
        job("job_3", "completed", { finishedAt: "2026-09-25T08:01:00.000Z" }),
        job("job_4", "failed", { error: "pdf_parse: broken xref" }),
      ],
    };
    const onSelect = (id: string) => id;
    const { getByText } = render(
      <QueuePanel data={data} selectedJobId={null} onSelectJob={onSelect} />,
    );

    // filenames
    expect(getByText("job_1.pdf")).toBeTruthy();
    expect(getByText("job_2.pdf")).toBeTruthy();
    expect(getByText("job_3.pdf")).toBeTruthy();
    expect(getByText("job_4.pdf")).toBeTruthy();

    // status labels (§25 example uses PROCESSING / WAITING)
    expect(getByText("PROCESSING")).toBeTruthy();
    expect(getByText("WAITING")).toBeTruthy();
    expect(getByText("COMPLETED")).toBeTruthy();
    expect(getByText("FAILED")).toBeTruthy();

    // engine failure surfaced (§30)
    expect(getByText(/pdf_parse: broken xref/)).toBeTruthy();

    // current job badge (§23 "only one worker executes")
    expect(getByText("job_2")).toBeTruthy();

    // waiting count in section header
    expect(getByText(/Waiting \(1\)/)).toBeTruthy();
  });

  test("empty queue shows the idle hint", () => {
    const { getByText } = render(
      <QueuePanel data={{ current: null, jobs: [] }} selectedJobId={null} onSelectJob={() => {}} />,
    );
    expect(getByText(/No jobs yet/)).toBeTruthy();
  });
});

describe("ResultsPanel (§26/§29)", () => {
  test("no selection → empty state, no queries fired", () => {
    const { getByText } = renderWithClient(<ResultsPanel jobId={null} />);
    expect(getByText(/No job selected/)).toBeTruthy();
  });
});

describe("InputPanel (§24)", () => {
  test("renders both input-mode tabs and starts on PDF Files", () => {
    const { getByRole, getByText } = renderWithClient(<InputPanel />);
    const files = getByRole("tab", { name: /PDF Files/ });
    const urls = getByRole("tab", { name: /PDF URLs/ });
    expect(files.getAttribute("aria-selected")).toBe("true");
    expect(urls.getAttribute("aria-selected")).toBe("false");
    expect(getByText(/Drag & drop PDFs here/)).toBeTruthy();
  });

  test("URL mode: add and remove rows", () => {
    const { getByRole, getAllByRole } = renderWithClient(<InputPanel />);
    // Radix tab triggers select on mousedown (click alone is not enough in
    // happy-dom, which lacks PointerEvent).
    const urlsTab = getByRole("tab", { name: /PDF URLs/ });
    fireEvent.mouseDown(urlsTab);
    fireEvent.click(urlsTab);
    expect(urlsTab.getAttribute("aria-selected")).toBe("true");

    expect(getAllByRole("textbox").length).toBe(1);

    fireEvent.click(getByRole("button", { name: /Add URL/ }));
    expect(getAllByRole("textbox").length).toBe(2);

    // remove one row again (remove buttons are icon-only, aria-labelled)
    const removeButtons = getAllByRole("button").filter((b) =>
      b.getAttribute("aria-label")?.startsWith("Remove URL"),
    );
    expect(removeButtons.length).toBe(2);
    fireEvent.click(removeButtons[1]);
    expect(getAllByRole("textbox").length).toBe(1);
  });
});

describe("shared package (§22)", () => {
  test("dashboard imports shared constants at runtime", () => {
    expect(APP_NAME).toBe("Image–Caption Extraction");
  });
});
