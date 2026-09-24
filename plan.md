# Image–Caption Extraction Automation
## Hyper-Detailed Phase-by-Phase Implementation Plan

> **Project type:** Junior AI Developer Assessment  
> **Target:** CBSE Grade 9 NCERT PDF image extraction + image-to-caption mapping  
> **Primary constraint:** Complete a credible working system within **2 days**  
> **Primary quality goal:** Aim for approximately **95% correct image → caption mappings** on the selected NCERT chapters, then personally verify the output  
> **Scope:** Assessment-first, NCERT-optimized, lightweight enough for a modest PC  
> **Important:** This document reflects the architecture and technology decisions already agreed upon. Do not introduce additional infrastructure unless a real implementation blocker requires it.

---

# 1. Project Objective

Build a web application that accepts one or more Grade 9 NCERT PDF documents and automatically:

1. Extracts native image objects from each PDF.
2. Saves every relevant image occurrence as an individual image file.
3. Extracts text and positional information from the PDF.
4. Uses PaddleOCR only where native PDF text is insufficient or unreliable.
5. Identifies likely caption text for each image.
6. Maps every extracted image to its most likely caption.
7. Assigns a confidence score to the mapping.
8. Uses a lightweight fallback matcher for low-confidence cases.
9. Marks an image as `caption_not_found` instead of inventing a caption when no reliable caption can be identified.
10. Produces:
   - `results.json`
   - `results.csv`
   - extracted image files
11. Presents the result through a professional single-page dashboard.
12. Allows:
   - PDF upload mode
   - PDF URL mode
   - multiple PDFs per submission
   - one PDF processed at a time globally
   - FIFO queueing
   - per-image selection
   - select-all image download
   - JSON/CSV download
13. Allows manual inspection of results so the developer can verify the target accuracy on the chosen NCERT chapters.

---

# 2. Guiding Principles

## 2.1 Assessment first

The core success criterion is not architectural sophistication.

The core success criterion is:

```text
PDF
→ correct image extraction
→ correct caption mapping
→ clean JSON/CSV output
```

Frontend/backend infrastructure exists to make the extraction pipeline usable.

---

## 2.2 Keep the ML stack lightweight

Use:

- PyMuPDF for PDF structure and extraction.
- PaddleOCR for OCR fallback and bounding boxes.
- Lightweight deterministic matching logic for image-caption association.

Do **not** add another heavy model unless the existing approach genuinely fails on the target NCERT documents.

---

## 2.3 Prefer deterministic information already present in the PDF

Before asking a model to infer anything:

1. Extract embedded images.
2. Extract PDF-native text.
3. Extract text coordinates.
4. Use page structure.
5. Use OCR only where necessary.
6. Use lightweight scoring for matching.

The PDF already contains valuable structural information. Use it.

---

## 2.4 Never force a caption when the evidence is weak

A false image-caption mapping is worse than:

```json
{
  "caption": null,
  "status": "caption_not_found"
}
```

The system must be allowed to say:

> I found an image, but I could not confidently identify its caption.

---

## 2.5 Optimize for the actual assessment documents

The assessment specifically concerns Grade 9 NCERT PDFs.

The caption-matching heuristics should therefore be tuned against the actual NCERT chapters being demonstrated.

The system does not need to become a universal PDF understanding engine.

---

## 2.6 Build the extraction pipeline before polishing the UI

Recommended priority:

```text
1. Python extraction
2. Caption matching
3. Output generation
4. Queue/API integration
5. Dashboard
6. Documentation/polish
```

Do not spend half of Day 1 creating UI components while the extraction algorithm is still untested.

---

# 3. Final Architecture

## 3.1 High-level architecture

```text
                           Turborepo
                              │
              ┌───────────────┴───────────────┐
              │                               │
         apps/web                         apps/api
     Next.js + React                  Hono + TypeScript
     + Tailwind                       + Hono RPC
     + shadcn/ui                      + FIFO worker
     + TanStack Query                 + filesystem state
              │                               │
              └───────────────┬───────────────┘
                              │
                       Python process
                              │
                     extraction/main.py
                              │
              ┌───────────────┼───────────────┐
              │               │               │
          PyMuPDF         PaddleOCR       Matching
              │               │               │
              └───────────────┴───────────────┘
                              │
                    JSON + CSV + images
                              │
                         data/results/
```

---

# 4. Final Technology Decisions

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Hono RPC client

## Backend

- Hono
- TypeScript
- Hono RPC
- Bun
- Local filesystem for persistence
- No authentication

## Monorepo

- Turborepo
- Bun workspaces
- Shared TypeScript package

## Python

