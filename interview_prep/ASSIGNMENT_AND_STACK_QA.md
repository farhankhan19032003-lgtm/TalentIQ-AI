# Interview Q&A: assignment, stack, Docker, and curveballs

Companion to `TECHNICAL_INTERVIEW_QA.md` (58 deeper questions on parsing, scoring, evaluation, fairness). This file covers what the assignment email says will be asked: **explain and demonstrate the complete application**, **explain the matching algorithm and how the percentage is calculated**. Answers are written to be spoken in simple English. Numbers come from real runs of this project.

Golden rule: never claim more than you tested. When you do not know, say "I did not measure that" and say what you would do. The README already says this honestly, so staying consistent is a strength.

---

## A. The opening (they will start here)

**A1. Give me a two-minute overview of your project.**
TalentIQ AI takes a job description and a batch of resumes and returns a ranked shortlist where every score is explained. A recruiter pastes or uploads a JD, the system extracts the requirements, then they upload PDF or DOCX resumes in a batch. Each resume is parsed into skills, experience, education and projects. The matching engine scores every candidate from 0 to 100 with a hybrid formula, and the candidate page shows the points per component, matched and missing skills, an experience comparison and the exact resume sentence behind each match. It is decision support: it never rejects anyone. The stack is React, FastAPI, PostgreSQL and MiniLM sentence embeddings, and the whole thing also runs with `docker compose up`.

**A2. Which of the five assignment modules did you build and how?**
1. JD input: paste or upload (PDF, DOCX, TXT), requirements extracted with must-have versus preferred, alternatives, years and education.
2. Resume upload: batches of PDF and DOCX; I tested 20 in one batch plus corrupted, password-protected, fake-extension and duplicate files.
3. Matching: hybrid score with semantic similarity, matched and missing skills, relevant experience.
4. Ranking dashboard: table with candidate, experience, match % and matched skills, plus filters, sorting, compare and export.
5. Candidate analysis: extracted details, score breakdown, matched and missing skills, experience comparison and reasons.

**A3. What did you build beyond the assignment, and why?**
Blind screening, a what-if simulator, manual override with a mandatory reason, a pipeline board, a talent matrix and interview notes. I added them because a ranking tool is only trustworthy if a recruiter can challenge it. They are extras: the five modules work without them, and none of them changes the machine score.

---

## B. The algorithm and the percentage (the most likely deep dive)

**B1. How exactly is the match percentage calculated?**
```
Overall = 0.40 * Technical + 0.25 * Semantic + 0.20 * Experience + 0.10 * Education + 0.05 * Project/Domain
```
Each component is scored 0 to 100, multiplied by its weight, and the points are added. A component the job does not ask for is dropped and the other weights are renormalised. Weights are editable but must total 100 %.

**B2. Walk me through a real candidate.**
From my run, Vikram Joshi against the Python Backend JD:

| Component | Score | Weight | Points |
|---|---|---|---|
| Technical skills | 81.3 | 40 % | 32.52 |
| Semantic relevance | 74.0 | 25 % | 18.50 |
| Relevant experience | 100 | 20 % | 20.00 |
| Education | 100 | 10 % | 10.00 |
| Project/domain | 0 | 5 % | 0.00 |
| **Total** | | | **81.03** |

He matched 9 of 13 skills with direct resume evidence. AWS, CI/CD and Kubernetes are missing, and the project score is 0 because no projects section could be extracted. That is "missing evidence", and the UI shows a score range (81.0 to 86.0) instead of treating it as a mismatch.

**B3. How do you handle semantic similarity and not just keywords?**
I embed the JD narrative and the candidate's summary and experience text with all-MiniLM-L6-v2 and take the cosine similarity. Then a linear calibration maps cosine to 0-100 (0.20 maps to 0, 0.65 maps to 100 for MiniLM). So "built REST services" and "API development" score as similar even with no shared word. On paraphrases with no shared words, TF-IDF scores 0.00 and MiniLM scores 0.31 to 0.57, and my test suite checks that.

**B4. Why not just use only embeddings? Or only keywords?**
Embeddings alone blur important details: "Java" and "JavaScript" can look close, and a missing must-have skill is hidden. Keywords alone miss synonyms and meaning. The hybrid keeps a precise, explainable skill score (40 %) and adds meaning (25 %). Each match also has a type with different credit: exact 1.0, listed-only 0.85, related skill 0.35, semantic 0.10 to 0.25, none 0.

**B5. How do you decide the weights? Are they learned?**
No, they are hand-set from how recruiters usually read a resume: skills first, then meaning, then experience. I have not fitted them to hiring outcomes and I say so. The weights are configurable and the what-if page shows how ranking changes when they move. With real feedback I would learn them from recruiter overrides, which the system already records with reasons.

