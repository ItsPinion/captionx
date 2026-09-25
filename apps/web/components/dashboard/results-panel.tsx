"use client";

import { useMemo, useState } from "react";
import {
  Download,
  FileJson,
  FileSpreadsheet,
  FileArchive,
  ImageIcon,
  Loader2,
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  downloadCsv,
  downloadImage,
  downloadImagesZip,
  downloadJson,
  downloadSelectedAsZip,
  imageUrl,
} from "@/lib/downloads";
import { useJob, useJobResult } from "@/lib/hooks";
import type { ImageResult } from "@captionx/shared";

/**
 * §26 results table + §27 selection + §28/§29 downloads for one completed
 * (or in-flight) job. All data comes from the backend's authoritative
 * result — the frontend never reconstructs it (§29).
 */
export function ResultsPanel({ jobId }: { jobId: string | null }) {
  const job = useJob(jobId);
  const status = job.data?.status;
  const result = useJobResult(jobId, status === "completed");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
        <CardDescription>
          {jobId
            ? job.data?.filename ?? jobId
            : "select a completed job — try the queue panel"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!jobId && (
          <EmptyState text="No job selected yet. Completed jobs appear here — pick one from the queue above." />
        )}
        {jobId && job.isLoading && <EmptyState text="Loading job…" />}
        {jobId && job.isError && (
          <EmptyState text={`Failed to load job: ${job.error.message}`} />
        )}
        {jobId && (status === "queued" || status === "processing") && (
          <div className="flex flex-col items-center gap-3 py-10">
            <Loader2 className="text-muted-foreground size-6 animate-spin" />
            <p className="text-muted-foreground text-sm">
              {status === "queued" ? "Waiting in queue…" : "Processing…"}
            </p>
            <Progress value={66} className="max-w-xs animate-pulse" />
          </div>
        )}
        {jobId && status === "failed" && (
          <EmptyState text={`This job failed: ${job.data?.error ?? "unknown error"}`} />
        )}
        {status === "completed" &&
          (result.isLoading ? (
            <EmptyState text="Loading results…" />
          ) : result.isError ? (
            <EmptyState text={`Failed to load results: ${result.error.message}`} />
          ) : result.data ? (
            <ResultTable jobId={jobId!} images={result.data.result.images} />
          ) : null)}
      </CardContent>
    </Card>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="text-muted-foreground flex items-center justify-center rounded-md border border-dashed px-6 py-12 text-center text-sm">
      {text}
    </div>
  );
}

function ResultTable({ jobId, images }: { jobId: string; images: ImageResult[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<ImageResult | null>(null);
  const [zipPending, setZipPending] = useState(false);
  const [zipError, setZipError] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState<string>("");

  // Clear selection when switching jobs or when a result loads — derived
  // reset during render (React's recommended "adjust state on prop change"
  // pattern; no effect needed).
  const key = `${jobId}:${images.map((i) => i.image).join(",")}`;
  if (key !== resetKey) {
    setResetKey(key);
    setSelected(new Set());
    setZipError(null);
  }

  const matched = useMemo(
    () => images.filter((i) => i.status === "matched").length,
    [images],
  );
  const allSelected = selected.size === images.length && images.length > 0;

  const toggle = (filename: string, on: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(filename);
      else next.delete(filename);
      return next;
    });
  };

  const toggleAll = (on: boolean) => {
    setSelected(on ? new Set(images.map((i) => i.image)) : new Set());
  };

  const downloadSelected = async () => {
    setZipPending(true);
    setZipError(null);
    try {
      await downloadSelectedAsZip(
        jobId,
        images[0]?.image.split("_page_")[0] ?? jobId,
        images.filter((i) => selected.has(i.image)).map((i) => i.image),
      );
    } catch (error) {
      setZipError(error instanceof Error ? error.message : String(error));
    } finally {
      setZipPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => downloadJson(jobId)}>
          <FileJson className="size-4" /> Download JSON
        </Button>
        <Button variant="outline" size="sm" onClick={() => downloadCsv(jobId)}>
          <FileSpreadsheet className="size-4" /> Download CSV
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => downloadImagesZip(jobId)}
        >
          <FileArchive className="size-4" /> All images (.zip)
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={selected.size === 0 || zipPending}
          onClick={downloadSelected}
        >
          {zipPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Download className="size-4" />
          )}
          Download selected ({selected.size})
        </Button>
        {zipError && <span className="text-destructive text-xs">{zipError}</span>}
      </div>

      <p className="text-muted-foreground text-sm">
        {images.length} image{images.length === 1 ? "" : "s"} ·{" "}
        <span className="text-emerald-700 dark:text-emerald-400">
          {matched} matched
        </span>{" "}
        ·{" "}
        <span className="text-amber-700 dark:text-amber-400">
          {images.length - matched} caption_not_found
        </span>
      </p>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  aria-label="Select all images"
                  checked={allSelected}
                  onCheckedChange={(on) => toggleAll(on === true)}
                  disabled={images.length === 0}
                />
              </TableHead>
              <TableHead className="w-14">Image</TableHead>
              <TableHead className="w-14">Page</TableHead>
              <TableHead>Caption</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Method</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {images.map((image) => (
              <TableRow key={image.image}>
                <TableCell>
                  <Checkbox
                    aria-label={`Select ${image.image}`}
                    checked={selected.has(image.image)}
                    onCheckedChange={(on) => toggle(image.image, on === true)}
                  />
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    aria-label={`Preview ${image.image}`}
                    onClick={() => setPreview(image)}
                    className="focus-visible:ring-ring block overflow-hidden rounded border"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageUrl(jobId, image.image)}
                      alt={image.caption ?? image.image}
                      className="h-9 w-12 object-cover"
                      loading="lazy"
                    />
                  </button>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {image.page}
                </TableCell>
                <TableCell className="max-w-[28rem]">
                  <span
                    className={image.caption ? "" : "text-muted-foreground italic"}
                    title={image.caption ?? undefined}
                  >
                    {image.caption ?? "—"}
                  </span>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {(image.confidence * 100).toFixed(1)}%
                </TableCell>
                <TableCell>
                  {image.status === "matched" ? (
                    <Badge className="bg-emerald-600 text-white">matched</Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-amber-600 text-amber-700 dark:text-amber-400"
                    >
                      caption_not_found
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary" className="font-mono text-[10px]">
                    {image.method}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    aria-label={`Download ${image.image}`}
                    onClick={() => downloadImage(jobId, image.image)}
                  >
                    <Download className="size-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="sm:max-w-3xl">
          {preview && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8 text-base leading-snug">
                  {preview.caption ?? "Caption not found"}
                </DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="font-mono text-[11px]">{preview.image}</span>
                  <Badge variant="secondary">page {preview.page}</Badge>
                  <Badge variant="secondary">
                    {(preview.confidence * 100).toFixed(1)}%
                  </Badge>
                  <Badge
                    variant="outline"
                    className={
                      preview.status === "matched"
                        ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
                        : "border-amber-600 text-amber-700 dark:text-amber-400"
                    }
                  >
                    {preview.status}
                  </Badge>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {preview.method}
                  </Badge>
                </DialogDescription>
              </DialogHeader>
              <div className="bg-muted flex items-center justify-center rounded-md p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageUrl(jobId, preview.image)}
                  alt={preview.caption ?? preview.image}
                  className="max-h-[70vh] w-auto max-w-full rounded object-contain"
                />
              </div>
              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={() => downloadImage(jobId, preview.image)}
                >
                  <ImageIcon className="size-4" /> Download source image
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
