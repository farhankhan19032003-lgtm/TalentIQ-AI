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

**2. Why these weights (40 / 25 / 20 / 10 / 5)?**
They are hand-set heuristics, not learned from hiring outcomes, and I say so. The reasoning: skills evidence is the most checkable signal (a skill is either in the resume text or not), so it gets the most weight; semantic similarity is useful but a general-purpose model, so it is second; experience is 20 % because years only matter relative to what the job asks; education is 10 % because most JDs only need a degree level; projects are 5 % because many resumes have none. Because the guess might be wrong, it is visible and adjustable: weights are editable in the UI (must total 100 %), the what-if page re-ranks live, and every ranking row shows a "±" when its rank moves under ±10-point weight changes (`ranking_engine.sensitivity`). If a component is not applicable the others are rescaled, and the candidate page prints that in a note.

**3. How does it decide a skill is matched?**
The ontology maps aliases to one name. Credit per requirement: 1.0 if the skill is used in experience text, 0.85 if only listed, 0.35 for a related skill (Flask for Django, MySQL for PostgreSQL), 0.10-0.25 if a resume line is semantically close but the skill is never named, else 0. "X or Y" takes the best alternative. A related skill is never displayed as an exact match.

**4. Why MiniLM?**
`all-MiniLM-L6-v2` is small (~90 MB), CPU-only and good at sentence similarity, which is what resume-vs-responsibility comparison is. It runs offline, so there is no API cost or data leaving the machine. Trade-off: 256-token limit and it is general-purpose, not tuned for resumes. I included a pure-NumPy runtime (`minilm_numpy.py`, same weights) because torch could not be installed on my machine; it matches the published Sentence-Transformers example scores but I did not compare it vector-by-vector with PyTorch.

**5. What happens offline, or when the model is missing?**
`EMBEDDING_BACKEND=auto` uses MiniLM if the model files exist, otherwise falls back to TF-IDF fitted only on the JD and the ontology (so a score never depends on other candidates). The run stores `similarity_method` and the fallback reason, and the ranking page shows it. Calibration ranges are separate per method. Proof it matters: for "REST services for a payments platform" vs "HTTP APIs for the checkout system" TF-IDF gives 0.00 and MiniLM gives 0.57.

**6. How are bad PDFs handled?**
Layered, and always per file. `security.py` checks magic bytes, size, page count and active content. `document_parser.py`: password-protected → `failed` with a clear message; malformed → pdfplumber fallback, else `failed: corrupt`; image-only → OCR if Tesseract exists and the result is flagged **needs review**, otherwise it is *not scored* and shown as "Needs review: no extractable text". In my 19-file demo batch: 16 parsed (two flagged for review), 2 failed with reasons, 1 byte-identical duplicate skipped, the rest of the batch unaffected.

**7. How are duplicates detected?**
Two levels, both in `pipeline.ingest_resume`. (1) Byte-identical files: the SHA-256 of the upload is compared with `Resume.file_hash`, which has a unique constraint (`uq_resume_hash`), so the same file is never stored or ranked twice; the batch result shows it as `duplicate`, the skip is written to the audit log, and the ranking page lists it ("19 files received → 16 parsed · 2 failed · 1 identical duplicate skipped"; `GET /api/resumes/accounting`). (2) Same person, different file: if a new resume has the same e-mail as an existing candidate it is still processed, but the upload row warns "possible duplicate person". What it does **not** catch: a re-exported or edited copy without an e-mail, or the same person with two e-mails. That is a deliberate trade-off: merging people automatically could hide a real candidate, so a human decides.

**8. How would this scale?**
Honest answer: today parsing and matching run in the API process, which is fine for hundreds of resumes (50 PDFs upload in ~1 s, rank in ~7 s on a laptop) but not for thousands. Next steps: move parsing to a worker queue (Celery/RQ), store embeddings in Postgres with pgvector instead of recomputing per run, batch-encode, add DB indexes on candidate/job, run several API replicas behind nginx, and cache the ontology and model per process (already lazy singletons). I have not load-tested it.

