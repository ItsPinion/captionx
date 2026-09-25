"use client";

import {
  CheckCircle2,
  ChevronRight,
  Clock,
  Loader2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Job } from "@captionx/shared";

import type { JobsResponse } from "@/lib/hooks";

/**
 * §25 — queue visualization: current processing, waiting, completed, failed.
 * Intentionally simple: status groups, no job management controls.
 */
export function QueuePanel({
  data,
  selectedJobId,
  onSelectJob,
}: {
  data: JobsResponse | undefined;
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
}) {
  const jobs = data?.jobs ?? [];
  const processing = jobs.filter((j) => j.status === "processing");
  const waiting = jobs.filter((j) => j.status === "queued");
  const completed = jobs
    .filter((j) => j.status === "completed")
    .sort((a, b) => (b.finishedAt ?? b.createdAt).localeCompare(a.finishedAt ?? a.createdAt))
    .slice(0, 5);
  const failed = jobs
    .filter((j) => j.status === "failed")
    .sort((a, b) => (b.finishedAt ?? b.createdAt).localeCompare(a.finishedAt ?? a.createdAt))
    .slice(0, 5);

  const total = processing.length + waiting.length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Queue</CardTitle>
            <CardDescription>
              {total > 0
                ? `${total} job${total === 1 ? "" : "s"} in flight — one PDF at a time`
                : "idle — no jobs in flight"}
            </CardDescription>
          </div>
          {data?.current && (
            <Badge variant="secondary" className="font-mono text-[10px]">
              {data.current}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {jobs.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No jobs yet — submit PDFs above to get started.
          </p>
        )}

        {processing.map((job) => (
          <JobRow key={job.id} job={job}>
            <Progress value={66} className="h-1.5 animate-pulse" />
          </JobRow>
        ))}

        {waiting.length > 0 && (
          <Section title={`Waiting (${waiting.length})`}>
            {waiting.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </Section>
        )}

        {completed.length > 0 && (
          <Section title="Recently completed">
            {completed.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                action={
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectJob(job.id)}
                    className={selectedJobId === job.id ? "bg-muted" : undefined}
                  >
                    {selectedJobId === job.id ? "viewing" : "view results"}
                    <ChevronRight className="size-3.5" />
                  </Button>
                }
              />
            ))}
          </Section>
        )}

        {failed.length > 0 && (
          <Section title="Failed">
            {failed.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </Section>
        )}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
        {title}
      </p>
      {children}
    </div>
  );
}

function JobRow({ job, action, children }: {
  job: Job;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-md border px-3 py-2">
      <div className="flex items-center gap-2">
        <StatusIcon status={job.status} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">
          {job.filename}
        </span>
        <StatusBadge status={job.status} />
        {action}
      </div>
      {job.error && (
        <p className="text-destructive mt-1 truncate text-xs" title={job.error}>
          {job.error}
        </p>
      )}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}

function StatusIcon({ status }: { status: Job["status"] }) {
  if (status === "processing") {
    return <Loader2 className="size-4 shrink-0 animate-spin text-blue-600" />;
  }
  if (status === "completed") {
    return <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />;
  }
  if (status === "failed") {
    return <XCircle className="text-destructive size-4 shrink-0" />;
  }
  return <Clock className="text-muted-foreground size-4 shrink-0" />;
}

function StatusBadge({ status }: { status: Job["status"] }) {
  const map: Record<
    Job["status"],
    { label: string; className?: string }
  > = {
    processing: { label: "PROCESSING", className: "bg-blue-600 text-white" },
    queued: { label: "WAITING" },
    completed: { label: "COMPLETED", className: "bg-emerald-600 text-white" },
    failed: { label: "FAILED" },
  };
  const { label, className } = map[status];
  return (
    <Badge variant={className ? "default" : status === "failed" ? "destructive" : "secondary"} className={`shrink-0 text-[10px] ${className ?? ""}`}>
      {label}
    </Badge>
  );
}