- Python
- `venv`
- `requirements.txt`
- PyMuPDF
- PaddleOCR
- PaddlePaddle CPU
- Pillow
- lightweight Python utilities as required

## Storage

No database.

Use:

```text
data/
├── uploads/
├── jobs/
└── results/
```

## Processing

- One PDF at a time globally
- FIFO queue
- Multiple PDFs become individual jobs
- Unfinished jobs persisted on disk
- Completed jobs remain as final results

## PDF handling

- PyMuPDF first
- specialized fallback only if a real PDF incompatibility is encountered
- no aggressive document-image computer-vision detection

## OCR

- PaddleOCR
- use OCR as a fallback rather than blindly OCR-ing every page

## Matching

- spatial + textual heuristic scoring
- NCERT-optimized
- confidence scoring
- lightweight fallback strategy

## Deployment

- local-first
- deployment-ready structure
- no Docker required
- no cloud dependency
- no paid API

---

# 5. Repository Structure

The target repository should look approximately like this:

```text
project/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── providers/
│   │   └── ...
│   │
│   └── api/
│       ├── src/
│       │   ├── index.ts
│       │   ├── routes/
│       │   ├── queue/
│       │   ├── services/
│       │   ├── utils/
│       │   └── types/
│       └── ...
│
├── packages/
│   └── shared/
│       ├── src/
│       │   ├── types.ts
│       │   ├── constants.ts
│       │   └── index.ts
│       └── package.json
│
├── extraction/
│   ├── .venv/
│   ├── main.py
│   ├── requirements.txt
│   ├── src/
│   │   ├── pdf/
│   │   │   ├── extractor.py
│   │   │   ├── text.py
│   │   │   └── images.py
│   │   ├── ocr/
│   │   │   └── paddle.py
│   │   ├── matching/
│   │   │   ├── candidates.py
│   │   │   ├── scorer.py
│   │   │   └── fallback.py
│   │   ├── output/
│   │   │   ├── json_writer.py
│   │   │   └── csv_writer.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── pipeline.py
│   └── README.md
│
├── data/
│   ├── uploads/
│   ├── jobs/
│   └── results/
│
├── package.json
├── turbo.json
├── README.md
└── .gitignore
```

### Important repository rule

Do **not** commit:

```text
data/uploads/*
data/jobs/*
data/results/*
extraction/.venv/
```

Add them to `.gitignore`.

---

# 6. Phase 0 — Freeze Scope Before Coding

## Goal

Prevent scope creep.

## Locked scope

The application must support:

- multiple PDF uploads
- multiple PDF URLs
- one input mode per run
- local filesystem
- one PDF processing at a time
- FIFO queue
- per-PDF result directories
- PyMuPDF
- PaddleOCR fallback
- spatial/textual matching
- confidence
- `caption_not_found`
- JSON
- CSV
- image downloads
- select-all image download
- single-page professional dashboard
- Hono RPC
- TanStack Query
- Turborepo
- Bun
- Python `venv`

## Explicitly out of scope

Do not add:

- authentication
- database
- Redis
- BullMQ
- RabbitMQ
- WebSockets
- SSE
- Docker
- Kubernetes
- VLM
- LayoutLM
- YOLO document detection
- cloud inference
- paid APIs
- multi-service Python architecture
- automated evaluation platform
- deduplication
- generic universal PDF support

---

# 7. Phase 1 — Bootstrap the Monorepo

## Goal

Get the development environment running.

## 7.1 Create the Turborepo

Create:

```text
apps/web
apps/api
packages/shared
```

The Python project lives beside them as:

```text
extraction/
```

Python is not forced into the JavaScript workspace.

## 7.2 Configure Bun

Bun is the package manager/runtime for the TypeScript side.

Verify:

```bash
bun --version
```

Verify workspace installation works.

## 7.3 Configure TypeScript sharing

Create:

```text
packages/shared
```

Initial shared types should include:

```text
JobStatus
Job
ImageStatus
ImageResult
ExtractionResult
DocumentMetadata
```

Do not duplicate the Hono RPC contract in the shared package.

Hono RPC remains the source of truth for API route typing.

## 7.4 Configure web application

Initialize:

- Next.js
- React
- TypeScript
- Tailwind
- shadcn/ui

## 7.5 Configure API application

Initialize:

- Hono
- TypeScript

Add a trivial health endpoint.

Example conceptual endpoint:

```text
GET /health
```

Expected:

```json
{
  "status": "ok"
}
```

## 7.6 Acceptance criteria

Before moving forward:

- `bun install` works.
- frontend runs.
- API runs.
- web can reach API.
- shared package imports correctly.
- Hono RPC client can make one test call.

---

