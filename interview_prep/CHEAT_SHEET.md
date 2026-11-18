# TalentIQ AI - one-page cheat sheet

All numbers below were measured on the fictional `sample_data/` (Python Backend JD, 22 parsed resumes) on 2026-11-18. They are synthetic-data results, not real-world accuracy.

## How it works in 2 minutes
1. **JD in** (paste or PDF/DOCX upload) -> `jd_analyzer` extracts skills (must vs preferred, "X or Y" alternatives), min years, education level, responsibilities. The recruiter can edit it before saving.
2. **Resumes in** (PDF/DOCX, batch) -> security checks (magic bytes, size, macros), `document_parser` (PyMuPDF, pdfplumber fallback, Tesseract OCR for scans), `resume_extractor` (name/contact, sections, employment dates, education) and `skill_extractor` (160-skill ontology with synonyms).
3. **Match** -> five components, each 0-100, combined with weights:
   `Overall = 0.40 Technical + 0.25 Semantic + 0.20 Experience + 0.10 Education + 0.05 Project/Domain`
   - Technical: per-requirement credit (context 1.0, skills-list only 0.85, related skill 0.35, semantic-only 0.10-0.25, none 0), weighted must 1 / preferred 0.5 / title skill x2.
   - Semantic: all-MiniLM-L6-v2 cosine, JD narrative vs resume narrative and each responsibility vs its best resume line.
   - Experience: relevant years (merged calendar months, internships 50%) divided by the JD minimum, capped at 1.
4. **Output** -> ranking table (score, experience, matched skills), candidate page with per-component points, matched/related/missing skills, experience vs JD, "why / why not" with verbatim resume evidence. Missing evidence widens a score *range* (e.g. 64.7-69.7); it is not treated as a mismatch.
5. **Stack**: React + Vite + Tailwind, FastAPI, SQLAlchemy + Alembic, PostgreSQL (SQLite fallback), Docker compose (db + backend + nginx).

Worked example (Sana Qureshi, rank 1): Technical 48.26 (5.55 / 11.5 weighted credit), Semantic 61.66, Experience 100, Education 100, Project 0 (unverified) -> **64.72**. Full table: `docs/AI_MATCHING_ALGORITHM.md`.

## 10 questions you will probably get
1. **How is the percentage calculated?** The weighted sum above; weights are configurable and renormalised when the JD does not need a component. Each point on the candidate page traces to a component.
2. **Is it semantic or just keywords?** Both. Skills use an ontology (synonyms, related skills), and the 25% semantic component uses MiniLM embeddings. Measured: "REST services for payments" vs "HTTP APIs for checkout" gives 0.567 with MiniLM and 0.0 with TF-IDF; unrelated text gives 0.022.
3. **Why MiniLM and why a NumPy implementation?** Small (90 MB), CPU-only. torch could not be installed on my machine, so `minilm_numpy.py` runs the same published weights. It matches the published Sentence-Transformers example scores, but I have not compared it vector-by-vector with PyTorch.
4. **What if the model is missing / offline?** `EMBEDDING_BACKEND=auto` falls back to TF-IDF and the ranking page says which method ran. I ran both backends in the container.
5. **How do you handle experience?** Employment periods become calendar months, overlaps are merged, internships count 50%, and a role is "relevant" only if it mentions at least 2 JD skills (or 1 plus a title match). Years from the parser matched the answer key on 22/22 resumes.
6. **How accurate is parsing?** On the synthetic set: name 22/22, email 21/22 (OCR error on the scanned file), skill precision 1.00 and recall 0.99. Be upfront: the answer key is by construction and written by me, so this overstates real-world accuracy.
7. **How does ranking quality look?** 80.6% of (more relevant, less relevant) pairs ordered correctly on the Python Backend JD (125 / 155, after adding peer-skill credit; it was 75.5% before). I tuned on the same set, so this is not a held-out result.
8. **Why are scores low (best is 64.7, none at 70+)?** Honest answer: the formula is strict (missing must-haves score 0, project/domain is usually unverified), and the 70 threshold is a heuristic. A candidate with Flask/MySQL gets only 0.35 credit for Django/PostgreSQL. A calibrated threshold would need real labelled data.
9. **How do you handle bad files and security?** Magic-byte checks, size/page/zip-bomb limits, macros and active-content PDFs rejected, password-protected and corrupt files reported with a reason. In my 26-file batch: 22 parsed, 2 failed, 2 rejected.
10. **Fairness and limits?** Protected-attribute lines are removed before matching, blind mode hides names, a twin-resume test checks equal scores, and the system never auto-rejects (decision support only). Limits: synthetic data only, 160-skill ontology, no PDF sandbox, no user accounts, Render/Vercel configs untested.

## 3-minute demo script (record this)
Setup: `docker compose up -d`, open http://localhost:8080, then `python scripts/load_samples.py --jd python_backend_developer --no-bad-files` **or** upload by hand. Delete any real resume from the database first.

| Time | Do | Say |
|---|---|---|
| 0:00 | Jobs -> New job, paste `python_backend_developer.txt`, click analyze | "Module 1: it extracts must-have and preferred skills, 3+ years, Bachelor's, and treats FastAPI or Django as alternatives. I can edit before saving." Save. |
| 0:35 | Upload resumes: select the `sample_data/resumes` PDFs and DOCX (include `corrupted_resume.pdf`, `scanned_resume_image_only.pdf`) | "Module 2: a mixed batch of 20+ files. The corrupt and password-protected ones fail with a clear reason; the scanned PDF goes through OCR." |
| 1:15 | Ranking -> Run matching | "Module 3: MiniLM embeddings plus the skill ontology. Table is sorted by Match %, with experience and matched skills." Point at the range next to the score. |
| 1:45 | Open the top candidate (Sana Qureshi) | "Module 5: the points add up to the score (19.3 + 15.4 + 20 + 10 = 64.7). Flask counts as *related* for Django, so partial credit. Missing: Docker, pytest. Experience: 4.5 years against a 3-year minimum, role by role." |
| 2:30 | Open "Requirement evidence" and click a row | "Every claim shows the exact resume line." |
| 2:50 | Mention the limits | "Synthetic data only; this is decision support, not an auto-reject tool." |