**9. Bias and fairness?**
Protected-attribute lines (age, gender, religion, ...) are scrubbed before matching; blind mode hides names and contact details in the UI and exports; a twin-resume test (same resume, different names and protected-attribute lines) differs by 0.0 points with TF-IDF and at most 0.61 points with MiniLM over 6 JDs (the embedding model is the only place a name can matter); the audit log stores no personal text; the system never auto-rejects. Limits I state openly: twins are synthetic, proxy features (school, location) are untested, and the benchmark is not real hiring data.

**10. Why no auto-reject?**
Three reasons. The score is a similarity-and-evidence signal, not a probability of job performance; the weights are unvalidated heuristics; and missing evidence (a scanned resume, no projects section, no dates) is not a mismatch. So the system ranks and explains, and every consequential action is a human one: stage changes and overrides are recruiter actions with an audit-log entry, an override needs a written reason and never rewrites the machine score, parse problems show as "needs review", and the ranking page carries a decision-support disclaimer. A bias audit would also be much harder if the software silently removed people.

**11. How accurate is it, and how did you calibrate it?**
Against the answer key for 34 parsable synthetic resumes: name 34/34, email 34/34, experience years 34/34, education level 34/34, skill precision 1.00 and recall 0.99. Ranking: 89.2 % of (more relevant, less relevant) pairs are ordered correctly over 204 graded JD/resume pairs; strong resumes (grade 3) have median 84.9, unrelated ones median 16.4 (`python eval/calibration_report.py`). The caveat I would say first: the answer key was written by me from the same templates, and the calibration was tuned on the same pairs, so this is a consistency check, not a real-world accuracy claim.
I measured, not guessed. A demo showed best = 64.7, which had two causes: the batch had no strong candidate for that JD, and three real calibration flaws (generic tools made every role "relevant", the responsibility-level cosine used the wrong range, a missing Projects section counted as 0). Each fix has a reason and a test (`test_scoring_calibration.py`: strong ≥ 80, medium 50-79, weak < 40, under TF-IDF and MiniLM). Credits and weights were not changed; poor fits actually dropped (grade-1 median 48 → 30). A later live check found the semantic score saturating: three strong candidates with cosines 0.75, 0.77 and 0.87 all got 100. I moved the MiniLM upper anchors from 0.75/0.45 to 0.90/0.55 (above the highest cosine measured), so 0 of 204 pairs now hit 100 and the strong median is 84.9 instead of 89.4. Trade-off I would state: every score drops a few points; the strong band still clears 80.

**12. What would you improve next?**
Get a small set of real, consented resumes with recruiter labels and re-fit `CALIBRATION` and the fit threshold; add a re-parse action so old candidates pick up parser upgrades; grow the 160-skill ontology; sandbox PDF parsing; add user accounts. Render/Vercel deploy files are untested; Docker Compose is verified.

## Questions about specific choices (short answers)
- *Why did a fresher show "—" and 0.0 years?* The resume had no Experience section, so there was no dated employment. The table now shows "No dated roles", the role falls back to the resume's own headline marked "(profile)", "6+ years" written in text is a *claimed* figure credited at 60 %, and a role that cannot be found at all is shown as "Role not found" with a needs-review flag (`tests/test_resume_layouts.py`, 18 layouts).
- *How are experience and relevance computed?* Employment periods become sets of calendar months, so overlaps are never double counted; part-time and internship months count 50 %. A role is relevant if it demonstrates at least 25 % of the job's weighted requirements ("fit"); the old rule (any 2 shared skills) made Git + Docker count for every job. Score = min(1, relevant years / required years), with a preferred-years blend if the JD gives a range.
- *Why an ontology instead of only embeddings for skills?* Exact and related skills must be explainable and editable by a recruiter; embeddings are used as weak, labelled evidence (max 0.25 credit).
- *Why show a score range?* Missing evidence (no projects, no dates) is not a mismatch; the range shows what the score could be.
- *Why PostgreSQL?* The assignment prefers it; Alembic migrations are tested on it. SQLite remains the zero-setup fallback.
- *What is verified in the UI?* Every evidence snippet is a verbatim substring of the resume; unverifiable snippets are discarded, never invented.