# 8. Phase 2 — Set Up the Python Extraction Environment

## Goal

Create a reproducible Python environment.

## 8.1 Create `venv`

Inside `extraction/`:

```bash
python -m venv .venv
```

Activate it.

## 8.2 Create requirements

Start with only required packages.

Conceptually:

```text
PyMuPDF
PaddleOCR
PaddlePaddle
Pillow
```

Add packages only when an actual implementation need appears.

## 8.3 Verify PyMuPDF

Create a tiny script:

```text
open PDF
print page count
```

## 8.4 Verify PaddleOCR

Run it on one rendered NCERT page.

Confirm:

- model downloads correctly
- CPU inference works
- text boxes are returned

Do this early.

If PaddleOCR cannot run on the machine, resolve this before building the rest of the pipeline.

## 8.5 Acceptance criteria

You can:

```text
open PDF
→ render page
→ OCR text
→ obtain bounding boxes
```

on your actual PC.

---

# 9. Phase 3 — Design the Python Data Model

## Goal

Keep the pipeline stages independent and testable.

Define internal structures for:

### Document

```text
document_id
filename
page_count
source
```

### Image occurrence

```text
image_id
page
index
bbox
width
height
filename
```

### Text region

```text
text
bbox
source
page
```

Where `source` is:

```text
native_pdf
ocr
```

### Caption candidate

```text
text
bbox
image_id
features
score
```

### Final match

```text
image_id
caption
confidence
status
method
```

Possible status:

```text
matched
caption_not_found
```

---

# 10. Phase 4 — Implement Native PDF Extraction

## Goal

Extract images and native text before OCR.

## 10.1 Open the PDF

Use PyMuPDF.

## 10.2 Iterate pages

For every page:

1. determine page number
2. get image occurrences
3. get image bounding boxes
4. get native text blocks
5. preserve ordering

## 10.3 Extract images

Do not deduplicate.

Each occurrence is a separate record.

Name files:

```text
<document>_page_<page>_image_<index>.png
```

Example:

```text
biology_ch01_page_03_image_01.png
```

## 10.4 Text extraction

Start with:

```text
page.get_text("blocks")
```

Capture:

- text
- x0
- y0
- x1
- y1

## 10.5 Rendered image fallback for OCR

Render a page only when OCR is required.

Do not render all pages at unnecessarily high resolution.

Start with a moderate DPI that PaddleOCR can handle quickly on CPU.

## 10.6 Acceptance criteria

A test PDF should produce:

```text
N image files
N image metadata records
text blocks with coordinates
page numbers
```

---

# 11. Phase 5 — Determine When OCR Is Needed

## Goal

Avoid expensive OCR where possible.

## Decision flow

```text
PDF page
  ↓
native text extraction
  ↓
usable text?
 ├── yes → use native text
 └── no / suspicious → render page → PaddleOCR
```

## Suspicious page signals

Potential examples:

- almost no native text but page visibly contains text
- text blocks are missing where an apparent caption should exist
- page appears image-heavy
- extracted text is obviously incomplete

Do not over-engineer this detector.

Start with a simple rule.

## Output

Each page ultimately has:

```text
text_regions[]
```

with each region tagged:

```text
native_pdf
```

or:

```text
ocr
```

---

# 12. Phase 6 — PaddleOCR Integration

## Goal

Integrate OCR without letting it dominate runtime.

## 12.1 Use a mobile OCR model

Prefer CPU-friendly PaddleOCR mobile models.

## 12.2 Initialize the OCR model once

Do not load the model separately for every page.

Bad:

```text
for page:
    initialize OCR
    OCR(page)
```

Better:

```text
initialize OCR once

for page:
    OCR(page)
```

This matters significantly for runtime.

## 12.3 Convert OCR coordinates to page coordinates

If the page is rendered at scale:

```text
scale = rendered_pixels / PDF_points
```

convert OCR coordinates back to the PDF/page coordinate system.

The image-caption matcher should use one consistent coordinate system.

## 12.4 OCR errors

OCR may:

- split captions into multiple boxes
- merge lines
- misread numbers
- confuse characters

Do not rewrite the original caption blindly.

Keep OCR output as the detected source text.

---

# 13. Phase 7 — Caption Candidate Detection

## Goal

For each image, identify nearby text blocks that could represent a caption.

## 13.1 Same-page restriction

Start by searching for candidates on the same page.

This greatly reduces false matches.

## 13.2 Build a candidate window

For an image:

```text
image bbox = [x0, y0, x1, y1]
```

Search nearby text blocks.

Primary region:

```text
below image
```

Secondary region:

```text
above image
```

Avoid searching the entire page unless fallback logic requires it.

