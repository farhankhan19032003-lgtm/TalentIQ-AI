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

**Sample data (all fictional).** `sample_data/` holds 6 job descriptions (`.txt`, plus a `.docx` copy of one), 35+ resumes (PDF and DOCX, from strong to poor fit), deliberately bad files (corrupt PDF/DOCX, password-protected PDF, fake extension, an image-only scanned PDF for OCR) and `ground_truth/ground_truth.json`. With the app running, load it through the API: `python scripts/load_samples.py` (Docker, port 8080) or `python scripts/load_samples.py --base http://localhost:8000 --jd python_backend_developer --no-bad-files --run`. For a deterministic 3-minute demo use `python scripts/load_samples.py --demo --run`: it loads the Python Backend JD, **15 fictional resumes (8 PDF, 7 DOCX) from strong to poor fit** and 3 edge cases (scanned, corrupt, password-protected) listed in `sample_data/demo_set.json`. Regenerate the files with `python scripts/generate_sample_data.py` (from the repo root).

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

### 50-resume test pack (2026-11-16)
A separate pack of 50 fictional PDF resumes with an answer key (5 intended profile groups of 10, one AI/ML JD) was run through the real UI on an empty database: JD pasted and saved, all 50 PDFs attached through the file chooser, matching run with MiniLM.

| Check | Result |
|---|---|
| Upload | 50 parsed, 0 failed, 0 duplicates (about 1 s) |
| Matching | 50 candidates ranked in 6.6 s (MiniLM, NumPy runtime) |
| "Strong match" group (10) | **all 10 in the top 10**; every one ranked above every Good-with-gaps, Backend/API, ML-focused and Adjacent/weak candidate |
| Other groups vs "Adjacent/weak" | only 75 % of (partial, weak) pairs are ordered correctly; the best "Adjacent/weak" resume ranks 13th and scores 79.7 |
| Experience years vs the key | within 1 year for 39 of 50 resumes (mean absolute difference 0.85 y) |
| Skill extraction vs the key's skill lists | recall 0.94, precision 0.73 (the app also extracts skills such as Agile that the key does not list, so precision is partly the key being short) |

Honest notes: the first run ranked three "Strong match" resumes 24th, 28th and 30th because a role titled "Machine Learning Engineer" was not treated as relevant to an "AI/ML Engineer" job (0 relevant years). That was fixed (title abbreviations are normalised, regression test added) and the numbers above are from the run after the fix, so the fix was made on this same pack. The pack is synthetic and its key is "intended profile", not a human judgement of fit.

### Configuration
Environment variables only (no `.env` auto-loading) — see [.env.example](.env.example). Set `API_KEY` for any shared deployment. `EMBEDDING_BACKEND` defaults to `auto` (options: `auto | minilm | tfidf`); `EMBEDDING_MODEL_DIR` points at the model files (default `backend/storage/models/all-MiniLM-L6-v2`).

## Documentation
[Architecture](docs/ARCHITECTURE.md) · [Matching algorithm](docs/ALGORITHM.md) · [API](docs/API_DOCUMENTATION.md) · [Testing](docs/TESTING.md) · [Security](docs/SECURITY.md) · [Demo script](docs/DEMO_SCRIPT.md) · [Audit report](docs/AUDIT_REPORT.md) · [Checklist](docs/CHECKLIST.md) · [Interview prep](interview_prep/)

## Known limitations
- **PDF fonts:** the PDF reports use bundled Noto Sans + Noto Sans Devanagari (SIL OFL, see `backend/app/assets/fonts/`), so Hindi in names, resume evidence and interview notes is shaped correctly (needs the `uharfbuzz` package; without it Hindi is drawn unshaped). Arabic, Chinese, Japanese and emoji have no bundled font and appear as `?`. A Hindi word glued to Latin text without a space gets a space inserted in the PDF (a reportlab limitation: a space-free word is drawn with one font).
- Benchmarked only on **synthetic** resumes written by the author; ground truth is author-defined; dev set = test set. Results do not predict real-world accuracy.
- On that benchmark the hybrid ranker beats a plain TF-IDF baseline by a **small** margin: mean NDCG@5 **0.943 with TF-IDF** and **0.945 with MiniLM embeddings** vs 0.932 for the plain baseline (random: 0.25). MiniLM vs TF-IDF is +0.002, which is noise on 6 JDs and 35 synthetic resumes (MiniLM is better on 3 JDs, worse on 1 (Java backend 0.878 vs 0.936), equal on 2). The synthetic resumes reuse the JD's own vocabulary, so this set cannot show the benefit of embeddings; on paraphrases with no shared words TF-IDF scores 0.00 while MiniLM scores 0.31 to 0.57 and ranks them well above unrelated text (`tests/test_minilm_numpy.py`).
- The NumPy MiniLM matches the published Sentence-Transformers example scores (three pairs to four decimals) and gives the same vectors whether a text is encoded alone or in a batch (difference below 1e-6), but it has not been compared vector-by-vector against the PyTorch model (torch cannot be installed on the author's machine).
- **PostgreSQL 16.4** was run on Windows (portable binaries, `postgresql+psycopg://...`): the whole backend suite (237 tests, `TEST_DATABASE_URL`), Alembic upgrade/check/downgrade/upgrade, and the 50-resume flow (50 parsed, MiniLM ranking identical to SQLite, max score difference 0.0, reports and interview notes work). Not tested: older/newer Postgres versions, connection pooling under load, Linux/macOS. Install with `pip install "psycopg[binary]"`; on a machine whose Application Control blocks the binary wheel, point psycopg at a PostgreSQL `libpq.dll` (`PSYCOPG_IMPL=python` and its `bin` folder on `PATH`).
- Bare short skill names (`R`, `Go`, `C`) are only recognised as list items; inflections ("recommender") can be missed; vendor "Oracle" can false-positive.
- Skill ontology has 160 hand-edited skills; unlisted skills are invisible to the matcher.
- DOCX has no page numbers; text boxes in DOCX are not extracted; no layout-aware parsing of images/tables inside PDFs.
- PDF parsing runs in-process (no sandbox). No malware scanning.
- No user accounts/roles: a single optional shared API key.
- `docker compose up --build` is **verified** (Docker Desktop on Windows/WSL2: healthy stack, 20-resume flow, same scores). The Render blueprint and Vercel config are provided but **untested**; Linux and macOS hosts are untested. Frontend bundle is ~690 kB (Recharts).
- Candidate availability is not collected, so availability analytics are intentionally empty.
