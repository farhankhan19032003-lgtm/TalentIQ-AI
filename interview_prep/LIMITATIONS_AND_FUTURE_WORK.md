# Limitations and future work

## Limitations (all true of the code as shipped)
1. Synthetic, small (35 resumes, 6 JDs), author-labelled benchmark; dev set = test set; no real resumes.
2. Hybrid ≈ TF-IDF baseline on that benchmark (+0.012 NDCG@5, worse on one JD).
3. MiniLM path never executed here; calibration ranges for it (0.20–0.65) are guesses.
4. Hand-set weights/credits; no validation against hiring outcomes; score ≠ probability.
5. Ontology of 160 skills; unknown skills are invisible; bare `R`/`Go`/`C` only as list items; inflections missed; "Oracle" vendor false positive.
6. Generalist backend candidates tend to rank above specialists for ML/Java JDs (semantic overlap).
7. DOCX: no page numbers, text boxes ignored. PDF: no table/image understanding beyond text blocks and optional OCR.
8. English only. Date parsing covers common formats; year-only dates are approximated and flagged.
9. Single shared API key; in-process parsing; no AV; no TLS; files stored unencrypted.
10. Proxy bias (school, location, name-adjacent signals, gaps) is not measured.
11. Availability not collected; no calendar/ATS integration.
12. Docker/Render/Vercel and Linux/macOS untested; Postgres only on 16.4 and not under load (Windows and Postgres 16.4 were run). No CI.

## Future work (ordered by value)
1. Collect a small real, consented, double-annotated set; report inter-annotator agreement and a held-out test split.
2. Install and evaluate MiniLM (and a multilingual model); recalibrate; compare against TF-IDF with confidence intervals.
3. Learn/validate weights from recruiter feedback (override reasons are already captured).
4. Worker queue + sandboxed parsing + AV scanning; roles and per-tenant isolation; TLS and rate limiting.
5. Statistical fairness audit (selection-rate parity on real pools; proxy analysis).
6. Layout-aware PDF models for tables/columns; DOCX text boxes; page numbers via conversion.
7. CI with the backend/frontend suites and the browser script; Windows runner.