## 13.3 Candidate filtering

Remove obvious candidates such as:

- page numbers
- headers
- footers
- very distant paragraphs
- extremely large body-text blocks
- unrelated text columns

## 13.4 Preserve text exactly

Candidate text should not be normalized for the final output.

Normalization can exist internally for matching.

---

# 14. Phase 8 — Feature Engineering for Caption Matching

## Goal

Create lightweight features rather than another ML model.

For each `(image, text_candidate)` pair calculate features.

## 14.1 Vertical distance

Distance from image bottom to candidate top.

A small distance should score higher.

## 14.2 Horizontal alignment

Compare:

```text
image x-center
candidate x-center
```

Aligned text is more likely to be a caption.

## 14.3 Overlap

Calculate horizontal overlap between image and candidate.

A caption often spans a similar horizontal region.

## 14.4 Relative position

Give positive score to:

```text
candidate below image
```

Secondary score:

```text
candidate above image
```

## 14.5 Caption keywords

Boost candidate text containing:

```text
Fig
Figure
Image
Plate
Diagram
```

The system should not require these words.

They are only features.

## 14.6 Caption length

Captions are generally shorter than normal body paragraphs.

Use this as a weak signal.

Do not hard-code an aggressive maximum length.

## 14.7 Numbering

Patterns like:

```text
Fig. 3.2
Figure 4.1
Image 2
```

can increase score.

## 14.8 Font or style signals

Use PDF font metadata only if convenient and reliable.

Do not spend significant time reverse-engineering fonts.

---

# 15. Phase 9 — Build the Primary Scoring Function

## Goal

Combine features into one score.

Conceptual model:

```text
candidate_score =
    proximity_score
  + alignment_score
  + caption_keyword_score
  + numbering_score
  + text_shape_score
  + layout_score
```

A simple weighted implementation is sufficient.

Example initial weighting:

```text
proximity         40%
horizontal align  20%
caption keywords  15%
numbering         10%
text shape        10%
layout             5%
```

These weights are starting points, not permanent truths.

Tune using the real NCERT output.

---

# 16. Phase 10 — Confidence Calculation

## Goal

Expose how certain the matcher is.

Possible confidence approach:

```text
top_score
relative to
second_best_score
```

A mapping should be considered low-confidence when:

- top score is weak
- top two candidates are close
- candidate distance is large
- structural evidence is poor

The confidence score does not need to be mathematically perfect.

It must be useful for distinguishing:

```text
clearly good
probably good
uncertain
```

---

# 17. Phase 11 — Implement Fallback Matching

## Goal

Recover difficult cases without introducing another model.

## Primary matcher

Strict:

```text
same page
near image
strong positional relationship
```

## Fallback matcher

Slightly broader:

```text
same page
larger candidate window
allow above/below
increase weight of keyword/numbering evidence
```

Do not immediately search neighboring pages.

Only consider that later if an actual NCERT case proves it necessary.

## Final rule

If no candidate exceeds the minimum confidence threshold:

```text
caption = null
status = "caption_not_found"
```

---

# 18. Phase 12 — Preserve Every Image Occurrence

## Goal

No deduplication.

If the PDF contains:

```text
page 4 → image A
page 9 → image A again
```

produce:

```text
page_04_image_01.png
page_09_image_01.png
```

as separate records.

Reason:

The occurrence can have different contextual relationships or captions.

---

# 19. Phase 13 — Result Schema

## JSON structure

Use something close to:

```json
{
  "document": {
    "filename": "biology_ch01.pdf",
    "source": "upload",
    "page_count": 18
  },
  "images": [
    {
      "image": "biology_ch01_page_03_image_01.png",
      "page": 3,
      "caption": "Fig. 3.1: Structure of the cell",
      "confidence": 0.94,
      "status": "matched",
      "method": "native_text"
    }
  ]
}
```

## Required fields

At minimum:

```text
image
page
caption
confidence
status
method
```

## `caption_not_found`

```json
{
  "image": "biology_ch01_page_08_image_02.png",
  "page": 8,
  "caption": null,
  "confidence": 0.18,
  "status": "caption_not_found",
  "method": "no_reliable_candidate"
}
```

---

# 20. Phase 14 — CSV Output

Keep CSV intentionally simpler.

Columns:

```text
image
page
caption
confidence
status
method
```

Quote caption fields correctly.

Preserve the extracted caption text.

---

# 21. Phase 15 — Hono/Python Job Contract

## Goal

Keep the boundary between Hono and Python simple.

Hono executes:

```text
python main.py \
  --job-id <id> \
  --input <pdf-path> \
  --output <result-path>
```

