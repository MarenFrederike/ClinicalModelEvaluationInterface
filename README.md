# Clinical Model Evaluation Interface

A web-based tool for clinicians to evaluate AI-generated radiology reports. Built as part of the SP3 PhD Candidate Assessment (Task 1). Clinicians can rate individual model outputs, compare outputs head-to-head, and mark regions of interest directly on medical images. All results feed into an Elo-based leaderboard and per-axis performance statistics.

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Getting Started](#getting-started)
4. [Docker Deployment](#docker-deployment)
5. [Local Development](#local-development)
6. [First Boot](#first-boot)
7. [Important Notes](#important-notes)

---

## Features

| Feature | Description |
|---|---|
| **Case library** | 6 real-world Radiopaedia radiology cases with clinical prompts, patient context, and representative images |
| **Single-output rating** | Rate a model output across four dimensions: overall quality, clinical accuracy, completeness, and clarity of language |
| **Head-to-head comparison** | Compare two model outputs side-by-side on four clinical axes plus an overall 5-point preference |
| **Smart output selection** | The UI automatically surfaces the least-evaluated output first; compare mode always picks the least-compared pair |
| **Bounding box overlay** | Model attention regions (which image areas influenced the output) are shown as amber boxes overlaid on the case image |
| **Evaluator region marking** | Evaluators can draw their own regions of interest directly on the image by clicking and dragging; regions are saved with the evaluation |
| **Text annotation** | Evaluators can highlight specific text passages in the model output and label them as correct/important (green), wrong (red), or unnecessary (yellow) |
| **Elo leaderboard** | Head-to-head comparisons drive a live Elo ranking of all models |
| **Per-axis statistics** | Win percentages for accuracy, completeness, safety, and reasoning quality per model |
| **Flag system** | Evaluators can flag outputs containing serious errors, hallucinations, or clinically unsafe content |
| **Free-text comments** | Evaluators can leave written feedback alongside numeric ratings |
| **Results dashboard** | Summary statistics, model performance radar chart, Dice score region overlap analysis, and Elo leaderboard — all computed live from the database |

---

## Tech Stack

| Component | Technology |
|---|---|
| Web framework | FastAPI 0.115 + Uvicorn 0.30 |
| Templating | Jinja2 3.1 |
| ORM | SQLAlchemy 2.0 (declarative mapped columns) |
| Database | SQLite (file: `data/db.sqlite`) |
| Image drawing | HTML5 Canvas API (vanilla JS, no framework) |
| Charts | Chart.js 4.4 (Radar + Scatter plots) |
| Form handling | python-multipart 0.0.9 |
| File serving | aiofiles 24.1 |
| Python | 3.14+ |

---

## Getting Started

### Docker Deployment (Recommended)

The only prerequisite is [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone <repo-url>
cd ApplicationProject
docker compose up --build
```

Open your browser at **http://localhost:8080**.

The database is created and fully seeded on the first boot. The `data/` directory is mounted as a named Docker volume (`db_data`), so all evaluations persist across container restarts and rebuilds — **stopping or rebuilding the container never touches the data**.
On that note: even though it is no good practice to load a db into git, it was chosen for this purpose to provide a small example at startup without having to provide a proper server hosting the website. 

**Subsequent starts** (no code changes):
```bash
docker compose up
```

**Rebuild after code changes** (data is preserved):
```bash
docker compose up --build
```

**Full reset** (wipes all evaluations and re-seeds from scratch — use with care):
```bash
docker compose down -v
docker compose up --build
```

---

## Local Development

Requires Python 3.14+.

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
venv\Scripts\uvicorn app.main:app --reload
```

Open your browser at **http://127.0.0.1:8000**.

---

## First Boot

On the very first startup (Docker or local), the app automatically:

1. Creates all database tables in `data/db.sqlite`
2. Detects that the database is empty and runs the seed script
3. Downloads a representative image for each of the 6 cases from Radiopaedia (stored as binary BLOBs in the DB — no files on disk)
4. Inserts 2 model outputs per case (12 total), each with mock bounding boxes

If image downloads fail (e.g. no network access), the cases and outputs are still fully seeded — only the image BLOBs will be missing. The "View image ↗" link to the Radiopaedia viewer will still work.

> **Re-seeding (local dev):** Delete `data/db.sqlite` and restart the server. With Docker, use `docker compose down -v && docker compose up --build` — but note this wipes all submitted evaluations.

---

## Important Notes

- **No authentication.** Clinician IDs are self-reported strings. This is intentional for low-friction research use — not a production deployment.
- **One output can be evaluated multiple times** by different clinicians (or the same clinician). The results page averages across all evaluations for a given output.
- **SQLAlchemy ≥ 2.0.40 required.** Version 2.0.35 is incompatible with Python 3.14 and will crash on startup. The Docker image handles this automatically.
- **Image data is stored in SQLite.** For production use with many cases or high-resolution images, consider migrating image storage to a file system or object store (S3, etc.) and storing only the path in the DB.
- **Database persistence in Docker** is handled by a named volume (`db_data`). Stopping or rebuilding the container does not lose data. Only `docker compose down -v` removes the volume.

---

## For Implementation Details

See [IMPLEMENTATION_DETAILS.md](./IMPLEMENTATION_DETAILS.md) for technical architecture, code structure, database schema, and API routes.
