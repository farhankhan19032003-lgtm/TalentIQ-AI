# Testing

## How to run
```powershell
cd backend ; python ..\scripts\fetch_minilm.py   # once: the embedding model (without it the MiniLM tests are skipped)
python -m pytest -q                         # 265 tests collected
ruff check app tests eval                   # lint (backend/ruff.toml)
cd ..\frontend ; npm test                   # 37 tests
cd ..\backend ; python eval\run_evaluation.py --backend minilm --tag mine   # and --backend tfidf to compare
```

## Latest run (2026-11-18, after the parsing and scoring-calibration work)
| Check | Result |
|---|---|
| Backend pytest (Docker image, Python 3.13, SQLite test DB) | **265 passed** (new: `test_resume_layouts.py` 19 tests over 14 layouts, `test_scoring_calibration.py` 8 tests incl. strong/medium/weak bands under TF-IDF and MiniLM and an API regression for merged requirements) |
| `ruff check app tests eval` | all checks passed |
| Frontend `tsc --noEmit` / vitest | clean / **37 passed** (new: `skillchips.test.tsx`: exact, related and missing chips look different; experience and education verdicts) |
| Browser run of `docs/DEMO_SCRIPT.md` on a fresh `docker compose` stack (Playwright + Chrome, upload through the file chooser) | 7/7 steps OK, 0 console errors, 0 failed HTTP calls |
| Parsing vs answer key (34 parsable synthetic resumes) | name 34/34, email 34/34, experience years 34/34, education level 34/34 |
| Scoring vs author grades (204 graded JD/resume pairs, MiniLM, `eval/calibration_report.py`) | 89.2 % of ordered pairs correct; grade-3 median 84.9, grade-0 median 16.4; semantic component saturated for 0 of 204 pairs (see `docs/ALGORITHM.md`, Calibration) |

The local Windows venv cannot run scipy (blocked by an Application Control policy), so the backend suite above ran inside the Docker image. The older recorded results below are from 2026-11-16 and predate these changes.

## Earlier recorded results (Windows, Python 3.15, 2026-11-16; MiniLM via the pure-NumPy runtime)
| Suite | Result |
|---|---|
| Backend pytest | **237 passed, 0 skipped** (the conftest forces TF-IDF for the older tests; `test_minilm_numpy.py` and the MiniLM test in `test_semantic_matching.py` use the real model) |
| Frontend vitest | **31 passed** |
| Browser end-to-end on a clean database (Edge driven through the DevTools protocol) | JD **PDF** uploaded through the file chooser, job saved, **12 resumes (6 PDF + 6 DOCX)** uploaded through the file chooser, matching run with MiniLM, ranking table read, top candidate opened: every step worked. Details below |
| `tsc --noEmit` + `vite build` | clean / success |
| Browser end-to-end (Playwright driving Chrome against the real servers) | **21/21 steps passed**; no failed API calls, no backend errors logged |
| Alembic | upgrade → check → downgrade → upgrade all succeeded |

The browser script is shipped as a **manual tool**: `scripts/e2e_browser_check.py` (needs `pip install playwright`, an empty DB, both servers running). It is not part of `pytest`. Of 5 runs in the sandbox, 4 passed 21/21; 1 failed several steps and its first failure was not captured (cause unknown, probably timing).

## What each backend file covers
| File | Covers |
|---|---|
| `test_document_parser.py` | PDF/DOCX parsing, 2-column order, layout tables, scanned/encrypted/corrupt classification, text normalisation |
| `test_security.py` | magic bytes, size limit, active content, macros, zip bomb, path traversal, injection flagging |
| `test_skills_and_jd.py` | skill extraction (ambiguous/case-sensitive/negation), proficiency, JD requirements, `any_of`, importance |
| `test_experience_scoring.py` | month-union maths, part-time/internship weighting, uncertain dates, score recomputation, weights validation |
| `test_semantic_matching.py` | cosine properties, TF-IDF independence from the pool, calibration, fallback behaviour |
| `test_matching_engine.py` | match types and credits, evidence verification, formula reproduction, format independence, explanation grounding |
| `test_api.py` | 41-file batch, bad files, duplicates, jobs CRUD, ranking/filter/sort/pagination, candidate detail, **all stored evidence is verbatim resume text**, DB persistence, compare, what-if non-mutation, notes/status/override, analytics, CSV/Excel/PDF, blind mode, audit log without PII, deletion, retention, API key, safe 500s |
| `test_fairness_eval.py` | twin resumes score identically, protected attributes not stored, explanations contain no demographic terms, **benchmark regression floors** |
| `test_migrations.py` | Alembic matches the models |