**B6. How is experience calculated?**
Each employment period becomes a set of calendar months. Overlapping jobs are counted once, internships count at 50 %, and "Present" is resolved to the analysis date. Only roles relevant to the JD count toward relevant years. I fixed one real bug here: "Machine Learning Engineer" was not treated as relevant to an "AI/ML Engineer" job until I normalised title abbreviations, and I added a regression test.

**B7. How do you stop the system from inventing evidence?**
Every evidence snippet must be a verbatim substring of the resume text. A snippet that cannot be verified is discarded, never shown. If there is no evidence, the requirement is shown as "No evidence", not guessed.

**B8. Does a higher score mean the candidate will perform better?**
No. It is a decision-support signal comparing resume text with job requirements. It is not a probability of being hired or of job performance, and the app says that at the bottom of the candidate page.

---

## C. Evaluation and honesty

**C1. How accurate is it?**
On my synthetic benchmark (35 resumes, 6 JDs): skill micro-F1 0.993, experience accuracy 1.00, and NDCG@5 0.945 with MiniLM versus 0.943 with TF-IDF and 0.932 for a plain baseline. On a separate 50-resume pack all 10 intended strong matches ranked in the top 10, experience years were within one year for 39 of 50, and skill recall was 0.94 with precision 0.73. The data is synthetic and the labels are mine, so these numbers do not predict real-world accuracy.

**C2. Your MiniLM and TF-IDF numbers are almost equal. Why use MiniLM?**
Correct, it is a tie on this set because my synthetic resumes reuse the JD's own words, so keyword methods already do well. The real benefit shows on paraphrases, where TF-IDF gives 0.00 and MiniLM ranks them clearly above unrelated text. I report the tie honestly instead of claiming an improvement.

**C3. How did you test the project?**
237 backend tests (also run on PostgreSQL), 31 frontend tests, a benchmark script, and end-to-end browser tests with headless Chrome: upload a JD, upload 20 resumes, handle bad files, run matching, open a candidate, toggle blind mode. The browser test found a real bug, that a newly created job was not set as active, which I fixed.

---

## D. Stack and design choices

**D1. Why React, FastAPI and PostgreSQL?**
They are what the assignment prefers and they fit the job. FastAPI gives typed request validation and automatic API docs. React with Vite gives a fast single-page UI. PostgreSQL gives proper concurrency and JSON columns, and SQLAlchemy plus Alembic give versioned migrations.

**D2. Why not use an LLM?**
Cost, privacy and explainability. This runs offline on a CPU laptop, sends no resume to a third party, and gives deterministic scores, so the same input gives the same output and every number can be traced. An LLM could be added later for summaries, but the score itself should stay auditable.

**D3. You said sentence-transformers, but you wrote your own NumPy version. Why?**
PyTorch cannot be installed on my machine because Windows Application Control blocks the compiled wheels. I implemented the same model in pure NumPy with the same weights, tokenizer and pooling. It reproduces the published example scores to four decimals. The honest limitation: I did not compare it vector by vector with PyTorch. If sentence-transformers is installed, the app uses it automatically.

**D4. How does the app handle many resumes or concurrency?**
It was tested with batches of 20 to 50 resumes (50 ranked in about 6.6 seconds). Parsing runs in the request process, so for large volumes or many users I would add a worker queue, sandboxed parsing and rate limiting. I have not load-tested it.

**D5. How do you secure uploads?**
Magic-byte checks so a fake `.pdf` is rejected, size, page and zip-bomb limits, rejection of PDFs with active content and DOCX with macros, random storage names, prompt-injection text flagged, an optional API key, and CSV formula-injection protection in exports.

---

## E. Docker and DevOps

**E1. How do you run the project?**
Locally with `.\start.ps1` (starts PostgreSQL, the backend and the frontend), or fully containerised with `docker compose up --build` and then open http://localhost:8080.

**E2. What is in your Docker setup?**
Three containers. PostgreSQL 16 with a volume and a health check. The backend, a Python 3.13 image with Tesseract OCR, the MiniLM model baked in at build time (hash-verified), Alembic migrations on start, a non-root user and a health check. And the React build served by nginx, which proxies `/api` to the backend. The frontend waits until the backend is healthy.

**E3. Did the Docker build teach you anything?**
Yes. The first build failed because I had pinned numpy 2.5, which needs Python 3.12 or newer, while my Dockerfile used Python 3.11. Building in a clean container exposed a dependency problem that my own machine hid. I moved the image to Python 3.13 and updated the README. I also removed the sample data from the image so it contains no demo data.

