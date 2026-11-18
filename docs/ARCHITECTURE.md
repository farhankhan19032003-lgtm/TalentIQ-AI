# Architecture

## Components
```
frontend/ (React 18, Vite, TS, Tailwind, Recharts, React Router, Axios, Lucide)
   └─ /api proxy ─▶ backend/app (FastAPI)
        api/        routers: jobs, resumes, matching, misc (analytics, reports, audit, settings, ontology, demo)
        services/   security → document_parser → resume_extractor/skill_extractor → pipeline
                    jd_analyzer, experience_analyzer, semantic_matcher, matching_pipeline,
                    ranking_engine, explanation_engine, exports
        models/     SQLAlchemy ORM (15 tables)         alembic/  migration 0001
        data/       skill_ontology_source.txt → skill_ontology.json (160 skills)
```

## Request flow: resume upload
1. `validate_upload`: extension allow-list, size limit, magic bytes, PDF active-content (`/JavaScript`, `/Launch`…), DOCX macro and zip-bomb checks.
2. File stored under a random name (original name is sanitised and kept only as metadata).
3. `parse_pdf` / `parse_docx` → pages of text with reading order, per-page quality, OCR if a page is scanned.
4. `resume_extractor` scrubs protected-attribute lines, detects sections, extracts fields with **page + source line + method + confidence**.
5. `skill_extractor` finds skills (exact / alias / context) using the ontology; each mention keeps its snippet, section and whether it is a "listed only" mention.
6. A candidate row and child rows (skills, employment, education, projects) are stored. Per-file errors are caught, classified (`corrupt`, `password_protected`, `unsupported_type`, `signature_mismatch`, `file_too_large`…) and returned in the batch result; the rest of the batch continues. A duplicate file (SHA-256) is reported without re-parsing; same-email duplicates are flagged.

## Request flow: matching
`POST /api/matching/run/{job_id}` → for each candidate `match_candidate` computes five components and per-requirement evidence → `compute_overall` → `rank` (overall desc, technical desc, candidate id asc: deterministic) → `sensitivity` (11 weight-perturbation scenarios) → explanation → persisted as `MatchRun` + `MatchResult` + `ScoreComponent` + `EvidenceItem`. The job snapshot, weights, algorithm version and similarity method are stored with the run so results are reproducible and auditable.

## Key design decisions
| Decision | Reason |
|---|---|
| Rule-based extraction + ontology instead of an LLM | Runs on a CPU laptop, deterministic, every output traceable to text. |
| Evidence must be a verbatim substring of the resume | Prevents fabricated quotations; failed checks are surfaced as `failed_verification`. |
| Missing evidence ≠ mismatch (score range) | A resume without an Education section should not look like "no degree". |
| TF-IDF fitted on the JD + ontology texts only | Scores do not change when other candidates are uploaded (MiniLM embeddings are per-text, so they are pool-independent too). |
| MiniLM run by a bundled pure-NumPy implementation when sentence-transformers is missing | Real sentence embeddings without torch, which is not installable everywhere (see `docs/ALGORITHM.md`). |
| Dates/separators stripped before semantic similarity | Removed a formatting-sensitivity bug (twin resumes differed by 0.8 points before the fix). |
| Overrides stored separately | The machine score and rank stay auditable; the recruiter's decision is visible next to it. |
| SQLite default, Postgres-compatible | Zero setup locally; SQLAlchemy 2 + Alembic keep the schema portable (verified on PostgreSQL 16.4). |

## Data model (tables)
`jobs`, `candidates`, `resumes`, `extracted_skills`, `employment`, `education`, `projects`, `match_runs`, `match_results`, `score_components`, `evidence_items`, `manual_overrides`, `candidate_notes`, `saved_searches`, `audit_logs`. Deleting a candidate cascades to all child rows and removes the stored file.

## Error handling
All errors use one envelope `{"error": {"code", "message", "details"?}}`. Unexpected exceptions return a generic `internal_error` (no paths or stack traces); details go to the server log only.
