"use client";

import { useQuery } from "@tanstack/react-query";
import { ScanText, ServerCog } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import { APP_NAME, APP_SUBTITLE } from "@captionx/shared";

/** §24 Section 1 — header with a live API health indicator. */
export function Header() {
  const health = useQuery({
    queryKey: ["health"],
    refetchInterval: 10_000,
    queryFn: async () => {
      const res = await apiClient.health.$get();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
  });

  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="bg-primary text-primary-foreground flex size-10 items-center justify-center rounded-lg">
          <ScanText className="size-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{APP_NAME}</h1>
          <p className="text-muted-foreground text-sm">{APP_SUBTITLE}</p>
        </div>
      </div>
      <Badge variant={health.isError ? "destructive" : "secondary"} className="gap-1.5">
        <ServerCog className="size-3" />
        {health.isError
          ? "API offline"
          : health.isLoading
            ? "API…"
            : "API connected"}
      </Badge>
    </header>
  );
}