## Independent score verification
`test_overall_equals_documented_formula` recomputes the overall score from the stored components with a separate arithmetic path, and the evaluation harness re-checks **210/210** stored results the same way. This verifies the *arithmetic*, not whether the weights are *right*.

## Evaluation benchmark (synthetic) — read the caveats
Ground truth is defined by construction when the resumes are generated, then reviewed by the author. Not independent. The ontology was refined after viewing errors on the same set, so skill metrics are optimistic.

| Metric (final run, TF-IDF) | Value |
|---|---|
| Parseable files parsed | 34 / 34; 6 / 6 failure cases classified correctly |
| Skill extraction micro P / R / F1 | 0.996 / 0.989 / 0.993 (272 TP, 1 FP, 3 FN) |
| Name / email accuracy | 1.00 / 0.97 |
| Effective-experience accuracy (±0.1 y) | 1.00 (35 resumes) |
| JD skill F1 / importance accuracy | 0.978 / 0.986 |
| Mean NDCG@5 hybrid vs TF-IDF baseline vs random | 0.943 vs 0.932 vs 0.253 |
| Precision@5 hybrid and baseline | 0.80 / 0.80 |
| Twin resumes max score difference | 0.0 |
| Rank unchanged under ±10 pp weight perturbation | 51 % of results (rank sensitivity is real) |
| Mean parse / match time | 29 ms per resume / 0.43 s per JD for 35 candidates |

Hybrid vs baseline: +0.012 NDCG@5 on a 6-JD synthetic set is **not** evidence of a real advantage; on the AI/ML JD the baseline is better (0.884 vs 0.871). The title-core weighting raised NDCG from 0.9425 to 0.9434 and was kept; further tuning was stopped to avoid overfitting the benchmark.

### Same benchmark with MiniLM sentence embeddings (2026-11-16)
| Job | Hybrid + TF-IDF | Hybrid + MiniLM (NumPy) |
|---|---|---|
| AI/ML Engineer | 0.871 | **0.890** |
| Python backend | 0.956 | **1.000** |
| Data analyst | 0.968 | **0.973** |
| Java backend | **0.936** | 0.878 |
| Cloud DevOps | 1.000 | 1.000 |
| Full stack | 0.929 | 0.929 |
| **Mean NDCG@5** | 0.9434 | **0.9452** (plain TF-IDF baseline 0.9316, random 0.25) |

+0.002 is noise on 6 JDs and 35 synthetic resumes; the set reuses each JD's own wording, so it cannot show what embeddings add. That is shown separately: for paraphrases with no shared words TF-IDF scores 0.00 and MiniLM 0.31–0.57 (`test_embeddings_beat_tfidf_on_paraphrases_with_no_shared_words`). Match time per JD for 35 candidates: 0.4 s (TF-IDF) vs 1.6 s (MiniLM, first run; embeddings are cached).

### Browser end-to-end on a clean database (what was actually done)
A second backend (port 8001, empty SQLite file and upload folder) and a second Vite server (port 5174, proxied to it) were started so the real data was never touched. Then, in one Edge page: New job → attached a **PDF** job description (title, 7 must-have, 5 preferred skills, "5+ years" and "Bachelor's" were filled in) → Save job → **Rank** → Upload resumes → attached **12 files at once** (6 PDF, 6 DOCX) → "12 parsed, 0 failed, 0 duplicate" → Run matching (3.7 s, "MiniLM sentence embeddings") → ranking table with **Candidate, Experience, Match % and Matched skills (names)** → opened rank 1: contact, overall score, component scores, requirement evidence with matched and missing skills, experience comparison ("9.4 y of 9.4 y, required 5+ y") and "Why this score". The driver scripts are not shipped (they were throwaway).

