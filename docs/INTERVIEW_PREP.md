# Interview prep: TalentIQ AI

Every answer below points at code in this repository. Numbers come from the fictional `sample_data/` set (see [ALGORITHM.md](ALGORITHM.md)); say so if asked.

## The app in two minutes

TalentIQ ranks resumes against a job description and explains every score.

1. **Job in.** A recruiter pastes a JD or uploads a PDF/DOCX/TXT. `jd_analyzer.py` extracts must-have vs preferred skills, "X or Y" alternatives, minimum years and degree level. All of it is editable before saving.
2. **Resumes in.** A batch of PDF/DOCX files goes through upload security (magic bytes, size, macros), `document_parser.py` (PyMuPDF, OCR for scans, DOCX tables and text boxes) and `resume_extractor.py` (name, contact, dated roles, education, projects, skills, each with its page and source line). One bad file never fails the batch: each file ends as `parsed`, `failed`, `rejected` or `duplicate`.
3. **Match.** `matching_pipeline.py` scores five components from 0 to 100: Technical skills 40 %, Semantic relevance 25 %, Experience 20 %, Education 10 %, Projects/domain 5 %. Skills use an ontology with synonyms and related-skill partial credit; semantic relevance uses MiniLM sentence embeddings.
4. **Show.** The ranking table lists Candidate, Experience, Match % and Matched skills (exact, related and missing look different). The candidate page opens with a one-sentence verdict, then the extracted profile, score breakdown, experience-vs-JD comparison, requirement-by-requirement evidence and "why this score".
5. **Safe by design.** It is decision support: nothing is auto-rejected, every recruiter action is audit-logged, and the machine score is never rewritten by an override.

Stack: React + TypeScript, FastAPI, PostgreSQL (SQLAlchemy + Alembic), MiniLM (NumPy runtime included), Docker Compose.

## The 12 questions you will most likely get

**1. How is the percentage calculated?**
`Overall = 0.40·Technical + 0.25·Semantic + 0.20·Experience + 0.10·Education + 0.05·Project`, all weights in `core/config.py` and editable in the UI. Components the JD does not need are dropped and the rest renormalised; a Projects section that is missing is left out instead of counted as zero. Worked example in `docs/ALGORITHM.md`: Sana Qureshi gets Technical 52.86 (5.55 weighted credit of 10.5), Semantic 50.45, Experience 100, Education 100 → **67.11**, with a range 63.8-68.8 because one component is unverified.

**2. How does it decide a skill is matched?**
The ontology maps aliases to one name. Credit per requirement: 1.0 if the skill is used in experience text, 0.85 if only listed, 0.35 for a related skill (Flask for Django, MySQL for PostgreSQL), 0.10-0.25 if a resume line is semantically close but the skill is never named, else 0. "X or Y" takes the best alternative. A related skill is never displayed as an exact match.

**3. Why MiniLM?**
`all-MiniLM-L6-v2` is small (~90 MB), CPU-only and good at sentence similarity, which is what resume-vs-responsibility comparison is. It runs offline, so there is no API cost or data leaving the machine. Trade-off: 256-token limit and it is general-purpose, not tuned for resumes. I included a pure-NumPy runtime (`minilm_numpy.py`, same weights) because torch could not be installed on my machine; it matches the published Sentence-Transformers example scores but I did not compare it vector-by-vector with PyTorch.

**4. What if embeddings are unavailable?**
`EMBEDDING_BACKEND=auto` uses MiniLM if the model files exist, otherwise falls back to TF-IDF fitted only on the JD and the ontology (so a score never depends on other candidates). The run stores `similarity_method` and the fallback reason, and the ranking page shows it. Calibration ranges are separate per method. Proof it matters: for "REST services for a payments platform" vs "HTTP APIs for the checkout system" TF-IDF gives 0.00 and MiniLM gives 0.57.

**5. How do you handle bad PDFs?**
Layered, and always per file. `security.py` checks magic bytes, size, page count and active content. `document_parser.py`: password-protected → `failed` with a clear message; malformed → pdfplumber fallback, else `failed: corrupt`; image-only → OCR if Tesseract exists and the result is flagged **needs review**, otherwise it is *not scored* and shown as "Needs review: no extractable text". In my 18-file demo batch: 16 parsed (one flagged for review), 2 failed with reasons, the rest of the batch unaffected.

