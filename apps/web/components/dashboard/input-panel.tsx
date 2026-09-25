"use client";

import { useRef, useState } from "react";
import {
  CheckCircle2,
  FileText,
  Link2,
  Loader2,
  Plus,
  Trash2,
  Upload,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { urlFailureMessage } from "@/lib/errors";
import { useSubmitUploads, useSubmitUrls } from "@/lib/hooks";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * §24 Section 2 — input mode tabs: "PDF Files" | "PDF URLs".
 * Files: drag/drop + picker + removable list + Start Extraction (§26).
 * URLs: multiple rows + add/remove + Start Extraction (§19).
 */
export function InputPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Add PDFs</CardTitle>
        <CardDescription>
          Every PDF becomes an independent job in the global FIFO queue — one
          PDF is processed at a time.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="files">
          <TabsList className="w-full sm:w-fit">
            <TabsTrigger value="files" className="flex-1 sm:px-6">
              <FileText className="size-4" /> PDF Files
            </TabsTrigger>
            <TabsTrigger value="urls" className="flex-1 sm:px-6">
              <Link2 className="size-4" /> PDF URLs
            </TabsTrigger>
          </TabsList>
          <TabsContent value="files">
            <FilesMode />
          </TabsContent>
          <TabsContent value="urls">
            <UrlsMode />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function FilesMode() {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const submit = useSubmitUploads();

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const merged = [...prev];
      for (const file of Array.from(incoming)) {
        if (!seen.has(`${file.name}:${file.size}`)) {
          merged.push(file);
          seen.add(`${file.name}:${file.size}`);
        }
      }
      return merged;
    });
  };

  const start = () => {
    if (files.length === 0 || submit.isPending) return;
    submit.mutate(files, { onSuccess: () => setFiles([]) });
  };

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          addFiles(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          dragOver ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"
        }`}
      >
        <Upload className="text-muted-foreground size-6" />
        <div className="text-sm font-medium">Drag & drop PDFs here</div>
        <div className="text-muted-foreground text-xs">
          or click to browse — multiple files supported
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {files.map((file, i) => (
            <li
              key={`${file.name}:${file.size}:${i}`}
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
            >
              <FileText className="text-muted-foreground size-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{file.name}</span>
              <span className="text-muted-foreground shrink-0 text-xs">
                {formatBytes(file.size)}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-6"
                aria-label={`Remove ${file.name}`}
                onClick={() =>
                  setFiles((prev) => prev.filter((_, j) => j !== i))
                }
              >
                <Trash2 className="size-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {submit.isError && (
        <p className="text-destructive text-sm">{submit.error.message}</p>
      )}

      <div>
        <Button onClick={start} disabled={files.length === 0 || submit.isPending}>
          {submit.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Upload className="size-4" />
          )}
          Start Extraction{files.length > 0 ? ` (${files.length})` : ""}
        </Button>
        {submit.isSuccess && submit.data.errors.length > 0 && (
          <div className="mt-3 flex flex-col gap-1">
            {submit.data.errors.map((e) => (
              <p key={e.filename} className="text-destructive text-xs">
                <XCircle className="mr-1 inline size-3" />
                {e.filename}: {e.reason}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function UrlsMode() {
  const [urls, setUrls] = useState<string[]>([""]);
  const submit = useSubmitUrls();

  const start = () => {
    const clean = urls.map((u) => u.trim()).filter(Boolean);
    if (clean.length === 0 || submit.isPending) return;
    submit.mutate(clean, { onSuccess: () => setUrls([""]) });
  };

  return (
    <div className="flex flex-col gap-3 pt-4">
      <Label className="text-muted-foreground text-xs">
        One PDF URL per row — the server downloads the file (30 s timeout,
        100 MB limit) and queues it.
      </Label>
      {urls.map((url, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            type="url"
            placeholder="https://example.org/chapter.pdf"
            value={url}
            onChange={(e) =>
              setUrls((prev) => prev.map((u, j) => (j === i ? e.target.value : u)))
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                setUrls((prev) => [...prev, ""]);
              }
            }}
          />
          <Button
            variant="ghost"
            size="icon"
            className="size-9 shrink-0"
            aria-label={`Remove URL row ${i + 1}`}
            disabled={urls.length === 1}
            onClick={() => setUrls((prev) => prev.filter((_, j) => j !== i))}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setUrls((prev) => [...prev, ""])}
        >
          <Plus className="size-4" /> Add URL
        </Button>
        <Button
          size="sm"
          onClick={start}
          disabled={urls.every((u) => !u.trim()) || submit.isPending}
        >
          {submit.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Upload className="size-4" />
          )}
          Start Extraction
        </Button>
      </div>

      {submit.isError && (
        <p className="text-destructive text-sm">{submit.error.message}</p>
      )}

      {submit.isSuccess && (
        <ul className="flex flex-col gap-1.5">
          {submit.data.results.map((r) => (
            <li key={r.url} className="flex flex-col gap-0.5 text-xs">
              <span className="flex items-start gap-1.5">
                {r.ok ? (
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                ) : (
                  <XCircle className="text-destructive mt-0.5 size-3.5 shrink-0" />
                )}
                <span className="min-w-0 flex-1 truncate">{r.url}</span>
                {r.ok && <Badge variant="secondary">queued</Badge>}
              </span>
              {!r.ok && r.error && (
                <span className="text-destructive pl-5">
                  {urlFailureMessage(r.error)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
