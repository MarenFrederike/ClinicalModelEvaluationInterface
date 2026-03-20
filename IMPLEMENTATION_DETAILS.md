# Implementation Details — Clinical Model Evaluation Interface

> **⚠️ Disclaimer:** This document is automatically generated and provides a detailed technical overview of the application architecture, code structure, database schema, and API design. It is intended for developers and contributors working on the codebase.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [How It Works — End to End](#how-it-works--end-to-end)
3. [Evaluation Mode 1 — Rate a Single Output](#evaluation-mode-1--rate-a-single-output)
4. [Evaluation Mode 2 — Head-to-Head Comparison](#evaluation-mode-2--head-to-head-comparison)
5. [Bounding Box & Region Marking Feature](#bounding-box--region-marking-feature)
6. [Text Annotation Feature](#text-annotation-feature)
7. [Results & Elo Ranking](#results--elo-ranking)
8. [Dice Score Evaluation](#dice-score-evaluation)
9. [Database Schema](#database-schema)
10. [Seed Data](#seed-data)
11. [API Routes Reference](#api-routes-reference)

---

## Project Structure

```
ApplicationProject/
├── app/
│   ├── __init__.py
│   ├── main.py            # App entry point — lifespan, routing
│   ├── database.py        # SQLAlchemy engine, session factory, Base, get_db()
│   ├── models.py          # ORM table definitions (4 tables)
│   ├── seed.py            # Mock data: 6 cases, 12 model outputs, bounding boxes
│   └── routes/
│       ├── __init__.py
│       ├── cases.py       # All GET page routes + image endpoint + results + Dice computation
│       └── evaluations.py # POST handlers for both evaluation modes
├── app/templates/
│   ├── index.html         # Case list / home page with mode selector
│   ├── pick_output.html   # Output selection screen (before single-rate)
│   ├── evaluate.html      # Single-output rating form + interactive canvas + text annotation
│   ├── compare.html       # Head-to-head comparison form + read-only canvas + 3-button workflow
│   └── results.html       # Statistics dashboard + Elo leaderboard + radar chart + Dice scatter plot
├── static/
│   └── (CSS in templates only)
├── data/
│   └── db.sqlite          # SQLite database (auto-created on first boot)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md              # User-facing documentation
└── IMPLEMENTATION_DETAILS.md (this file)
```

---

## How It Works — End to End

### 1. Startup sequence (`app/main.py`)

`main.py` defines a FastAPI `lifespan` context manager that runs once before the server starts accepting requests:

```
Server starts
  → lifespan() runs
    → SQLAlchemy creates all tables (if they don't exist)
    → seed(db) is called
      → checks if any Cases exist
      → if not: downloads images + inserts all mock data
  → routes registered
  → server begins accepting requests
```

### 2. Database initialisation (`app/database.py`)

Creates a SQLite engine pointing at `data/db.sqlite`. Provides:
- `Base` — the declarative base all ORM models inherit from
- `SessionLocal` — a session factory used by the lifespan and `get_db()`
- `get_db()` — a FastAPI dependency that opens a DB session per request and closes it when the response is sent

### 3. Seed data (`app/seed.py`)

The seed script runs exactly once (it checks `db.query(Case).first()` and returns immediately if any case exists). It:

- Iterates over a `CASES` list of 6 Radiopaedia cases (title, modality, clinical prompt, patient age/sex, image URL)
- For each case: calls `_fetch_image(url)` using `urllib.request` to download a JPEG, stores the raw bytes in `cases.image_data` as a BLOB in the database
- Creates 2 `ModelOutput` rows per case from the `OUTPUTS` dict, each with:
  - A realistic multi-paragraph radiology report (`output_text`)
  - A `bounding_boxes` JSON string listing 2–4 regions the model "attended to" in normalised [0–1] coordinates

### 4. Request handling (`app/routes/cases.py`, `app/routes/evaluations.py`)

All page navigation is handled by GET routes in `cases.py`. All form submissions are handled by POST routes in `evaluations.py`. After a successful POST, the server redirects back to the home page or results (`303 See Other`) so the browser does not re-submit the form on refresh.

---

## Evaluation Mode 1 — Rate a Single Output

### User flow

```
Home (/)
  → click "Rate" on a case
  → GET /cases/{id}/evaluate         — output selection screen
  → click on an output card
  → GET /cases/{id}/evaluate/{oid}   — evaluation form
  → fill in ratings + optionally draw regions + add text annotations + submit
  → POST /evaluations/single/{oid}
  → redirect to / with ?done={case_id}
```

### Output selection screen (`pick_output.html`)

- Lists all model outputs for the case as cards
- Each card shows: model name + version, output type, and a coloured chip showing how many times that output has already been evaluated
  - Green chip = 0 evaluations (never seen)
  - Yellow chip = 1–2 evaluations
  - Grey chip = 3+ evaluations
- The output with the fewest evaluations is sorted **first** and tagged "Recommended" — this nudges evaluators toward the least-covered outputs without forcing a choice
- Sorting is done server-side by querying `COUNT(evaluations.id)` per output

### Evaluation form (`evaluate.html`)

The form contains:

| Field | Type | Required? | Notes |
|---|---|---|---|
| Clinician ID | Text input | Yes | Free-text identifier (e.g. initials). No password. Used to track who submitted what. |
| Overall quality | 1–5 radio (stars) | Yes | 1 = Unacceptable, 5 = Excellent |
| Clinical accuracy | 1–5 radio | No | How factually correct the report is |
| Completeness | 1–5 radio | No | Whether anything clinically important was missed |
| Clarity of language | 1–5 radio | No | Readability and appropriate medical language |
| Comments | Textarea | No | Free text for specific errors, omissions, or suggestions |
| Text annotations | Interactive | No | Select text and label as correct (green), wrong (red), or unnecessary (yellow) |
| Flag | Checkbox | No | Marks the output as containing a serious error or unsafe content |
| Marked regions | Hidden input (JSON) | No | Populated automatically by the canvas drawing tool |

On submission, `evaluations.py`:
1. Validates `output_id` exists
2. Validates `rating` is in [1, 5]
3. Creates an `Evaluation` row with all provided fields
4. Flips `model_output.status` from `"queued"` to `"evaluated"`
5. Commits and redirects

---

## Evaluation Mode 2 — Head-to-Head Comparison

### User flow

```
Home (/)
  → click "Compare ↔" button in Compare mode
  → GET /compare                           — auto-loads globally least-compared pair
  → fill in per-axis + overall preference + submit
  → POST /evaluations/compare/{case_id}
  → (optionally) "Submit & Next" or "Submit & Exit"
  → redirect to / or /compare
```

### Automatic pair selection

The server uses `itertools.combinations(outputs, 2)` to enumerate every possible pair of outputs for the case. For each pair it queries `ComparisonEvaluation` for the count of times that exact pair has been compared (in either direction — `a→b` or `b→a`). The pair with the lowest count is shown.

For the global comparison mode (`/compare`), the function queries **all cases** and their outputs, computes comparison counts for all possible pairs across all cases, and returns the globally least-compared pair.

### Comparison form (`compare.html`)

The form shows both outputs side-by-side and asks for judgement on four clinical axes plus an overall preference:

**Per-axis judgement** (for each of: Accuracy, Completeness, Safety, Reasoning)

Each axis gets a 3-option radio row:
- **A is better**
- **Tie / equal**
- **B is better**

All four axes are optional — evaluators can leave axes blank if they don't feel qualified to judge that dimension.

**Overall preference** (required) — 5-point scale:

| Value | Meaning |
|---|---|
| Strongly prefer A | A is clearly superior overall |
| Slightly prefer A | A is somewhat better |
| Tie | Both outputs are equivalent |
| Slightly prefer B | B is somewhat better |
| Strongly prefer B | B is clearly superior overall |

**Three-button workflow:**
- **✓ Submit & Next** (green) — save comparison and load the next globally least-compared pair
- **↗ Submit & Exit** (blue) — save comparison and return to home page
- **✕ Disregard & Exit** (red) — discard form without saving and return to home

On submission, `evaluations.py` validates that:
- `output_a_id` and `output_b_id` both belong to `case_id`
- Per-axis values (if provided) are in `{"a", "tie", "b"}`
- `overall_preference` is in the valid 5-point set
- The `action` parameter is one of: "next", "exit", "disregard"

A `ComparisonEvaluation` row is then written (unless action is disregard) and the server redirects accordingly.

---

## Bounding Box & Region Marking Feature

### Motivation

The AI model, as part of its reasoning process, identifies which regions of the image most influenced its output. These attention regions are stored alongside the model output and visualised for the evaluator. Evaluators can also mark their own regions of interest — areas they think the model should have attended to, or areas relevant to the clinical question.

### Model attention regions (amber boxes)

- **Stored in:** `model_outputs.bounding_boxes` — a JSON text column
- **Format:** `[{"x": 0.52, "y": 0.42, "w": 0.28, "h": 0.32, "label": "Retroperitoneal mass", "confidence": 0.94}, ...]`
- **Coordinates:** all values are normalised to [0, 1] relative to image width/height. `x` and `y` are the top-left corner of the box.
- **Rendered:** the Jinja2 template injects the stored JSON string directly into a `<script>` block as a JavaScript array literal. The canvas JS reads the image's natural pixel dimensions, scales each box by `canvas.width` / `canvas.height`, and draws labelled rectangles in amber (`#f59e0b`).

### Evaluator-drawn regions (red boxes)

- **Drawn:** on the same canvas using click-and-drag mouse interaction. A dashed red preview box appears while dragging. On mouse up, if the drawn box is larger than 4×4 pixels it is added to an in-memory array `evaluatorBoxes`.
- **Stored in form:** a hidden `<input name="marked_regions">` is updated with `JSON.stringify(evaluatorBoxes)` on every addition or clear. It submits alongside all other form fields.
- **Format:** `[{"x": 0.1, "y": 0.2, "w": 0.15, "h": 0.12}, ...]` — same normalised coordinates, no label or confidence.
- **Stored in DB:** `evaluations.marked_regions` — JSON text column. Saved as `NULL` if no regions were drawn.
- **Clear button:** resets `evaluatorBoxes` and the hidden input without affecting the model boxes.

### Canvas coordinate system

The canvas is sized to the image's **natural** (pixel) dimensions — not the CSS display size. This means drawing is independent of how large the image appears on screen. Mouse positions are converted from CSS pixels to canvas pixels using `getBoundingClientRect()`:

```javascript
const r  = canvas.getBoundingClientRect();
const sx = canvas.width  / r.width;   // scale factor
const sy = canvas.height / r.height;
const canvasX = (mouseEvent.clientX - r.left) * sx;
```

Stored coordinates are then normalised by dividing canvas pixel values by `canvas.width` and `canvas.height`. This makes the data resolution-independent — the same box coordinates work regardless of image size.

### Compare page (read-only canvas)

On the comparison page, both model outputs' bounding boxes are overlaid on the same image:
- **Blue boxes (`#2563eb`)** — Output A attention regions
- **Green boxes (`#16a34a`)** — Output B attention regions

No drawing is available on the compare page — it is display-only, for context.

---

## Text Annotation Feature

### Motivation

While rating individual model outputs, evaluators need a way to highlight and flag specific text passages that are particularly strong, erroneous, or unnecessary. Text annotations provide fine-grained feedback on report quality — which sentences are accurate and important, which contain errors, and which are superfluous.

### Annotation interface

On the evaluation form, below the model output text, evaluators can:

1. **Select text** by clicking and dragging across words in the output (standard browser text selection)
2. **Choose a label** by clicking one of three buttons:
   - **✓ Correct** (green) — text is accurate and clinically important
   - **✗ Wrong** (red) — text contains an error or is clinically inaccurate
   - **⚠ Unnecessary** (yellow) — text is not wrong but not clinically necessary

### Stored data

- **Stored in:** `evaluations.text_highlights` — a JSON text column
- **Format:** `[{"start": 45, "end": 78, "label": "green", "text": "specific words"}, ...]`
  - `start` and `end` are character indices within the full `output_text`
  - `label` is one of: `"green"`, `"red"`, `"yellow"`
  - `text` is the annotated text snippet (for display purposes)
- **Saved as:** JSON string in the database, parsed and rendered on the results page
- **Optional:** evaluations with no annotations store `NULL` in this column

### Interactive UI

- **Real-time list:** as evaluators add annotations, they appear in a numbered list with badges and quoted text
- **Remove individual annotations:** each item has an ✕ button to delete that single annotation
- **Clear all:** a "Clear all" button removes all annotations at once
- **Duplicate prevention:** attempting to highlight the same text twice is rejected with an alert
- **Live preview:** the list updates immediately as annotations are added or removed

### Results display

On the results page, under each evaluation summary, text annotations appear in a collapsible section. Each annotation shows:
- The colored badge (✓/✗/⚠) matching its label
- The quoted text snippet
- Background color matching the label (green/red/yellow)

This allows other clinicians to immediately see which parts of each output were problematic or noteworthy during past evaluations.

---

## Results & Elo Ranking

### Results page (`/results`)

The results page (`results.html`) computes all statistics live from the database on every request. No pre-aggregated tables — everything is derived at query time.

**Summary cards** (top of page):

| Card | Description |
|---|---|
| Total evaluations | Count of all `Evaluation` rows |
| Total cases | Count of all `Case` rows |
| Flagged outputs | Count of evaluations with `is_flagged = true` |
| Models evaluated | Count of unique model keys with ≥1 evaluation |
| Total comparisons | Count of `ComparisonEvaluation` rows |

### Model Performance Radar Chart

A unified radar chart displays model performance across four evaluation dimensions:
- Overall Quality Rating (1–5 scale)
- Clinical Accuracy (1–5 scale)
- Completeness (1–5 scale)
- Clarity of Language (1–5 scale)

Each model is a separate polygon on the same chart with a distinct color. Evaluators can click model names in the legend to toggle their visibility. The chart uses Chart.js for rendering.

### Elo ranking

The Elo system treats each head-to-head `overall_preference` as a match result between two "players" (model versions). The algorithm runs over all `ComparisonEvaluation` rows ordered by `submitted_at`, updating ratings incrementally.

**Score mapping:**

| `overall_preference` | Score for A |
|---|---|
| `strongly_a` | 1.00 |
| `slightly_a` | 0.75 |
| `tie` | 0.50 |
| `slightly_b` | 0.25 |
| `strongly_b` | 0.00 |

**Elo update formula** (K = 32):

```
E_a = 1 / (1 + 10^((elo_b - elo_a) / 400))   # expected score for A
delta = K × (actual_score_a - E_a)
elo_a += delta
elo_b -= delta
```

All models start at Elo 1500. After the first comparison with no prior history, E_a = 0.5 (equal expectation), so winning gives +16 and losing gives −16. As Elo diverges, upsets give larger swings than expected wins.

**Per-axis win percentages:**

Separately from Elo, the system tallies per-axis wins. For each comparison:
- If `axis_accuracy == "a"`, model A gets a win on accuracy; model B gets a loss
- `"tie"` counts as a total++ for both but a win for neither
- Win% = wins / total (shown as "—" if no data)

The leaderboard table shows: Model | Elo | Comparisons | Accuracy% | Completeness% | Safety% | Reasoning%

---

## Dice Score Evaluation

### Motivation

The Dice score (Sørensen–Dice coefficient) measures the spatial overlap between evaluator-marked regions and model attention regions. A higher Dice score indicates better agreement between the evaluator's and model's focus areas.

### Formula

```
Dice = 2 × |Overlap| / (|Region A| + |Region B|)
```

Where:
- `|Overlap|` is the total intersection area between all region pairs
- `|Region A|` is the total area of evaluator-marked regions
- `|Region B|` is the total area of model bounding boxes

The score ranges from 0 (no overlap) to 1 (perfect overlap).

### Implementation

**Backend computation** (`app/routes/cases.py`):
- `compute_dice(region_a_list, region_b_list)` function calculates overlap for all region pairs
- For each pair, determines intersection rectangle using max/min x,y coordinates
- Returns average Dice score across all evaluation pairs for an output
- Called during results computation; results are collected in `dice_data` list

**Display** (`results.html`):
- Scatter plot with X = Case ID, Y = Dice Score (0–1 scale)
- Points colored by model; legend allows toggling visibility
- Axis scaling dynamically adjusts to actual data range with 10% padding
- Tooltip shows exact Dice score and case ID on hover

---

## Database Schema

### `cases`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `title` | VARCHAR(255) | Case name (e.g. "Lung Adenocarcinoma") |
| `clinical_prompt` | TEXT | The question posed to the model |
| `modality` | VARCHAR(50) | CT / MRI / X-ray / Ultrasound |
| `image_path` | VARCHAR(512) | URL to external viewer (Radiopaedia) |
| `image_data` | BLOB | Raw JPEG bytes, served via `/cases/{id}/image` |
| `patient_age` | INTEGER | Anonymised patient age |
| `patient_sex` | VARCHAR(10) | M / F / Other |
| `created_at` | DATETIME | Row creation timestamp |

### `model_outputs`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `case_id` | INTEGER FK → cases | Which case this output belongs to |
| `model_name` | VARCHAR(100) | e.g. "DECIPHER-M" |
| `model_version` | VARCHAR(50) | e.g. "v1", "v2" |
| `output_text` | TEXT | The full model report |
| `output_type` | VARCHAR(50) | "report" \| "answer" \| "annotation" |
| `status` | VARCHAR(20) | "queued" → "evaluated" after first submission |
| `generated_at` | DATETIME | When the output was created |
| `bounding_boxes` | TEXT | JSON: `[{x,y,w,h,label,confidence}, ...]` |

### `evaluations`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `output_id` | INTEGER FK → model_outputs | Which output was rated |
| `clinician_id` | VARCHAR(100) | Self-reported evaluator identifier |
| `rating` | INTEGER | 1–5 overall quality (required) |
| `accuracy` | INTEGER | 1–5 clinical accuracy (optional) |
| `completeness` | INTEGER | 1–5 completeness (optional) |
| `clarity` | INTEGER | 1–5 language clarity (optional) |
| `comments` | TEXT | Free-text feedback (optional) |
| `is_flagged` | BOOLEAN | True if marked as a serious error |
| `marked_regions` | TEXT | JSON: `[{x,y,w,h}, ...]` evaluator-drawn image regions (optional) |
| `text_highlights` | TEXT | JSON: `[{start,end,label,text}, ...]` annotated text spans (optional) |
| `submitted_at` | DATETIME | Submission timestamp |

### `comparison_evaluations`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `case_id` | INTEGER FK → cases | The case both outputs belong to |
| `output_a_id` | INTEGER FK → model_outputs | Left-hand output |
| `output_b_id` | INTEGER FK → model_outputs | Right-hand output |
| `clinician_id` | VARCHAR(100) | Self-reported evaluator identifier |
| `axis_accuracy` | VARCHAR(10) | "a" \| "tie" \| "b" (optional) |
| `axis_completeness` | VARCHAR(10) | "a" \| "tie" \| "b" (optional) |
| `axis_safety` | VARCHAR(10) | "a" \| "tie" \| "b" (optional) |
| `axis_reasoning` | VARCHAR(10) | "a" \| "tie" \| "b" (optional) |
| `overall_preference` | VARCHAR(20) | "strongly_a" \| "slightly_a" \| "tie" \| "slightly_b" \| "strongly_b" |
| `submitted_at` | DATETIME | Submission timestamp |

---

## Seed Data

Six cases from [Radiopaedia.org](https://radiopaedia.org), each with two DECIPHER-M model outputs (v1 and v2):

| Case | Modality | Key findings |
|---|---|---|
| Retroperitoneal Leiomyosarcoma | CT abdomen | Large retroperitoneal mass, ureteric involvement, pulmonary metastases |
| Right MCA Territory Infarct with Dense MCA Sign | CT head | Insular ribbon sign, hyperdense MCA sign |
| Lung Adenocarcinoma | CT chest | Left upper lobe mass, pleural effusion, mediastinal lymphadenopathy |
| Neurovascular Compression — Trigeminal Nerve | MRI brain | AICA–trigeminal nerve contact at root entry zone |
| Croup (Steeple Sign) | X-ray neck/chest | Subglottic narrowing, steeple sign |
| Abdominal Compartment Syndrome | CT abdomen | Massive hepatomegaly, ascites, IVC compression, round belly sign |

Each model output has 2–4 bounding boxes with clinically plausible locations (e.g., the leiomyosarcoma output marks the primary mass, ureteric involvement, and pulmonary metastases). v1 and v2 outputs intentionally differ in their box placement and included findings to simulate real model variation.

---

## API Routes Reference

| Method | Path | Handler | Description |
|---|---|---|---|
| GET | `/` | `cases.index` | Home page — case list with evaluation counts and mode selector |
| GET | `/cases/{id}/evaluate` | `cases.evaluate_select` | Output picker — sorted by eval count asc |
| GET | `/cases/{id}/evaluate/{oid}` | `cases.evaluate_page` | Single-output evaluation form |
| GET | `/compare` | `cases.compare_global` | Head-to-head form — auto-selects globally least-compared pair |
| GET | `/cases/{id}/compare` | `cases.compare_page` | Head-to-head form — auto-selects least-compared pair for specific case |
| GET | `/cases/{id}/image` | `cases.case_image` | Serves image BLOB with `Content-Type: image/jpeg` |
| GET | `/results` | `cases.results_page` | Statistics dashboard + Elo leaderboard + radar chart + Dice scatter |
| POST | `/evaluations/single/{oid}` | `evaluations.submit_single_evaluation` | Submit single-output rating |
| POST | `/evaluations/compare/{case_id}` | `evaluations.submit_comparison` | Submit head-to-head comparison |

All POST routes redirect with HTTP 303 on success.