Python:

1. validates arguments
2. loads PDF
3. updates status file
4. runs extraction
5. writes JSON
6. writes CSV
7. exits with code `0` on success
8. exits non-zero on failure

---

# 22. Phase 16 — Job Directory

Each job should have a predictable filesystem structure.

Example:

```text
data/jobs/job_001/
├── job.json
└── status.json
```

Results:

```text
data/results/biology_ch01/
├── results.json
├── results.csv
└── images/
    ├── biology_ch01_page_03_image_01.png
    └── ...
```

Do not put large transient processing files into the job metadata file.

---

# 23. Phase 17 — Global FIFO Worker

## Goal

Exactly one PDF at a time across all users.

## Processing rule

```text
if worker_is_busy:
    enqueue
else:
    start immediately
```

## Queue order

Sort by:

```text
createdAt
```

Oldest first.

## Processing lifecycle

```text
queued
  ↓
processing
  ↓
completed
```

or:

```text
queued
  ↓
processing
  ↓
failed
```

## Multiple user behavior

Example:

```text
User A submits PDF A
User B submits PDF B
User C submits PDF C
```

Queue:

```text
A → B → C
```

Only one worker executes.

---

# 24. Phase 18 — Restart Recovery

## Goal

Avoid losing unfinished work if Hono restarts.

On startup:

1. scan `data/jobs/`
2. identify jobs with:
   - `queued`
   - `processing`
3. convert interrupted `processing` jobs back to `queued`
4. sort by `createdAt`
5. resume FIFO

Completed jobs remain completed.

Failed jobs remain failed unless explicitly retried.

---

# 25. Phase 19 — URL Input Flow

## Goal

Support multiple PDF URLs in URL mode.

## Hono responsibilities

For each URL:

1. validate syntax
2. make HTTP request
3. verify a successful response
4. verify that the content is plausibly a PDF
5. save to `data/uploads/`
6. create a job
7. add to FIFO queue

## Do not

- send URL directly to Python
- allow Python to perform network requests
- create a generic web crawler
- support arbitrary website scraping

The task needs PDF URLs.

---

# 26. Phase 20 — File Upload Flow

## Goal

Accept multiple local PDFs.

Flow:

```text
Browser
  ↓
multipart/form-data
  ↓
Hono
  ↓
save file
  ↓
create job for each PDF
  ↓
FIFO queue
```

Every PDF is an independent job.

---

# 27. Phase 21 — Hono RPC API

Keep the API surface intentionally small.

Suggested operations:

```text
createUploadJobs
createUrlJobs
getJob
getJobResult
downloadJson
downloadCsv
downloadImage
downloadImagesZip
```

Potential logical route layout:

```text
/jobs/upload
/jobs/url
/jobs/:jobId
/jobs/:jobId/result
/jobs/:jobId/json
/jobs/:jobId/csv
/jobs/:jobId/image/:filename
/jobs/:jobId/images.zip
```

The frontend uses the Hono RPC client rather than hand-writing request typings.

---

# 28. Phase 22 — Shared Types

Put reusable domain types in:

```text
packages/shared
```

Examples:

```ts
type JobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed";

type ImageStatus =
  | "matched"
  | "caption_not_found";
```

Share:

- status enums
- result object shapes
- basic job metadata
- UI-facing types

Do not duplicate Python's internal dataclasses in TypeScript.

Python remains independently typed.

---

# 29. Phase 23 — TanStack Query Integration

Use TanStack Query for:

## Queries

```text
job status
job result
```

## Mutations

```text
submit upload
submit URLs
```

## Polling

While a job is:

```text
queued
processing
```

poll status.

Stop when:

```text
completed
failed
```

A 1–2 second interval is sufficient for the assessment UI.

Do not poll unnecessarily after completion.

---

# 30. Phase 24 — Single-Page Dashboard Structure

## Section 1 — Header

Show:

```text
Image–Caption Extraction
NCERT PDF Automation
```

## Section 2 — Input mode

Tabs:

```text
PDF Files
PDF URLs
```

## File mode

Components:

- drag/drop zone
- file picker
- selected files
- remove file action
- `Start Extraction`

## URL mode

Components:

- multiple URL input rows
- add URL
- remove URL
- `Start Extraction`

---

# 31. Phase 25 — Queue Visualization

Show:

```text
Current processing
Waiting
Completed
Failed
```

Example:

```text
Physics.pdf
PROCESSING

Biology.pdf
WAITING

Chemistry.pdf
WAITING
```

No complicated job management interface is required.

---

# 32. Phase 26 — Results Table

For each completed PDF:

```text
Image preview
Page
Caption
Confidence
Status
Method
```

