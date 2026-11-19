# TalentIQ AI — Evidence-Driven Recruitment Intelligence

Upload resumes (PDF/DOCX), describe a job, and get a **ranked, explainable shortlist** where every score points back to the exact resume text that justifies it. It is **decision support**: it never auto-rejects anyone and a recruiter makes every decision.

Runs fully offline on a CPU-only laptop (8 GB RAM). No paid APIs, no LLM, no Ollama.

> **Honest status.** This is a student/portfolio-grade project, tested on **synthetic** data only. It has **not** been validated on real resumes, has no independent annotation, and is **not** production-ready. See [Known limitations](#known-limitations) and [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md).

## What it does

| Area | Implementation |
|---|---|
| Resume parsing | PDF (PyMuPDF, pdfplumber fallback, two-column reading order, optional Tesseract OCR) and DOCX (headings, layout tables). Name/contact, sections, employment, education, projects, certifications, skills — each with page + source line. |
| Job analysis | Extracts requirements, must-have vs preferred, "X or Y" alternatives, min/preferred years, education level, responsibilities, domains. Fully editable before saving. |
| Matching | Hybrid score (below), skill ontology with synonyms and related-skill partial credit, semantic similarity (all-MiniLM-L6-v2 sentence embeddings, run in pure NumPy when torch is unavailable; TF-IDF only as a labelled fallback). |
| Evidence | Every snippet is a **verbatim substring** of the resume text. Unverifiable snippets are discarded, never invented. |
| Explainability | Per-component points, matched/related/missing skills, "why / why not", missing-information list, score range when evidence is absent. |
| Recruiter tools | Filters, sort, pagination, compare up to 5, notes, status, saved searches, manual override **with required reason** (machine score is never rewritten), what-if simulation, CSV/Excel/PDF reports. |
| Pipeline & discovery | **Pipeline board**: drag candidates across New / Reviewed / Shortlisted / Interview / On hold / Not progressing, with Undo (every move is a recruiter decision and is audit-logged; nothing moves automatically). **Talent matrix**: every candidate scored against every job as a heatmap, with best fit per person, a "most versatile" insight and a top pick per job, with **Export Excel** (heatmap-coloured workbook of exactly what is on screen: filters, sort and blind mode; contact details are never included). **Ctrl/Cmd+K command palette** to jump to any page, job or candidate. **Bulk shortlist** on the Ranking page: tick candidates (or "select all on page" / "select all ≥ 70"), then Shortlist or move them to any stage in one atomic, audit-logged request, with Undo. **Interview notes** on every candidate: structured scorecards (round, date, interviewer, 1–5 stars for technical / communication / problem solving / collaboration, recommendation, strengths, concerns, notes) with an average rating and a tally of what interviewers said (also shown as an "N interviews · ★ avg" chip on Pipeline cards and as a section of the candidate PDF report; the PDF leaves them out in blind-screening mode, and `?interviews=false` omits them). The ranking Excel gets an **Interviews** sheet (one row per scorecard) plus "Interviews" / "Interview avg rating" columns, and the ranking CSV and the Talent matrix Excel get the same two summary columns (numbers only, never text); all of them leave interviews out in blind mode or with `?interviews=false`. They are human opinions: they never change the match score or rank, there is no combined verdict, they are erased with the candidate, and the audit log records ids only, never note text. Toast notifications for actions. |
| Fairness & privacy | Protected-attribute lines scrubbed before matching, blind-screening mode, twin-resume test, PII-free audit log, candidate deletion, retention purge. |
| Security | Magic-byte checks, size/page/zip-bomb limits, active-content PDF rejection, macro rejection, random storage names, prompt-injection flagging, optional API key, CSV formula-injection protection. |

### Screenshots
Placeholders: add your own captures to `docs/screenshots/` before submitting (the demo script in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) visits each of these pages).

| Page | File |
|---|---|
| New job: pasted JD with extracted, editable requirements | `docs/screenshots/01-job-editor.png` |
| Upload: batch of 54 files, one duplicate, two failed, scanned file flagged | `docs/screenshots/02-upload.png` |
| Ranking: Simple view (Candidate / Experience / Match % / Matched Skills) | `docs/screenshots/03-ranking-simple.png` |
| Candidate detail: verdict, profile, experience comparison, why this score | `docs/screenshots/04-candidate.png` |

