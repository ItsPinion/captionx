import { API_PROXY_PREFIX } from "@captionx/shared";

import { buildZip } from "@/lib/zip";

/**
 * Browser download helpers (plan.md §28 / §29).
 *
 * JSON/CSV/images.zip/individual images map directly onto the backend's
 * generated files — the frontend never reconstructs results (§29). Only
 * "Download selected" composes an archive client-side, from the exact
 * source images fetched one by one.
 */

/** Trigger a browser download for an API-served file. */
export function downloadFromApi(path: string): void {
  const anchor = document.createElement("a");
  anchor.href = `${API_PROXY_PREFIX}${path}`;
  anchor.download = "";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export function downloadJson(jobId: string): void {
  downloadFromApi(`/jobs/${jobId}/json`);
}

export function downloadCsv(jobId: string): void {
  downloadFromApi(`/jobs/${jobId}/csv`);
}

export function downloadImagesZip(jobId: string): void {
  downloadFromApi(`/jobs/${jobId}/images.zip`);
}

export function imageUrl(jobId: string, filename: string): string {
  return `${API_PROXY_PREFIX}/jobs/${jobId}/image/${encodeURIComponent(filename)}`;
}

export function downloadImage(jobId: string, filename: string): void {
  downloadFromApi(`/jobs/${jobId}/image/${encodeURIComponent(filename)}`);
}

/**
 * Fetch the selected source images and package them into a ZIP in the
 * browser (§28: selected filenames → create ZIP → download).
 */
export async function downloadSelectedAsZip(
  jobId: string,
  label: string,
  filenames: string[],
): Promise<void> {
  const files: Record<string, Uint8Array> = {};
  for (const name of filenames) {
    const res = await fetch(imageUrl(jobId, name));
    if (!res.ok) {
      throw new Error(`failed to fetch ${name} (HTTP ${res.status})`);
    }
    files[name] = new Uint8Array(await res.arrayBuffer());
  }
  const blob = new Blob([buildZip(files) as BlobPart], {
    type: "application/zip",
  });
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${label || jobId}_selected_images.zip`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
