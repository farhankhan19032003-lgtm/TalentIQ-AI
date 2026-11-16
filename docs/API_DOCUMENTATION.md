# API reference

Base URL `http://localhost:8000/api`. Interactive docs: `/api/docs` (Swagger) and `/api/openapi.json` (generated from the code, so always current).
If `API_KEY` is set, send header `X-API-Key: <key>` on every call except `/health` and `/auth/login`.
Errors: `{"error": {"code": "...", "message": "...", "details": ...}}` with HTTP 4xx/5xx. Unexpected failures return `internal_error` without internals.

| Method & path | Purpose |
|---|---|
| GET `/health` | status, DB, embedding backend, OCR, whether auth is required |
| POST `/auth/login` | `{api_key}` → 200 or 401 |
| GET/POST `/jobs` · GET/PUT/DELETE `/jobs/{id}` | CRUD. POST body: `title`, `description`, optional `required_skills`, `optional_skills`, `min_experience_years`. PUT may include edited `requirements` (importance `must`/`preferred`/`ignored`). |
| POST `/jobs/analyze` | Preview extracted requirements without saving |
| POST `/jobs/extract-text` | Upload a JD (`.pdf/.docx/.txt`) → text + analysis |
| POST `/resumes/upload` | multipart `files`; returns per-file status (`parsed`, `failed`, `duplicate`, `rejected`) + summary + `batch_id` |
| GET `/resumes` (`page`, `page_size`, `status`) · GET `/resumes/stats` · GET `/resumes/batches/{id}` | listing, stats, batch progress |
| GET/DELETE `/resumes/{id}` · POST `/resumes/{id}/retry` | inspect, delete, retry a failed parse |
| POST `/matching/run/{job_id}` | body `{weights?}` (must sum to 1) → new run |
| GET `/matching/runs/{job_id}` | run history |
| GET `/matching/results/{job_id}` | ranked results. Query: `page`, `page_size≤100`, `q`, `min_score`, `max_score`, `min_exp`, `max_exp`, `skills=a,b`, `review_status`, `min_confidence`, `needs_review`, `sort` (rank, name, overall, experience, coverage, confidence, completeness, role, status), `order`, `blind` |
| GET `/matching/candidate/{id}?job_id=` | full detail: breakdown, requirement evidence, experience, explanation, overrides, parsed profile (`blind` supported) |
| GET `/matching/compare?job_id=&ids=1,2,…` | 2–5 candidates |
| POST `/matching/whatif/{job_id}` | simulate `weights`, `min_years`, `add_requirements`, `requirement_changes`; **never persists** |
| POST `/matching/results/{result_id}/override` | `{new_score, reason}` (reason required) |
| POST `/candidates/{id}/notes` · PATCH `/candidates/{id}/status` · DELETE `/candidates/{id}` | notes, review status (`new, reviewed, shortlisted, interview, on_hold, not_progressing`), full data deletion |
| GET `/analytics/{job_id}` · GET `/analytics/talent-pool/overview?job_id=` | charts data |
| GET `/reports/{job_id}/csv\|excel\|pdf` (`blind=true` for CSV) · GET `/reports/{job_id}/candidate/{cid}/pdf` | exports |
| GET/POST `/searches` · DELETE `/searches/{id}` | saved filter sets |
| GET `/ontology?category=` · POST `/ontology/reload` | skill ontology |
| GET `/settings` · GET `/audit` · POST `/admin/retention/run?days=` | configuration, PII-free audit trail, retention purge |
| POST `/demo/seed-jobs` · POST `/demo/upload-samples` | load JD templates / the synthetic **test** resumes from `sample_data/` |

### Example (PowerShell)
```powershell
$job = Invoke-RestMethod -Method Post http://localhost:8000/api/jobs -ContentType application/json `
  -Body (@{title="Data Analyst"; description="Requirements:`n- SQL and Excel`n- 1+ years of experience"} | ConvertTo-Json)
curl.exe -F "files=@sample_data/resumes/anika_menon.pdf" http://localhost:8000/api/resumes/upload
Invoke-RestMethod -Method Post "http://localhost:8000/api/matching/run/$($job.id)" -ContentType application/json -Body "{}"
Invoke-RestMethod "http://localhost:8000/api/matching/results/$($job.id)?page_size=5"
```