**6. How would this scale?**
Honest answer: today parsing and matching run in the API process, which is fine for hundreds of resumes (50 PDFs upload in ~1 s, rank in ~7 s on a laptop) but not for thousands. Next steps: move parsing to a worker queue (Celery/RQ), store embeddings in Postgres with pgvector instead of recomputing per run, batch-encode, add DB indexes on candidate/job, run several API replicas behind nginx, and cache the ontology and model per process (already lazy singletons). I have not load-tested it.

**7. Bias and fairness?**
Protected-attribute lines (age, gender, religion, ...) are scrubbed before matching; blind mode hides names and contact details in the UI and exports; a twin-resume test (same resume, different names) shows a score difference of 0.0 on 6 JDs; the audit log stores no personal text; the system never auto-rejects. Limits I state openly: twins are synthetic, proxy features (school, location) are untested, and the benchmark is not real hiring data.

**8. Why did a fresher show "—" and 0.0 years?**
Because the resume had no Experience section (summary, skills, projects, education only), so there is genuinely no dated employment. That was a presentation gap, now fixed: the table shows "No dated roles", the role falls back to the resume's own headline marked "(profile)", "6+ years of experience" written in text is kept as a *claimed* figure credited at 60 %, and experience is labelled unverified rather than zero. Layouts covered by `tests/test_resume_layouts.py`: 14, including `since 2021`, `2019-23`, `03.2020 - 05.2021`, three-line headers, DOCX tables and text boxes.

**9. How do you compute experience and relevance?**
Employment periods become sets of calendar months, so overlaps are never double counted; part-time and internship months count 50 %. A role is relevant if it demonstrates at least 25 % of the job's weighted requirements ("fit"); the old rule (any 2 shared skills) made Git + Docker count for every job. Score = min(1, relevant years / required years), with a preferred-years blend if the JD gives a range.

**10. How accurate is it, and how do you know?**
Against the answer key for 34 parsable synthetic resumes: name 34/34, email 34/34, experience years 34/34, education level 34/34, skill precision 1.00 and recall 0.99. Ranking: 89.2 % of (more relevant, less relevant) pairs are ordered correctly over 204 graded JD/resume pairs; strong resumes (grade 3) have median 84.9, unrelated ones median 16.4 (`python eval/calibration_report.py`). The caveat I would say first: the answer key was written by me from the same templates, and the calibration was tuned on the same pairs, so this is a consistency check, not a real-world accuracy claim.

**11. How did you calibrate the scores without inflating them?**
I measured, not guessed. A demo showed best = 64.7, which had two causes: the batch had no strong candidate for that JD, and three real calibration flaws (generic tools made every role "relevant", the responsibility-level cosine used the wrong range, a missing Projects section counted as 0). Each fix has a reason and a test (`test_scoring_calibration.py`: strong ≥ 80, medium 50-79, weak < 40, under TF-IDF and MiniLM). Credits and weights were not changed; poor fits actually dropped (grade-1 median 48 → 30). A later live check found the semantic score saturating: three strong candidates with cosines 0.75, 0.77 and 0.87 all got 100. I moved the MiniLM upper anchors from 0.75/0.45 to 0.90/0.55 (above the highest cosine measured), so 0 of 204 pairs now hit 100 and the strong median is 84.9 instead of 89.4. Trade-off I would state: every score drops a few points; the strong band still clears 80.

**12. What would you do next / what are the limitations?**
Get a small set of real, consented resumes with recruiter labels and re-fit `CALIBRATION` and the fit threshold; add a re-parse action so old candidates pick up parser upgrades; grow the 160-skill ontology; sandbox PDF parsing; add user accounts. Render/Vercel deploy files are untested; Docker Compose is verified.

## Questions about specific choices (short answers)
- *Why an ontology instead of only embeddings for skills?* Exact and related skills must be explainable and editable by a recruiter; embeddings are used as weak, labelled evidence (max 0.25 credit).
- *Why show a score range?* Missing evidence (no projects, no dates) is not a mismatch; the range shows what the score could be.
- *Why PostgreSQL?* The assignment prefers it; Alembic migrations are tested on it. SQLite remains the zero-setup fallback.
- *What is verified in the UI?* Every evidence snippet is a verbatim substring of the resume; unverifiable snippets are discarded, never invented.