Use shadcn components:

- Card
- Table
- Badge
- Progress
- Button
- Tabs
- Dialog
- Checkbox

Avoid adding unnecessary component libraries.

---

# 33. Phase 27 — Image Selection

Each result row includes a checkbox.

Support:

```text
Select all
Clear all
Download selected
```

Selection is only a UI concern.

Do not store selections on the server.

---

# 34. Phase 28 — Image Downloads

## Individual

Download the exact source image.

## Multiple

When user selects multiple images:

```text
selected filenames
       ↓
create ZIP
       ↓
download
```

## Select all

Select every successfully extracted image.

This should include images with:

```text
caption_not_found
```

because the image was still validly extracted.

---

# 35. Phase 29 — JSON/CSV Downloads

Buttons:

```text
Download JSON
Download CSV
```

These should map directly to generated files.

The frontend should not reconstruct the results itself.

The backend serves the authoritative generated result.

---

# 36. Phase 30 — Error Handling

## API-level

Return useful errors for:

- invalid file
- URL download failure
- nonexistent job
- unavailable result

## Python-level

Write stage information into status.

Example:

```json
{
  "status": "failed",
  "stage": "ocr",
  "message": "OCR initialization failed"
}
```

Possible stages:

```text
input
pdf_parse
image_extraction
ocr
matching
output
```

## Recovery

Use existing fallback where appropriate.

Do not implement a generic retry engine.

---

# 37. Phase 31 — UI Error States

Show errors clearly.

Examples:

```text
Could not download PDF
```

```text
Could not process this PDF
```

```text
No caption could be confidently identified for this image
```

Do not show stack traces to normal users.

Detailed error information can remain in server logs/status files.

---

# 38. Phase 32 — NCERT-Specific Tuning

## Goal

Optimize for the actual target.

Choose two assessment chapters.

For each chapter:

1. run extraction
2. inspect all extracted images
3. inspect mappings
4. classify mistakes
5. adjust matcher
6. rerun

## Track mistake categories

Use a small manual table:

```text
error_type
-----------
wrong_nearby_text
caption_above_image
caption_below_image
split_caption
shared_caption
ocr_error
false_image
caption_not_found
```

This is not a formal benchmark system.

It is an engineering tuning process.

---

# 39. Phase 33 — Manual Accuracy Verification

The project does not need an automated test platform for the 95% assessment requirement.

You personally verify the selected chapters.

For each extracted image ask:

```text
Did we extract the correct image?
Did we attach the correct caption?
```

Count correct mappings.

For your own reference:

```text
accuracy =
correct_image_caption_pairs / total_expected_pairs
```

Example:

```text
95 correct
100 expected

accuracy = 95%
```

Do not publish a 95% claim unless you actually inspect the output and can support it.

---

# 40. Phase 34 — Edge Cases to Check

Before finalizing, deliberately inspect:

## Case 1

Image directly above caption.

## Case 2

Image directly below caption.

## Case 3

Caption begins with:

```text
Fig.
```

## Case 4

Caption begins with:

```text
Figure
```

## Case 5

Caption contains no explicit figure keyword.

## Case 6

Two images are adjacent.

## Case 7

Two images share a caption region.

## Case 8

Image has no caption.

Expected:

```text
caption_not_found
```

## Case 9

Page contains multiple columns.

## Case 10

OCR is necessary.

## Case 11

The PDF contains tiny decorative graphics.

## Case 12

Same image appears twice.

Both occurrences remain separate.

---

# 41. Phase 35 — Performance Optimization

Your PC is a constraint.

Optimize in this order.

## 41.1 Avoid unnecessary OCR

Native PDF text is cheaper.

## 41.2 Initialize OCR once

Do not load the model repeatedly.

## 41.3 Process one PDF globally

Already decided.

## 41.4 Avoid huge render resolutions

Use enough DPI for OCR without rendering needlessly large images.

## 41.5 Avoid keeping entire PDFs/pages in memory

Process page-by-page where practical.

## 41.6 Release temporary page images

Delete temporary rendered images when they are no longer needed.

## 41.7 Don't parallelize

Do not use worker pools.

Do not run several PDFs simultaneously.

---

# 42. Phase 36 — Cleanup and Storage Rules

## Uploads

Keep original uploaded PDFs for debugging during the assessment.

## Jobs

Keep enough state to understand processing.

## Results

Keep completed result directories.

## Temporary files

Delete unnecessary temporary render files.

Do not let OCR intermediate files accumulate forever.

---

# 43. Phase 37 — Final README

README should contain:

## 1. Project title

Example:

```text
NCERT Image–Caption Extraction Automation
```