**E4. Why pin dependency versions?**
A fresh install pulled newer numpy and SQLAlchemy than the ones I tested, and a clean clone failed one test. Pinning gives a reproducible install. The trade-off is that I must update the pins deliberately.

**E5. Is it deployed anywhere?**
No. It runs locally and in Docker Compose. The Render and Vercel config files exist but are untested.

---

## F. Problems I hit and fixed (use these as "tell me about a challenge")

1. **PDFs corrupted after a Windows clone.** Git's `autocrlf` converted small PDFs to CRLF and broke them. I found it by cloning the GitHub repo fresh and running the tests, then added a `.gitattributes` marking PDFs and DOCX as binary.
2. **A test that silently depended on Tesseract.** It failed on machines without OCR. I made the expected count depend on whether OCR is available.
3. **psycopg blocked by Application Control.** I used the pure-Python driver with PostgreSQL's own `libpq.dll`, and `start.ps1` sets that up automatically.
4. **Active job not selected.** A browser test showed Ranking and Candidate pages empty for a new user. Fixed by pre-selecting the latest job and making a newly created job active.
5. **Title abbreviation bug** ("ML Engineer" not relevant to "AI/ML Engineer"), fixed with normalisation and a regression test.

---

## G. Curveball questions

**G1. If I give you a real resume, will it work?**
It should parse most standard PDFs and DOCX, but I have only validated on synthetic resumes. Unusual layouts, images inside tables and DOCX text boxes are known weak spots. I would run it on a small consented set and measure before trusting it.

**G2. Can the system be biased?**
It does not use protected attributes, scrubs protected-attribute lines before matching, offers blind screening, and passed a twin-resume test with zero difference. But proxies such as school, location or employment gaps are not measured, so I cannot call it fair, only that I took the obvious steps.

**G3. What happens if two candidates have the same score?**
Ties are broken deterministically, so the same input always gives the same ranking. There is also a rank-sensitivity analysis showing how stable a rank is when weights change.

**G4. A skill is not in your ontology. What then?**
It is invisible to the skill matcher, because the ontology has 160 hand-edited skills. The semantic component can still pick up related meaning. The fix is to grow the ontology or add data-driven skill extraction.

**G5. What would you improve first with one more week?**
A small real, consented, double-annotated dataset for a held-out evaluation, then comparing MiniLM, TF-IDF and a multilingual model with confidence intervals, then a worker queue with sandboxed parsing and proper authentication.

**G6. Which part are you least sure about?**
The weights and the cosine calibration range, because they are hand-set and not learned from real hiring data. I can show with the what-if page how sensitive the ranking is to them.

**G7. You used AI coding assistants. How do I know you understand the code?**
Ask me to open any part. The weights live in `core/config.py` (`DEFAULT_WEIGHTS`), the weighted sum is in `services/matching_pipeline.py`, and the per-component logic is in separate modules: `skill_extractor.py`, `semantic_matcher.py` (with `minilm_numpy.py`), `experience_analyzer.py`, `jd_analyzer.py`, `resume_extractor.py`, `document_parser.py` and `explanation_engine.py`. I can walk from an upload, through parsing and extraction, to the match result and the evidence object shown in the UI, and I can explain every number on the candidate page.

---

## H. Live demo checklist (they may ask you to run it)

1. `.\start.ps1`, open http://localhost:5173 (empty app).
2. Jobs, New job, upload the DOCX JD, Analyse requirements, Save.
3. Upload resumes: 20 good files, then the 4 error files.
4. Ranking, Run matching; explain the table columns and page 2.
5. Click the top candidate: points table, why this score, missing skills, evidence row, experience section.
6. Toggle blind screening; try what-if with minimum years 12; add an override with a reason.
7. Optional: `docker compose up -d` and show http://localhost:8080 and `docker compose ps`.

## Questions you can ask them
- What would a good candidate-ranking tool need to do for your recruiters beyond a score?
- How do you handle bias and consent in your current screening process?
- What does the team use for NLP today, and how do you evaluate it?

## Hinglish tips
- Pehle simple jawab do, phir agar poochein to detail mein jao.
- Numbers yaad rakho: 40/25/20/10/5 weights, Vikram 81.03, 237 + 31 tests, 20 resumes, MiniLM 0.945 vs 0.943.
- "Mujhe nahi pata" bolna theek hai, par saath mein bolo "main ye measure karta aur ye karta".
- Limitations khud pehle bolo (synthetic data, hand-set weights). Ye interviewer par achha asar karta hai.
