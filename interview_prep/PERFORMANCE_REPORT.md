# Performance report (measured, TF-IDF backend, Linux sandbox)

Only numbers that were actually measured are listed.

| Measurement | Result | Source |
|---|---|---|
| Batch upload + parse, 41 files | 1.24 s (HTTP, test client) | eval `batch_upload_seconds` |
| Mean parse time per resume | 29.1 ms | eval |
| Max parse time (one file) | 493 ms (the OCR file) | eval |
| Matching, 35 candidates × 1 JD | mean 0.43 s | eval |
| Peak memory, whole benchmark (parse 41 files + 6 JDs, in-process) | ≈ 307 MB RSS | `resource.getrusage` |
| Backend test suite | ≈ 22 s for 143 tests | pytest |
| Frontend production bundle | 690 kB JS (204 kB gzip), 20 kB CSS | `vite build` |

## Not measured
PyTorch MiniLM memory (torch adds hundreds of MB; unmeasured); concurrent users; large corpora (> 100 resumes); page-load times in the browser. Measured once on Windows: 50 resumes upload in about 1 s and rank in 4-7 s with the NumPy MiniLM (SQLite and PostgreSQL 16.4), a single run each. Do not extrapolate the numbers above to those cases.

## Why it is fast enough here
Pure-Python regex extraction, a tiny TF-IDF fitted on one JD, embedding cache keyed by SHA-1 of text (MiniLM path), and no network calls.