## 2. Problem statement

Explain exactly what the assessment asks.

## 3. Solution overview

Explain:

```text
PyMuPDF
+
PaddleOCR
+
spatial/textual matching
```

## 4. Architecture

Include a diagram.

## 5. Why this architecture

Mention:

- local/free
- lightweight
- no paid APIs
- NCERT optimization
- modular pipeline

## 6. Setup

Bun:

```text
install dependencies
run web/API
```

Python:

```text
create venv
install requirements
```

## 7. Running the system

Explain:

```text
start API
start web
open dashboard
submit PDFs
inspect results
```

## 8. Output

Show:

```text
results.json
results.csv
images/
```

## 9. Matching method

Explain the scoring features.

## 10. Limitations

Examples:

- scanned/image-only PDF pages may not be handled if no native image object exists
- OCR can introduce text recognition errors
- unusual layouts may produce ambiguous matches
- system is tuned for NCERT layouts
- only one PDF is processed at a time

## 11. Accuracy

Only report what you personally verified.

---

# 44. Phase 38 — Final Assessment Demo Flow

Your demo should be very simple.

## Step 1

Open application.

## Step 2

Select:

```text
PDF Files
```

## Step 3

Upload the two chosen NCERT chapter PDFs.

## Step 4

Click:

```text
Start Extraction
```

## Step 5

Show:

```text
PDF 1 PROCESSING
PDF 2 WAITING
```

This demonstrates the global FIFO constraint.

## Step 6

Wait for processing to finish.

## Step 7

Open results.

Show:

```text
image
caption
page
confidence
status
```

## Step 8

Download:

```text
JSON
CSV
selected images
```

## Step 9

Open the JSON/CSV to demonstrate that the structured output is real.

---

# 45. Phase 39 — Final Submission Checklist

Before submitting, verify all of the following.

## Application

- [ ] Next.js starts.
- [ ] Hono starts.
- [ ] Hono RPC works.
- [ ] TanStack Query works.
- [ ] Python starts.
- [ ] PaddleOCR works.
- [ ] file mode works.
- [ ] URL mode works.
- [ ] multiple PDFs create multiple jobs.
- [ ] queue is FIFO.
- [ ] only one PDF runs at a time.
- [ ] restart recovery works.
- [ ] failed jobs are visible.
- [ ] completed results remain accessible.

## Extraction

- [ ] images are saved separately.
- [ ] all intended image occurrences are retained.
- [ ] filenames include document/page/image index.
- [ ] captions are mapped.
- [ ] `caption_not_found` works.
- [ ] confidence is present.
- [ ] JSON is valid.
- [ ] CSV is valid.
- [ ] image downloads work.

## Dashboard

- [ ] professional but simple.
- [ ] drag/drop works.
- [ ] URL mode works.
- [ ] processing status visible.
- [ ] queue visible.
- [ ] results table works.
- [ ] image preview works.
- [ ] select-all works.
- [ ] selected-image download works.
- [ ] JSON download works.
- [ ] CSV download works.
- [ ] errors are understandable.

## Quality

- [ ] both selected NCERT chapters manually inspected.
- [ ] obvious caption errors corrected.
- [ ] false positives reviewed.
- [ ] no unsupported 95% claim.
- [ ] known limitations documented.

---

# 46. Two-Day Critical Path

If time becomes limited, follow this priority order exactly.

## Priority 1 — Mandatory

```text
PDF input
↓
PyMuPDF image extraction
↓
native text extraction
↓
PaddleOCR fallback
↓
caption candidate matching
↓
JSON/CSV
```

## Priority 2 — Mandatory

```text
Hono
↓
Python process
↓
filesystem jobs
↓
FIFO
```

## Priority 3 — Important

```text
Next.js dashboard
↓
results table
↓
downloads
```

## Priority 4 — Polish

```text
shadcn/ui refinement
loading states
empty states
error states
README
```

If you are behind schedule, do **not** remove time from the extraction pipeline to improve UI cosmetics.

---

# 47. What to Build First

The first working milestone should be a command-line program.

You should be able to run:

```text
python main.py \
  --job-id test-001 \
  --input sample.pdf \
  --output data/results/sample/
```

and receive:

```text
data/results/sample/
├── results.json
├── results.csv
└── images/
```

with at least:

```text
image filename
page number
caption
confidence
status
```

If this works, the hardest technical part of the assessment is under control.

The web application is then an interface around a proven extraction engine.

---

# 48. Final Mental Model

The whole project can be understood as five systems.

