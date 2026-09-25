# Final Assessment Demo Flow

The demo, exactly as scripted in `plan.md` §44 — every step verified
end-to-end on this build (evidence in the "Verified" notes). Numbers you
should see are quoted so anything off-script is obvious.

Prerequisites (once):

```bash
bun install
cd extraction && ./setup.sh && cd ..   # venv + fixtures + vendored OCR models
bun run dev                            # API :4000 + dashboard :3000
```

Open **http://localhost:3000**.

---

## Step 1 — Open application

The dashboard header shows a live API health check (green `ok` via the Hono
RPC client, proxied through `/api/*`).

> Verified: `GET /api/health → {"status":"ok","service":"captionx-api"}`.

## Step 2 — Select `PDF Files`

The input panel's **PDF Files** tab is the default. (The **PDF URLs** tab is
the alternate input mode — not part of this demo.)

## Step 3 — Upload the two chosen NCERT chapter PDFs

The dashboard's **Add PDFs** card has a **selection menu of all 15 Class 9
Science chapters** (pinned edition) — tick one or many and hit *Extract
selected*, or use the per-row *pinned* / *official* download links. Official
chapter URLs (current ncert.nic.in edition — note its numbering differs from
the pinned edition: Sound is `jesc111` there, and 3 old chapters were
dropped):

- ch05 The Fundamental Unit of Life: https://ncert.nic.in/textbook/pdf/jesc105.pdf
- Sound (pinned ch12 → official ch11): https://ncert.nic.in/textbook/pdf/jesc111.pdf
- all chapters: https://ncert.nic.in/textbook.php?jesc1=0-13

Drag & drop — or pick — **both** chapter PDFs together:

- `extraction/fixtures/ncert_class9_science_ch05_cell.pdf`
- `extraction/fixtures/ncert_class9_science_ch12_sound.pdf`

They queue as a removable file list; one job per PDF is created.

## Step 4 — Click `Start Extraction`

The button (labelled `Start Extraction (2)`) fires one multipart upload; the
API creates two independent jobs and responds 201.

> Verified: `{jobs: [ch05 queued, ch12 queued], errors: []}`.

## Step 5 — Show the global FIFO constraint

The queue panel shows, live:

```text
ch05  PROCESSING      ← the single global worker's current job
ch12  WAITING         ← everything else queues, oldest first
```

The second PDF **never** starts until the first finishes, even though both
were submitted together — the §23 one-PDF-at-a-time constraint.

> Verified by 0.2 s-interval polling during a live run: ch05 PROCESSING /
> ch12 WAITING for ~1.9 s, then FIFO handoff. (The chapters are small, so
> the window is short; submitting 3+ PDFs makes it easier to see.)

## Step 6 — Wait for processing to finish

Statuses flip to `completed` (≈1–2 s per chapter on a modest machine —
native-text path, streaming pipeline). Polling stops automatically.

## Step 7 — Open results

The results view lists every extracted image with:

```text
image       page_NN_image_NN.png + thumbnail → full preview dialog
caption     exact printed caption text (or "No caption could be
            confidently identified for this image")
page        1-based page number
confidence  0..1
status      matched | caption_not_found
```

Expected on the pinned edition:

| Chapter | images | matched | caption_not_found |
|---|---|---|---|
| ch05 *The Fundamental Unit of Life* | **8** | **6** | 2 |
| ch12 *Sound* | **9** | **7** | 2 |

The `caption_not_found` rows are correct abstentions (Hooke/Hertz portraits,
Exercises-page art) — the system never invents captions.

> Verified: `Fig. 5.1: Compound microscope` @0.77, `Fig. 12.4: A beam of
> light from a light source…` @0.82, etc. — 13/13 matched captions verified
> visually (see `extraction/VERIFICATION.md`).

## Step 8 — Download JSON, CSV, selected images

- Tick checkboxes (select-all works; `caption_not_found` images are still
  valid extractions and included) → **download selected** (client-side ZIP).
- **JSON** / **CSV** / **images.zip** buttons download the backend's
  authoritative files for the selected job.

> Verified: `results.json` 200 (2.4 KB) · `results.csv` 200 (1.2 KB) ·
> `images.zip` 200 (139 KB, 9 PNGs).

## Step 9 — Show the structured output is real

Open the downloaded files:

- **JSON** — `{document: {filename, source, page_count}, images:
  [{image, page, caption, confidence, status, method}]}` — one object per
  image, confidence as a float, exact caption text.
- **CSV** — header `image,page,caption,confidence,status,method`, one row
  per image, same values as the dashboard shows.
- **images.zip** — the extracted PNGs, named
  `<document>_page_NN_image_NN.png`.

> Verified: JSON parses to the exact contract; CSV has 9 rows for ch12 with
> correct enums; ZIP contains 9 PNGs matching the table.

---

Switch jobs with the job selector in the results header (both completed jobs
remain accessible — completed results are kept, §36).
