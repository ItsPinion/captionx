import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join, resolve, sep } from "node:path";

import { paths } from "../config";

/**
 * Completed-result serving (plan.md §21 routes) + images.zip (§28).
 *
 * results.json / results.csv / images are the authoritative files written by
 * the Python engine (§29: "The backend serves the authoritative generated
 * result" — the frontend never reconstructs them).
 */

export function resultsJsonPath(jobId: string): string | null {
  const path = paths.resultsJson(jobId);
  return existsSync(path) ? path : null;
}

export function resultsCsvPath(jobId: string): string | null {
  const path = paths.resultsCsv(jobId);
  return existsSync(path) ? path : null;
}

/** Resolve a requested image filename safely inside the job's images dir. */
export function imageFilePath(jobId: string, filename: string): string | null {
  const imagesDir = resolve(paths.imagesDir(jobId));
  const candidate = resolve(imagesDir, basename(filename));
  if (!candidate.startsWith(imagesDir + sep)) return null; // traversal guard
  if (!existsSync(candidate) || !statSync(candidate).isFile()) return null;
  return candidate;
}

export function listImageFiles(jobId: string): string[] {
  const dir = paths.imagesDir(jobId);
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((name) => statSync(join(dir, name)).isFile());
}

// --- minimal store-only ZIP writer (no deps; PNGs are already compressed) ---

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

interface ZipEntry {
  nameBytes: Uint8Array;
  data: Uint8Array;
  crc: number;
  offset: number;
}

/** Build a store-method ZIP archive from `{name: bytes}` (DOS date-time 0). */
export function buildZip(files: Record<string, Uint8Array>): Uint8Array {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const entries: ZipEntry[] = [];
  let offset = 0;

  const push = (bytes: Uint8Array) => {
    chunks.push(bytes);
    offset += bytes.byteLength;
  };

  for (const [name, data] of Object.entries(files)) {
    const nameBytes = encoder.encode(name);
    const crc = crc32(data);
    const entry: ZipEntry = { nameBytes, data, crc, offset };
    entries.push(entry);

    const header = new DataView(new ArrayBuffer(30));
    header.setUint32(0, 0x04034b50, true); // local file header
    header.setUint16(4, 20, true); // version needed
    header.setUint16(6, 0x0800, true); // UTF-8 names
    header.setUint16(8, 0, true); // store
    header.setUint16(10, 0, true); // time
    header.setUint16(12, 0x21, true); // date (1996-01-01, constant)
    header.setUint32(14, crc, true);
    header.setUint32(18, data.byteLength, true); // compressed
    header.setUint32(22, data.byteLength, true); // uncompressed
    header.setUint16(26, nameBytes.byteLength, true);
    header.setUint16(28, 0, true);

    push(new Uint8Array(header.buffer));
    push(nameBytes);
    push(data);
  }

  const centralStart = offset;
  for (const entry of entries) {
    const central = new DataView(new ArrayBuffer(46));
    central.setUint32(0, 0x02014b50, true); // central directory header
    central.setUint16(4, 20, true);
    central.setUint16(6, 20, true);
    central.setUint16(8, 0x0800, true);
    central.setUint16(10, 0, true); // store
    central.setUint16(12, 0, true);
    central.setUint16(14, 0x21, true);
    central.setUint32(16, entry.crc, true);
    central.setUint32(20, entry.data.byteLength, true);
    central.setUint32(24, entry.data.byteLength, true);
    central.setUint16(28, entry.nameBytes.byteLength, true);
    central.setUint32(42, entry.offset, true);
    push(new Uint8Array(central.buffer));
    push(entry.nameBytes);
  }

  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); // end of central directory
  end.setUint16(8, entries.length, true);
  end.setUint16(10, entries.length, true);
  end.setUint32(12, offset - centralStart, true);
  end.setUint32(16, centralStart, true);
  push(new Uint8Array(end.buffer));

  const total = chunks.reduce((n, c) => n + c.byteLength, 0);
  const out = new Uint8Array(total);
  let cursor = 0;
  for (const chunk of chunks) {
    out.set(chunk, cursor);
    cursor += chunk.byteLength;
  }
  return out;
}

/** Build images.zip bytes for a job (empty record when no images). */
export function buildImagesZip(jobId: string): Uint8Array {
  const dir = paths.imagesDir(jobId);
  const files: Record<string, Uint8Array> = {};
  for (const name of listImageFiles(jobId)) {
    files[name] = new Uint8Array(readFileSync(join(dir, name)));
  }
  return buildZip(files);
}