### Requirements
- **Docker route:** Docker Desktop (Compose v2). Nothing else.
- **Manual route:** Python 3.12+, Node 20+, optional PostgreSQL 16 and optional Tesseract OCR (scanned PDFs). About 1 GB of disk with the embedding model, 8 GB RAM, no GPU.

### Scoring formula

```
Overall = 0.40·Technical + 0.25·Semantic + 0.20·Experience + 0.10·Education + 0.05·Project/Domain
```
Weights are configurable (must sum to 100 %); every other number (credits, thresholds, calibration ranges) lives in `backend/app/core/config.py` and is explained in [docs/ALGORITHM.md](docs/ALGORITHM.md). Components a job does not require are dropped and the rest are renormalised. Missing candidate evidence scores 0 but **widens the score range** (shown as e.g. `62–75`) instead of being treated as a mismatch. Details: [docs/ALGORITHM.md](docs/ALGORITHM.md).

### Architecture

```mermaid
flowchart LR
  UI[React + Vite + Tailwind + Recharts] -- /api --> API[FastAPI]
  API --> SEC[Upload security]
  SEC --> PARSE[PDF/DOCX parser + OCR]
  PARSE --> EXT[Resume extractor + skill extractor + ontology]
  EXT --> DB[(SQLite / Postgres via SQLAlchemy + Alembic)]
  JD[JD analyzer] --> MATCH
  DB --> MATCH[Matching pipeline: skills, semantic, experience, education, projects]
  SIM[MiniLM or TF-IDF similarity] --> MATCH
  MATCH --> RANK[Ranking + sensitivity] --> DB
  DB --> EXPL[Explanation + exports] --> API
```

### Tech stack and why
| Layer | Choice | Why |
|---|---|---|
| UI | React 18 + Vite + TypeScript + Tailwind + Recharts | typed components, fast dev loop, charts for the score breakdown |
| API | FastAPI + Pydantic | automatic validation and OpenAPI docs (`/api/docs`), simple to test with `TestClient` |
| Database | PostgreSQL 16 (SQLite fallback) via SQLAlchemy 2 + Alembic | the assignment prefers PostgreSQL; migrations are versioned; SQLite keeps local setup to zero |
| Parsing | PyMuPDF (+ pdfplumber fallback), python-docx, optional Tesseract OCR | text PDFs, DOCX including tables/text boxes, scanned PDFs when Tesseract is installed |
| Semantic matching | Sentence-Transformers `all-MiniLM-L6-v2` (pure-NumPy runtime included), TF-IDF fallback | small (90 MB), CPU-only, works offline; the fallback is labelled in the UI |
| Skills | hand-edited 160-skill ontology (synonyms, related skills) | explainable, editable, no model needed for exact/related matching |
| Packaging | Docker Compose (db + backend + nginx frontend), Codespaces config | one command to run |

### Data storage