A bug this exposed afterwards, on real data: MiniLM similarities were `numpy.float32`, which cannot be stored in the JSON columns of a match result, so matching crashed for one job (it only happens on certain resumes, not on the sample set). Fixed by returning `float64`; `test_similarities_are_plain_python_compatible_floats` guards it.

## 50-resume test pack (2026-11-16)
`AI_ML_Resume_Test_Pack_50` (50 fictional PDFs, answer key with 5 groups of 10, AI/ML JD). Run in Edge through the DevTools protocol on an empty database (port 8001): JD pasted, saved, 50 PDFs attached in one file-chooser action, matching run.

* Upload 50 parsed / 0 failed; matching 6.6 s with MiniLM.
* After the fix below: Strong match 10/10 in the top 10 (ranks 1-10); Strong above every other group in 100 % of pairs; (Good + Backend + ML-focused) above Adjacent/weak in only 75 % of pairs; best Adjacent/weak resume is #13 (79.7).
* Experience: within 1 year of the key for 39/50 (mean abs. difference 0.85 y). Skills vs key: recall 0.94, precision 0.73.
* Bug found: a role titled "Machine Learning Engineer" counted as 0 relevant years for an "AI/ML Engineer" job (relevance needs 2 skills, or 1 skill plus a title word, and "ML" is not a word of "Machine Learning"). Three strong candidates ranked 24/28/30. Fixed in `experience_analyzer.title_tokens_of`; test `test_title_abbreviations_count_as_the_same_field`. The fix was made on this pack, so these numbers are not an unbiased estimate.
* Interview-notes form tested in the browser on the same isolated setup: create, validation (Save disabled when empty), edit, delete, Cancel on the delete confirmation (note kept), Cancel on the form (nothing saved), HTML shown as text, Hindi text, match score and rank unchanged.

## PostgreSQL run (2026-11-16)
PostgreSQL 16.4 (portable Windows binaries, port 5433) with `psycopg` 3 on the PostgreSQL `libpq.dll` (the binary wheel is blocked by Application Control on this machine).
* `TEST_DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5433/talentiq_test python -m pytest -q` -> **237 passed** (1924 match results stored; `detail`/`explanation` are `json` columns). `test_migrations` still uses SQLite by design.
* `alembic upgrade head` -> `alembic check` ("No new upgrade operations detected") -> `downgrade base` -> `upgrade head` on an empty Postgres database: 17 tables, no errors.
* Real server on Postgres: JD analysed and saved, 50 PDFs uploaded (50 parsed, 1.3 s), MiniLM matching 4.4 s. All 50 scores equal the SQLite run (max difference 0.0). PDF/CSV/Excel reports, candidate PDF, interview create/delete and the audit log work.
* Not covered: other Postgres versions, concurrent users, pooling.

## Why the best "Adjacent/weak" resume ranks 13th (looked into, not tuned)
Akhil Kapoor (key label "Adjacent/weak", title Data Analyst) lists Python, SQL, FastAPI, MLflow, Spark and Computer Vision, so he really matches 6 of 8 requirements (MLflow counts as MLOps) and has 3 relevant years; the key labels him by job title, the app scores the evidence. This is a limit of the answer key, not a defect I fixed; changing the weights to push him down would be fitting the benchmark.

## Not tested
Real-world resumes; Docker; PostgreSQL versions other than 16.4 and pooling under load; Word/PowerPoint report rendering (no Office or LibreOffice here; only the file contents were checked); Linux/macOS runtime of the latest code (developed and run on Windows here); load/concurrency; accessibility audit; cross-browser (Chrome/Edge only); the PyTorch `sentence-transformers` runtime (torch cannot be installed on this machine) and a vector-by-vector comparison of the NumPy model against it.