```text
SYSTEM 1
INPUT
PDF upload / URL
        ↓

SYSTEM 2
PDF UNDERSTANDING
PyMuPDF
        ↓

SYSTEM 3
AI-ASSISTED TEXT UNDERSTANDING
PaddleOCR when needed
        ↓

SYSTEM 4
IMAGE ↔ CAPTION MATCHING
spatial + textual scoring
        ↓

SYSTEM 5
DELIVERY
JSON + CSV + images + dashboard
```

Everything else exists only to connect these five systems.

---

# 49. Final Architecture Summary

```text
┌───────────────────────────────────────────────────────────┐
│                     Next.js Dashboard                     │
│  Upload | URLs | Queue | Results | Downloads              │
└────────────────────────────┬──────────────────────────────┘
                             │
                        Hono RPC
                             │
┌────────────────────────────▼──────────────────────────────┐
│                     Hono API                              │
│                                                           │
│  input validation                                         │
│  file download                                            │
│  job creation                                             │
│  FIFO queue                                               │
│  Python process launcher                                  │
│  result serving                                           │
└────────────────────────────┬──────────────────────────────┘
                             │
                       one PDF at a time
                             │
┌────────────────────────────▼──────────────────────────────┐
│                  Python Extraction                         │
│                                                           │
│  PyMuPDF                                                  │
│    ├─ embedded images                                     │
│    ├─ text                                                │
│    └─ coordinates                                         │
│                                                           │
│  PaddleOCR (fallback)                                     │
│    └─ OCR text + boxes                                    │
│                                                           │
│  Matching                                                 │
│    ├─ proximity                                           │
│    ├─ alignment                                           │
│    ├─ caption keywords                                    │
│    ├─ numbering                                           │
│    └─ layout signals                                      │
│                                                           │
│  Fallback matcher                                         │
│                                                           │
│  Output                                                   │
│    ├─ JSON                                                │
│    ├─ CSV                                                 │
│    └─ images                                              │
└───────────────────────────────────────────────────────────┘
```

---

# 50. Definition of Done

The project is complete when all of the following are true:

1. The user can open the Next.js dashboard.
2. The user can choose PDF upload mode or PDF URL mode.
3. Multiple PDFs can be submitted.
4. Each PDF becomes its own FIFO job.
5. Only one PDF is processed at a time.
6. Hono launches the Python extractor.
7. Python extracts native PDF images.
8. Image occurrences are not deduplicated.
9. Images are named using document + page + index.
10. Native PDF text is extracted with coordinates.
11. PaddleOCR handles pages where OCR is needed.
12. Candidate captions are scored using spatial/textual features.
13. Low-confidence cases use the lightweight fallback matcher.
14. Images with no reliable caption become `caption_not_found`.
15. Every PDF receives its own result directory.
16. JSON is generated.
17. CSV is generated.
18. Images are generated.
19. Dashboard shows results.
20. Individual images can be downloaded.
21. Selected images can be downloaded together.
22. All images can be selected.
23. JSON/CSV downloads work.
24. Errors are understandable.
25. Restart recovery does not lose unfinished jobs.
26. At least the two selected NCERT chapters have been manually inspected.
27. Matching logic has been tuned based on observed NCERT errors.
28. README explains the architecture, setup, algorithm, and limitations.
29. No paid APIs or proprietary inference services are required.
30. The system is demonstrably useful for the assessment's image-caption extraction task.

---

# 51. Absolute Priority Rule

When forced to choose between:

```text
more features
```

and:

```text
better image-caption accuracy
```

choose:

```text
BETTER IMAGE-CAPTION ACCURACY
```

When forced to choose between:

```text
more infrastructure
```

and:

```text
more time tuning the matcher
```

choose:

```text
MORE TIME TUNING THE MATCHER
```

When forced to choose between:

```text
fancy dashboard
```

and:

```text
reliable extraction
```

choose:

```text
RELIABLE EXTRACTION
```

This project succeeds because the core pipeline works, not because it has the most infrastructure.

---

# 52. Immediate Next Steps

Start in this order:

```text
1. Bootstrap Turborepo + Bun
2. Create Next.js app
3. Create Hono app
4. Create shared package
5. Create Python venv
6. Install PyMuPDF
7. Install PaddleOCR/PaddlePaddle CPU
8. Verify OCR on one NCERT page
9. Implement image extraction
10. Implement text extraction
11. Implement caption matching
12. Generate JSON/CSV
13. Implement Hono → Python execution
14. Implement FIFO worker
15. Build dashboard
16. Add downloads
17. Test selected NCERT chapters
18. Tune matching
19. Document limitations
20. Final demo
```

Do not begin with the dashboard.

Begin with:

```text
PDF → images + captions → JSON/CSV
```

That is the core assessment deliverable.
