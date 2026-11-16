# Feature checklist

Legend: ✅ implemented and tested here · 🟡 implemented, partially verified · ⬜ not implemented

## Core (modules A–N)
- ✅ A JD intelligence (requirements, must/preferred, alternatives, years, education, editable)
- ✅ B Resume parsing PDF/DOCX, two-column, OCR (Tesseract optional; OCR path tested on a scanned sample)
- ✅ C Hybrid matching with the 40/25/20/10/5 formula, configurable weights
- ✅ D Skill gap (matched / related / missing, requirement coverage)
- ✅ E Experience intelligence (month-union, part-time/internship, uncertain dates)
- ✅ F Ranking dashboard (filters, sort, pagination, compare ≤ 5, exports)
- ✅ G Candidate profile with clickable evidence
- ✅ H Explainable output (points table, why / why not, missing info)
- ✅ I Analytics + talent pool
- ✅ J Fairness / privacy / security controls (see SECURITY.md)
- ✅ K UI (React/Tailwind/Recharts)
- ✅ L DB + API (SQLAlchemy, Alembic, 37 paths)
- ✅ M Synthetic sample data (35 profiles + 6 failure files, 6 JDs)
- ✅ N Tests + docs

## Upgrade spec
- ✅ Evidence engine with verbatim verification · ✅ Skill ontology (160) · ✅ What-if (non-persisting) · ✅ Blind screening · ✅ Overrides with reasons · ✅ Twin fairness test · ✅ Evaluation framework + baselines · ✅ Performance measured (parse ≈ 29 ms, match ≈ 0.43 s per JD, 35 candidates)
- ✅ Notes, status, saved searches, JD templates, candidate and batch reports
- ✅ Semantic engine: all-MiniLM-L6-v2 sentence embeddings, executed and evaluated (pure-NumPy runtime; matches the published example scores; mean NDCG@5 0.945 vs 0.943 TF-IDF, a tie on this small synthetic set). 🟡 The PyTorch `sentence-transformers` runtime itself has not been run here
- 🟡 Docker / compose / Render / Vercel files: untested
- ✅ Postgres 16.4: 237 backend tests, Alembic round trip and the 50-resume flow pass (Windows; see docs/TESTING.md). Other versions and load untested.
- ⬜ Candidate availability collection (analytics shows that it is not collected)
- ⬜ Multi-user accounts, roles, per-recruiter isolation
- ⬜ Parser sandboxing / malware scanning
- ⬜ Learned weights / validation on real hiring outcomes
- 🟡 Browser E2E script shipped as a manual tool (`scripts/e2e_browser_check.py`), not wired into CI
- ⬜ PowerShell/Windows run verified
