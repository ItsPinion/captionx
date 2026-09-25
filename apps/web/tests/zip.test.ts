/**
 * Unit tests for the browser ZIP builder (plan.md §28 "Download selected").
 *
 * Validates the exact byte layout: local file headers, store method,
 * UTF-8 name flag, CRC-32, central directory and end-of-central-directory
 * records — without pulling in any dependency.
 */
import { describe, expect, test } from "bun:test";

import { buildZip } from "@/lib/zip";

function u16(buf: Uint8Array, off: number): number {
  return buf[off] | (buf[off + 1] << 8);
}
function u32(buf: Uint8Array, off: number): number {
  return (buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16) | (buf[off + 3] << 24)) >>> 0;
}

const TEXT = new TextEncoder();

describe("buildZip (browser store-method ZIP)", () => {
  test("single entry: header fields, name, payload, EOCD", () => {
    const payload = TEXT.encode("PNGDATA");
    const zip = buildZip({ "stub_page_01_image_01.png": payload });

    // Signature + local header
    expect(u32(zip, 0)).toBe(0x04034b50); // PK\x03\x04
    expect(u16(zip, 4)).toBe(20); // version needed
    expect(u16(zip, 6)).toBe(0x0800); // UTF-8 names flag
    expect(u16(zip, 8)).toBe(0); // store (no compression)
    expect(u32(zip, 14)).toBe(0xdb1a1847); // CRC32("PNGDATA")
    expect(u32(zip, 18)).toBe(payload.byteLength);
    expect(u32(zip, 22)).toBe(payload.byteLength);
    expect(u16(zip, 26)).toBe("stub_page_01_image_01.png".length);

    // Payload copied verbatim after the 30-byte header + name
    const nameLen = u16(zip, 26);
    const dataStart = 30 + nameLen;
    expect(zip.subarray(dataStart, dataStart + payload.byteLength)).toEqual(payload);

    // EOCD
    const eocd = zip.byteLength - 22;
    expect(u32(zip, eocd)).toBe(0x06054b50);
    expect(u16(zip, eocd + 8)).toBe(1);
    expect(u16(zip, eocd + 10)).toBe(1);
  });

  test("multiple entries + central directory offsets are consistent", () => {
    const files = {
      "a.png": TEXT.encode("aaa"),
      "b.png": TEXT.encode("bbbb"),
      "unter/buously.png": TEXT.encode("ccccc"),
    };
    const zip = buildZip(files);

    // Walk local headers, then find the central directory.
    let offset = 0;
    const dataStarts: number[] = [];
    for (let i = 0; i < 3; i++) {
      expect(u32(zip, offset)).toBe(0x04034b50);
      const nameLen = u16(zip, offset + 26);
      const extraLen = u16(zip, offset + 28);
      const size = u32(zip, offset + 18);
      dataStarts.push(offset + 30 + nameLen + extraLen);
      offset = dataStarts[i] + size;
    }
    const centralStart = offset;
    let centralOffset = centralStart;
    for (let i = 0; i < 3; i++) {
      expect(u32(zip, centralOffset)).toBe(0x02014b50);
      const nameLen = u16(zip, centralOffset + 28);
      centralOffset += 46 + nameLen; // record header + filename
    }
    const eocd = centralOffset;
    expect(u32(zip, eocd)).toBe(0x06054b50);
    expect(u16(zip, eocd + 8)).toBe(3);
    expect(u32(zip, eocd + 12)).toBe(eocd - centralStart);
    expect(u32(zip, eocd + 16)).toBe(centralStart);
  });

  test("non-ASCII filenames survive via the UTF-8 flag", () => {
    const zip = buildZip({ "käpitel_5_bild.png": TEXT.encode("x") });
    const nameLen = u16(zip, 26);
    expect(new TextDecoder().decode(zip.subarray(30, 30 + nameLen))).toBe(
      "käpitel_5_bild.png",
    );
    expect(u16(zip, 6)).toBe(0x0800);
  });
});
