# Demo video script (about 8 minutes)

For the assignment "AI-Based Resume Matching & Ranking System". Narration is in English (for the reviewer); the **Do** column is your screen action. The structure follows the five modules and the evaluation table (functional app 25 %, parsing 15 %, matching logic 25 %, score and explanation 15 %, UI 10 %, code and docs 10 %).

## Before you record
1. `.\start.ps1` (PostgreSQL + backend + frontend). Check the terminal says `Database: PostgreSQL (port 5433)`.
2. Empty database: stop the app, delete the `talentiq` database or use a fresh one, start again. Do not show real resumes: use only `sample_data/` (all fictional).
3. Browser at http://localhost:5173, zoom 110 %, close other tabs and notifications. Have `sample_data/job_descriptions/python_backend_developer.docx` and 10+ files from `sample_data/resumes/` ready in a folder.
4. Record at 1080p with a screen recorder (OBS or Win+G). Do one dry run first.

## Script

| Time | Do | Say |
|---|---|---|
| 0:00 | Dashboard, then briefly the README architecture diagram | "Hi, I'm Farhan. This is TalentIQ AI: it takes a job description and a batch of resumes, ranks the candidates, and explains every score with the exact resume text behind it. Stack: React and Vite, FastAPI, PostgreSQL, and MiniLM sentence embeddings. It runs fully offline, no paid API." |
| 0:40 | **Module 1.** Jobs, New job, upload `python_backend_developer.docx` | "Module 1. I upload a JD as DOCX; pasting text works too. The system extracts the title, must-have versus preferred skills, years of experience, education level and responsibilities." |
| 1:10 | Point at extracted requirements. Show "FastAPI or Django" | "It understands alternatives: 'FastAPI or Django' is one requirement, satisfied by either. Everything is editable before saving, so a recruiter stays in control." Click Save. |
| 1:40 | **Module 2.** Upload resumes, select 15 files (PDF and DOCX), upload | "Module 2. I upload 15 resumes in one batch, PDF and DOCX mixed. Each is parsed for name, contact, skills, employment, education, projects and certifications." |
| 2:10 | Show batch summary chips. Then upload the bad files: corrupted PDF, password-protected PDF, fake `.pdf` | "One bad file never stops the batch. A corrupted PDF, a password-protected one and a fake extension are rejected with a clear reason, and the rest continue. Duplicates are detected by hash." |
| 2:45 | Open one parsed resume, show extracted fields and page/line source | "Every extracted field keeps its page and source line, so parsing can be audited." |
| 3:10 | **Module 3.** Jobs, Rank, expand **Scoring weights**, Run matching | "Module 3. The score is a hybrid, not keyword counting: 40 % technical skills, 25 % semantic similarity, 20 % experience, 10 % education, 5 % project and domain relevance. Weights are editable and must total 100." |
| 3:50 | Point at the run line "MiniLM", hover for model name | "Semantic similarity uses the all-MiniLM-L6-v2 sentence embeddings, so 'built REST services' still matches 'API development' with no shared keyword. I run the model with my own NumPy implementation, so it works on a CPU-only laptop. Skills also go through a 160-skill ontology with synonyms and related-skill partial credit." |
| 4:20 | **Module 4.** Ranking table: Candidate, Experience, Match %, Matched skills. Sort by score, filter by a skill | "Module 4. The ranking dashboard: candidate, relevant years of experience, match percentage and matched skills, exactly like the assignment table. I can sort, filter by skill or score, paginate, compare up to five candidates and export CSV, Excel or PDF." |
| 5:00 | **Module 5.** Click the #1 candidate | "Module 5. Candidate-level analysis. Extracted details, overall score, and a bar chart plus a points table that adds up exactly to the final number." |
| 5:30 | Read the points table aloud: technical, semantic, experience, education, project | "Example: technical 36 points, semantic about 20, experience 20, education 10 and project 3. Overall equals the weighted sum, so there is no black box." |
| 6:00 | Matched and missing skills, experience comparison, "why matched" text | "Matched skills, missing skills, required versus actual years, and plain-language reasons. If a requirement has no evidence, it is shown as missing, never guessed." |
| 6:25 | Expand a requirement: highlighted resume snippet with page and section | "Each match shows the highlighted resume sentence with page and section. The snippet must be a verbatim substring of the resume. If it cannot be verified, it is discarded. The system cannot invent evidence." |
| 6:55 | Toggle **Blind screening** | "Fairness: blind screening hides names and contacts, and the ranking does not change. Protected-attribute lines are scrubbed before matching. It is decision support: it never auto-rejects anyone." |
| 7:15 | What-if: set minimum years to 12 | "What-if: if I raise the experience requirement to 12 years, I can see who moves and by how much. This is a preview, nothing is saved." |
| 7:35 | Override: score 90 plus a reason, show it beside the machine score | "A recruiter can override with a required reason. The machine score is never rewritten, and the override is audit-logged." |
| 7:50 | Terminal: `python -m pytest -q`, show `237 passed`. Then the GitHub repo | "Code quality: 237 automated tests pass on PostgreSQL 16, migrations run with Alembic, and the README documents setup, architecture and the scoring method. Source is on GitHub." |
| 8:10 | Limitations slide or README "Known limitations" | "Honest limits: it is tested on synthetic resumes only, the ground truth is author-defined, and MiniLM beats the TF-IDF baseline by only a small margin on this set. Weights are hand-set, not learned. It is a prototype, not production-ready. Thank you." |

## If the reviewer asks "how is the percentage calculated?"
```
Overall = 0.40 * Technical + 0.25 * Semantic + 0.20 * Experience + 0.10 * Education + 0.05 * Project/Domain
```
- **Technical:** weighted share of required skills found; must-have counts double; related skills get partial credit.
- **Semantic:** cosine similarity of MiniLM embeddings between the JD and the resume text, mapped to 0-100.
- **Experience:** relevant years (only roles relevant to the JD) versus the required minimum and preferred years.
- **Education:** candidate level versus required level.
- **Project/Domain:** overlap of project and domain terms with the JD.
- A component the JD does not ask for is dropped and the others are renormalised. Missing evidence scores 0 but widens the score range (for example `62-75`) instead of counting as a mismatch.

Details: `docs/AI_MATCHING_ALGORITHM.md`.

## Recording tips
- Keep each take under about 8 minutes; cut the pauses while matching runs (it takes about 5 seconds).
- Speak slowly, and use the mouse to point at what you describe.
- Do not show `.env`, terminal history or any real personal data.
- Upload the video as unlisted (YouTube or Drive) and put the link in the README and the submission email.