**What is used.** PostgreSQL 16 under Docker Compose (the stack on http://localhost:8080) and in the portable setup from `scripts/setup_postgres.ps1`; plain SQLite (`backend/talentiq.db`) only when no `DATABASE_URL` is set, so the first local run needs no database. The same SQLAlchemy models and Alembic migrations (`backend/alembic/versions`) run on both; the test suite uses SQLite and the migrations were checked against PostgreSQL. Nothing is kept in memory only: candidates, parsed fields with evidence, match runs and results, overrides and the audit log are rows. Original uploaded files go to `backend/storage/` (or the `uploads` volume in Docker) and can be switched off with `STORE_ORIGINAL_FILES=false`.

**Why a relational database.** Every score has to be traceable: a result row points to its run, its candidate, its per-component scores and its evidence lines, and runs are immutable snapshots (`MatchRun.job_snapshot`). That is joins and constraints (`uq_resume_hash`, `uq_run_candidate`), which a relational schema gives for free.

**Replacing it.** Only `app/core/database.py` (engine and session) and `app/models/db.py` know the database. Another SQL engine is a `DATABASE_URL` change plus `alembic upgrade head`. MongoDB would mean rewriting `models/db.py` and the queries in `app/api/*` and `services/pipeline.py` against a document model: one `candidates` document with embedded skills, employment and education, a `match_runs` collection holding results as embedded arrays, and a unique index on `file_hash`. It is not implemented and not needed for this scope; the trade-off is that cross-run queries (rank history, audit joins) become aggregation pipelines.

**Accounting for every file.** `GET /api/resumes/accounting?job_id=` returns files received, stored, parsed, failed, identical duplicates skipped (byte-identical files are not stored twice; each skip is recorded in the audit log and listed), how many parsed resumes the latest ranking covers, and how many are not in it. The Ranking page shows the same line and, when resumes were uploaded after the last run, a "N parsed resumes are not ranked, re-run" banner.

### Project structure
```
backend/app/
  api/          FastAPI routers: jobs, resumes, matching, misc (reports, settings, analytics), shared row builders (views.py)
  core/         config.py (ALL scoring weights, credits, thresholds and calibration ranges), database.py, errors.py
  models/       SQLAlchemy tables      schemas/  request/response models
  services/     document_parser.py     PDF/DOCX -> text (OCR, text boxes, tables)
                resume_extractor.py    text -> name, contact, employment (dates), education, projects, skills
                skill_extractor.py     ontology lookup, synonyms, listed-vs-context evidence
                jd_analyzer.py         job text -> requirements, years, education
                matching_pipeline.py   per-candidate scoring (the 5 components)
                experience_analyzer.py month-set experience arithmetic + role relevance
                semantic_matcher.py    MiniLM / TF-IDF similarity and calibration
                ranking_engine.py      weights, final score, ranking, weight sensitivity
                explanation_engine.py  headline, why matched / why not, per-component points
                pipeline.py            ingestion + run orchestration      exports.py  CSV/Excel/PDF reports
  data/         skill_ontology.json (+ editable source table)
backend/tests/  pytest suite (parsing layouts, scoring bands, API, security, eval regression)
backend/eval/   benchmark runner and recorded results
frontend/src/   pages/ (Jobs, Upload, Ranking, Candidate, ...), components/, utils.ts, types.ts, test/
sample_data/    fictional JDs and resumes, bad-file cases, ground truth, demo_set.json
scripts/        load_samples.py, generate_sample_data.py, fetch_minilm.py, build_ontology.py
docs/           ALGORITHM.md, ARCHITECTURE.md, API_DOCUMENTATION.md, DEMO_SCRIPT.md, INTERVIEW_PREP.md, ...
```

### API endpoints (full reference: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md), live docs at `/api/docs`)
| Method and path | Purpose |
|---|---|
| `POST /api/jobs/analyze` · `POST /api/jobs/extract-text` | preview the extraction for pasted text / read text from an uploaded PDF, DOCX or TXT JD |
| `POST /api/jobs` · `GET/PUT/DELETE /api/jobs/{id}` | save, read, edit (requirements, min years, qualification) and delete a job |
| `POST /api/resumes/upload` | batch upload (multipart `files`): per-file `parsed` / `failed` / `rejected` / `duplicate`, plus `needs_review` |
| `GET /api/resumes/accounting?job_id=` | every file accounted for: received, parsed, failed, duplicates skipped (listed), ranked vs not yet ranked |
| `GET /api/resumes` · `GET /api/resumes/{id}` · `POST /api/resumes/{id}/retry` · `DELETE /api/resumes/{id}` | list, diagnostics, retry, delete |
| `POST /api/matching/run/{job_id}` | score and rank every parsed candidate (custom weights optional) |
| `GET /api/matching/results/{job_id}` | the ranking table (filters, sort, pagination) |
| `GET /api/matching/candidate/{id}?job_id=` | candidate detail: extracted data, components, requirements, experience, explanation |
| `GET /api/matching/compare` · `POST /api/matching/whatif/{job_id}` | side-by-side compare, weight what-if |
| `GET /api/reports/{job_id}/csv\|excel\|pdf` | exports (contact details excluded in blind mode) |
| `PATCH /api/candidates/{id}/status` · `POST /api/matching/results/{id}/override` | recruiter decisions (audit-logged, never automatic) |
| `GET /api/health` · `GET /api/settings` | status (embedding backend, OCR) and the live scoring configuration |

## Quick start (Windows PowerShell)

Prerequisites: Python 3.12+ (the pinned numpy 2.5 needs it), Node 20+ (tested with Node 22). Optional: [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) for scanned PDFs.

```powershell
# 1. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python ..\scripts\fetch_minilm.py   # one time, about 90 MB: the sentence-embedding model (hash-verified). Without it the app uses TF-IDF and says so
alembic upgrade head          # optional: the app also creates tables on startup
python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend (new PowerShell window)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

**PostgreSQL (recommended, as the assignment prefers).** `.\scripts\setup_postgres.ps1` installs a portable PostgreSQL 16.4 into `~/talentiq-pg` (no admin rights); after that `.\start.ps1` starts it on port 5433, creates the `talentiq` database and runs the app on it. Without it the app falls back to SQLite. On a machine whose Application Control blocks the `psycopg` binary wheel, `start.ps1` sets `PSYCOPG_IMPL=python` and uses PostgreSQL's own `libpq.dll`.

Open http://localhost:5173 → **Jobs → New job** (paste or upload a JD, review the extracted requirements, Save) → **Upload resumes** (PDF/DOCX, 10+ per batch) → **Ranking → Run matching**. The app starts empty and ships no demo data in the UI: it only shows resumes you upload, so use files you have the right to process. The fictional files in `sample_data/` exist for the automated tests and the benchmark only. API docs: http://localhost:8000/api/docs.

**Semantic matching.** The semantic component uses the sentence-embedding model all-MiniLM-L6-v2. `python scripts/fetch_minilm.py` downloads it once (about 90 MB, every file checked against the hash Hugging Face publishes) into `backend/storage/models/`. The app runs it with `sentence-transformers` when that is installed, and otherwise with its own **pure-NumPy implementation of the same model** (`backend/app/services/minilm_numpy.py`: same weights, same WordPiece tokenizer, mean pooling, 256-token limit; no torch needed, so it works on any Python version and on locked-down machines). `EMBEDDING_BACKEND=auto` (the default) uses MiniLM when the model files exist and otherwise falls back to TF-IDF, and the ranking page says which one was used and why. `EMBEDDING_BACKEND=tfidf` forces TF-IDF, `minilm` insists on MiniLM.

**Sample data (all fictional).** `sample_data/` holds 6 job descriptions (`.txt`, plus a `.docx` copy of one), 35+ resumes (PDF and DOCX, from strong to poor fit), deliberately bad files (corrupt PDF/DOCX, password-protected PDF, fake extension, an image-only scanned PDF for OCR) and `ground_truth/ground_truth.json`. With the app running, load it through the API: `python scripts/load_samples.py` (Docker, port 8080) or `python scripts/load_samples.py --base http://localhost:8000 --jd python_backend_developer --no-bad-files --run`. For the larger **50-resume pack** (`sample_data/pack50/`, files named `resume_XX_name`, 42 PDF + 8 DOCX, plus edge cases) use `python scripts/load_samples.py --pack50 --run`; to wipe the database and uploads first and reload only synthetic data use `python scripts/reset_demo_data.py` (asks for confirmation; `--local` for a non-Docker run). For a deterministic 3-minute demo use `python scripts/load_samples.py --demo --run`: it loads the Python Backend JD, **15 fictional resumes (8 PDF, 7 DOCX) from strong to poor fit** and 3 edge cases (scanned, corrupt, password-protected) listed in `sample_data/demo_set.json`. Regenerate the files with `python scripts/generate_sample_data.py` (from the repo root).

### Run with Docker (one command)

```powershell
docker compose up --build        # then open http://localhost:8080
docker compose down -v           # stop and delete the database and uploads
```
Three containers: **PostgreSQL 16**, the **FastAPI backend** (Python 3.13, Tesseract OCR, the MiniLM model baked into the image and hash-checked at build time, Alembic migrations on start, non-root user, health check) and the **React frontend served by nginx**, which proxies `/api` to the backend. The first build takes several minutes (it downloads the 90 MB model). Verified on Docker Desktop (Windows, WSL2): the stack came up healthy, the 20-resume flow (JD upload, 20 PDF/DOCX resumes, bad-file handling, ranking, candidate page, blind mode) gave the same scores as the non-Docker run, similarity method `minilm`, Alembic at head. The image contains no sample data. Set `POSTGRES_PASSWORD` and `API_KEY` for anything beyond a local demo.

### Run in GitHub Codespaces (no local install)

On the repository page choose **Code, Codespaces, Create codespace on main**. The `.devcontainer/` config installs Docker inside the Codespace, builds the same `docker compose` stack and starts it. The first start takes several minutes (it builds the images and downloads the 90 MB MiniLM model); later starts reuse the images. When it is ready, open the **Ports** tab and click the globe icon next to port **8080** ("TalentIQ AI"). The app starts empty: upload a JD and resumes as usual. The port is private to your GitHub account by default; if you make it public to share a demo link, anyone with the link can use the app and see what is uploaded, so use only fictional resumes and switch it back to private afterwards. Codespaces has a free monthly quota and stops after inactivity, so the link only works while the Codespace is running. This setup was written to match the verified compose stack but has not been run on GitHub's infrastructure yet.

### Tests and lint

```powershell
cd backend ; python -m pytest -q          # backend suite
cd ..\frontend ; npm test                 # component/unit tests
cd ..\backend ; python eval\run_evaluation.py --backend minilm --tag mine  # benchmark (use --backend tfidf to compare)
ruff check app tests eval                 # lint (rules in backend/ruff.toml)
```
See [docs/TESTING.md](docs/TESTING.md) for what each suite covers and the latest recorded results.

### 50-resume synthetic pack (measured 2026-11-19)
`sample_data/pack50/` holds 50 fictional resumes named `resume_XX_firstname_lastname` (42 PDF, 8 DOCX; e-mails `name@example.com`) from strong to unrelated fit for the *Python Backend Developer* JD, plus `edge_cases/` (password-protected, corrupt, scanned, byte-identical duplicate) and `manifest.json` (the intended family and tier of each file). Regenerate with `python scripts/generate_pack50.py`; load with `python scripts/load_samples.py --pack50 --run`; wipe everything and reload with `python scripts/reset_demo_data.py`.

Result on a fresh Docker stack (54 files in one upload): **51 parsed, 2 failed (corrupt, password-protected), 1 duplicate skipped**, 51 ranked in 4.0 s (MiniLM). Mean score by intended group:

| Intended group (n) | Mean score | Range |
|---|---|---|
| Backend, strong evidence (6) | 89.7 | 89.2 - 90.0 |
| Backend, medium evidence (3) | 87.7 | 87.5 - 88.1 |
| Flask/MySQL instead of FastAPI/PostgreSQL (4) | 60.8 | 59.1 - 61.9 |
| DevOps, strong (3) | 60.0 | 59.7 - 60.2 |
| Backend fresher, thin evidence (3) | 53.7 | 52.3 - 55.6 |
| ML / full-stack / Java / data analysts (23) | 13 - 35 | 11.7 - 35.3 |
| Sales and accounting (5) | 10.7 - 11.3 | 10.5 - 12.0 |

The 9 backend resumes with real FastAPI/PostgreSQL evidence take ranks 1-9; related-skill resumes follow; unrelated careers are below 40. **Imperfect:** the generator makes "strong" and "medium" backend resumes differ by only one bullet, so those two groups are not separated by the score (89.7 vs 87.7); and the pack is generated from templates by the same author as the matcher, so this shows the pipeline behaves consistently, not that it works on real resumes. Two summary-only freshers (Aman Yadav, Kunal Bose) are shown with a "(profile)" role and a needs-review flag.

### Configuration
Environment variables only (no `.env` auto-loading); [.env.example](.env.example) lists them. Set `API_KEY` for any shared deployment.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./talentiq.db` (Docker Compose: PostgreSQL) | any SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `EMBEDDING_BACKEND` | `auto` | `auto` = MiniLM if its files exist, else TF-IDF (the run records and shows why); `minilm` / `tfidf` force one |
| `EMBEDDING_MODEL`, `EMBEDDING_MODEL_DIR` | `sentence-transformers/all-MiniLM-L6-v2`, `backend/storage/models/all-MiniLM-L6-v2` | model name and the folder `scripts/fetch_minilm.py` fills (about 90 MB, hash-checked) |
| `UPLOAD_DIR`, `STORE_ORIGINAL_FILES` | `./storage/uploads`, `true` | where original resumes are kept; `false` stores parsed data only |
| `MAX_UPLOAD_MB`, `MAX_PDF_PAGES`, `MAX_BATCH_FILES` | `5`, `30`, `60` | upload limits |
| `OCR_ENABLED` | `true` | use Tesseract for scanned PDFs when installed |
| `API_KEY` | empty (no auth) | shared key required by every API call when set |
| `RETENTION_DAYS` | `0` | `0` keeps data until a recruiter deletes it |
| `CORS_ORIGINS` | `http://localhost:5173,...` | allowed browser origins in dev |
| `POSTGRES_PASSWORD` | `talentiq` | Docker Compose database password; change it outside a laptop demo |

**Offline behaviour.** Nothing calls an external service at run time. If the embedding model files are missing, matching still works with TF-IDF similarity; the ranking page then says "TF-IDF fallback" and the reason. The Docker image already contains the model.

## Documentation
[Architecture](docs/ARCHITECTURE.md) · [Matching algorithm](docs/ALGORITHM.md) · [API](docs/API_DOCUMENTATION.md) · [Testing](docs/TESTING.md) · [Security](docs/SECURITY.md) · [Demo script](docs/DEMO_SCRIPT.md) · [Audit report](docs/AUDIT_REPORT.md) · [Checklist](docs/CHECKLIST.md) · [Interview prep](docs/INTERVIEW_PREP.md) · [Older notes](interview_prep/)

## Known limitations
- **PDF fonts:** the PDF reports use bundled Noto Sans + Noto Sans Devanagari (SIL OFL, see `backend/app/assets/fonts/`), so Hindi in names, resume evidence and interview notes is shaped correctly (needs the `uharfbuzz` package; without it Hindi is drawn unshaped). Arabic, Chinese, Japanese and emoji have no bundled font and appear as `?`. A Hindi word glued to Latin text without a space gets a space inserted in the PDF (a reportlab limitation: a space-free word is drawn with one font).
- Benchmarked only on **synthetic** resumes written by the author; ground truth is author-defined; dev set = test set. Results do not predict real-world accuracy.
- On that benchmark the hybrid ranker beats a plain TF-IDF baseline by a **small** margin: mean NDCG@5 **0.943 with TF-IDF** and **0.945 with MiniLM embeddings** vs 0.932 for the plain baseline (random: 0.25). MiniLM vs TF-IDF is +0.002, which is noise on 6 JDs and 35 synthetic resumes (MiniLM is better on 3 JDs, worse on 1 (Java backend 0.878 vs 0.936), equal on 2). The synthetic resumes reuse the JD's own vocabulary, so this set cannot show the benefit of embeddings; on paraphrases with no shared words TF-IDF scores 0.00 while MiniLM scores 0.31 to 0.57 and ranks them well above unrelated text (`tests/test_minilm_numpy.py`).
- The NumPy MiniLM matches the published Sentence-Transformers example scores (three pairs to four decimals) and gives the same vectors whether a text is encoded alone or in a batch (difference below 1e-6), but it has not been compared vector-by-vector against the PyTorch model (torch cannot be installed on the author's machine).
- **PostgreSQL 16.4** was run on Windows (portable binaries, `postgresql+psycopg://...`): the whole backend suite (237 tests at the time, `TEST_DATABASE_URL`; the suite has 275 tests now and the latest run was on SQLite inside Docker), Alembic upgrade/check/downgrade/upgrade, and the 50-resume flow (50 parsed, MiniLM ranking identical to SQLite, max score difference 0.0, reports and interview notes work). Not tested: older/newer Postgres versions, connection pooling under load, Linux/macOS. Install with `pip install "psycopg[binary]"`; on a machine whose Application Control blocks the binary wheel, point psycopg at a PostgreSQL `libpq.dll` (`PSYCOPG_IMPL=python` and its `bin` folder on `PATH`).
- Bare short skill names (`R`, `Go`, `C`) are only recognised as list items; inflections ("recommender") can be missed; vendor "Oracle" can false-positive.
- Skill ontology has 160 hand-edited skills; unlisted skills are invisible to the matcher.
- DOCX text boxes are read, but a DOCX has no page numbers; no layout-aware parsing of images/tables inside PDFs.
- PDF parsing runs in-process (no sandbox). No malware scanning.
- No user accounts/roles: a single optional shared API key.
- `docker compose up --build` is **verified** (Docker Desktop on Windows/WSL2: healthy stack, 20-resume flow, same scores). The Render blueprint and Vercel config are provided but **untested**; Linux and macOS hosts are untested. Frontend bundle is ~690 kB (Recharts).
- Candidate availability is not collected, so availability analytics are intentionally empty.
