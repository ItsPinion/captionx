"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Job } from "@captionx/shared";

import { apiClient } from "@/lib/api-client";

/**
 * TanStack Query data layer (plan.md §23).
 *
 * Queries:   jobs queue, single job, job result.
 * Mutations: submit uploads, submit URLs.
 * Polling:   1.5 s while anything is queued/processing, stopped otherwise
 *            ("do not poll unnecessarily after completion").
 */

export interface JobsResponse {
  jobs: Job[];
  current: string | null;
}

export function isJobActive(job: Job): boolean {
  return job.status === "queued" || job.status === "processing";
}

/** FIFO queue view (§25). Polls only while at least one job is active. */
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: async (): Promise<JobsResponse> => {
      const res = await apiClient.jobs.$get();
      if (!res.ok) {
        throw new Error(`queue request failed (HTTP ${res.status})`);
      }
      return res.json();
    },
    refetchInterval: (query) => {
      const data = query.state.data as JobsResponse | undefined;
      return data?.jobs.some(isJobActive) ? 1_500 : false;
    },
  });
}

/** One job's metadata — polled while queued/processing (§23). */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: jobId !== null,
    queryFn: async (): Promise<Job> => {
      const res = await apiClient.jobs[":jobId"].$get({
        param: { jobId: jobId! },
      });
      if (!res.ok) {
        throw new Error(`job request failed (HTTP ${res.status})`);
      }
      const body = await res.json();
      return body.job;
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      return job && isJobActive(job) ? 1_500 : false;
    },
  });
}

export interface ResultResponse {
  job: Job;
  result: import("@captionx/shared").ExtractionResult;
}

/**
 * Authoritative backend result (§29). Enabled only once the job has
 * completed; fetched once — results never change after completion.
 */
export function useJobResult(jobId: string | null, completed: boolean) {
  return useQuery({
    queryKey: ["result", jobId],
    enabled: jobId !== null && completed,
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async (): Promise<ResultResponse> => {
      const res = await apiClient.jobs[":jobId"].result.$get({
        param: { jobId: jobId! },
      });
      if (!res.ok) {
        throw new Error(`result request failed (HTTP ${res.status})`);
      }
      return res.json();
    },
  });
}

export interface UploadOutcome {
  jobs: Job[];
  errors: { filename: string; reason: string }[];
}

/** Submit local PDFs (multipart, §26) — one job per PDF. */
export function useSubmitUploads() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]): Promise<UploadOutcome> => {
      const form = new FormData();
      for (const file of files) {
        form.append("files", file, file.name);
      }
      const res = await apiClient.jobs.upload.$post({ form });
      const body = (await res.json()) as UploadOutcome | { error: string };
      if (!res.ok) {
        throw new Error(
          ("error" in body && body.error) || `upload failed (HTTP ${res.status})`,
        );
      }
      return body as UploadOutcome;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export interface UrlOutcome {
  jobs: Job[];
  results: { url: string; ok: boolean; error?: string }[];
}

/** Submit PDF URLs (§19) — Hono downloads; Python never sees a URL. */
export function useSubmitUrls() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (urls: string[]): Promise<UrlOutcome> => {
      const res = await apiClient.jobs.url.$post({ json: { urls } });
      const body = (await res.json()) as UrlOutcome | { error: string };
      if (!res.ok) {
        throw new Error(
          ("error" in body && body.error) || `URL submission failed (HTTP ${res.status})`,
        );
      }
      return body as UrlOutcome;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
