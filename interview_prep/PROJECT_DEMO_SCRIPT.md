# Project demo script (interview version)

Use `../docs/DEMO_SCRIPT.md` for the 5-minute walkthrough. For a 10-minute technical version add:

1. **Show the formula test:** `cd backend ; python -m pytest tests/test_matching_engine.py -q` (14 tests, ~1 s) → "scores are recomputed independently."
2. **Show evidence verification:** open `tests/test_api.py::test_all_evidence_is_verbatim_resume_text` → "every stored snippet exists in the resume text; that is how I guarantee no fabricated quotes."
3. **Show a failure case honestly:** AI/ML JD → hybrid NDCG 0.871 vs baseline 0.884. "I did not tune further, to avoid overfitting a 6-JD synthetic benchmark."
4. **Show the twin test:** two resumes differing only in name/gender/DOB/marital status lines score identically (Δ 0.0).
5. **Show rank sensitivity:** the ± marker in the ranking table; "51 % of ranks move under ±10 pp weight changes, so I show it."
6. **Show the limits slide:** synthetic data only; MiniLM unevaluated; not production-ready.

Questions to expect next: see `TECHNICAL_INTERVIEW_QA.md`.
