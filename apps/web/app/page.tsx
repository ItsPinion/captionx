"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  ScanText,
  ServerCog,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { APP_NAME, APP_SUBTITLE, type JobStatus } from "@captionx/shared";

/** Every value of the shared JobStatus union — rendered to prove the shared package imports at runtime. */
const JOB_STATUSES: JobStatus[] = [
  "queued",
  "processing",
  "completed",
  "failed",
];

export default function Home() {
  // Phase 1 acceptance check: a real call through the Hono RPC client.
  // (Dashboard itself is built in Phases 23–29; this page is replaced then.)
  const health = useQuery({
    queryKey: ["health"],
    refetchInterval: 5000,
    queryFn: async () => {
      const res = await apiClient.health.$get();
      if (!res.ok) {
        throw new Error(`API responded with HTTP ${res.status}`);
      }
      return res.json();
    },
  });

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanText className="size-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {APP_NAME}
            </h1>
            <p className="text-sm text-muted-foreground">{APP_SUBTITLE}</p>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ServerCog className="size-4 text-muted-foreground" />
              API status
            </CardTitle>
            <CardDescription>
              Live health check via Hono RPC (proxied through /api)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {health.isPending ? (
              <Badge variant="secondary" className="gap-1.5">
                <Loader2 className="animate-spin" />
                checking…
              </Badge>
            ) : health.isError ? (
              <Badge variant="destructive" className="gap-1.5">
                <XCircle />
                API unreachable
              </Badge>
            ) : (
              <Badge className="gap-1.5 bg-emerald-600 hover:bg-emerald-600">
                <CheckCircle2 />
                API OK · {health.data.status}
              </Badge>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Shared types loaded</CardTitle>
            <CardDescription>
              <code className="text-xs">@captionx/shared</code> imported at
              runtime
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {JOB_STATUSES.map((status) => (
              <Badge key={status} variant="outline">
                {status}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </section>

      <footer className="mt-auto border-t pt-4 text-xs text-muted-foreground">
        Phase 1 — monorepo bootstrap verified: Bun · Turborepo · Next.js ·
        Tailwind · shadcn/ui · Hono RPC · TanStack Query · shared types. Upload
        &amp; results dashboard arrives in later phases (see plan.md).
      </footer>
    </main>
  );
}
