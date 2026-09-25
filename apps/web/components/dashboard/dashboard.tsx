"use client";

import { useState } from "react";

import { Header } from "@/components/dashboard/header";
import { InputPanel } from "@/components/dashboard/input-panel";
import { QueuePanel } from "@/components/dashboard/queue-panel";
import { ResultsPanel } from "@/components/dashboard/results-panel";
import { useJobs } from "@/lib/hooks";

/**
 * §24 — single-page dashboard:
 *   1. Header          (title + API health)
 *   2. Input mode      (PDF Files | PDF URLs tabs)
 *   3. Queue           (processing / waiting / completed / failed)
 *   4. Results         (table, selection, downloads)
 */
export function Dashboard() {
  const jobs = useJobs();
  const [pinnedJobId, setPinnedJobId] = useState<string | null>(null);

  // Effective selection is derived, not effect-synced: default to the most
  // recent completed job, keep the user's pin while it stays completed.
  const completed = (jobs.data?.jobs ?? [])
    .filter((j) => j.status === "completed")
    .sort((a, b) =>
      (b.finishedAt ?? b.createdAt).localeCompare(a.finishedAt ?? a.createdAt),
    );
  const selectedJobId =
    pinnedJobId && completed.some((j) => j.id === pinnedJobId)
      ? pinnedJobId
      : (completed[0]?.id ?? null);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10">
      <Header />
      <InputPanel />
      <QueuePanel
        data={jobs.data}
        selectedJobId={selectedJobId}
        onSelectJob={setPinnedJobId}
      />
      <ResultsPanel jobId={selectedJobId} />
      <footer className="text-muted-foreground mt-4 text-center text-xs">
        Extraction runs locally — PyMuPDF geometry first, PaddleOCR only as
        fallback. A missing caption is reported honestly as
        <span className="mx-1 font-mono">caption_not_found</span>
        rather than guessed.
      </footer>
    </main>
  );
}
