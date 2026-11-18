# Matching algorithm (v2.0.0)

How TalentIQ turns a job description and a resume into a 0-100 score and an explanation. Every number named here lives in
`backend/app/core/config.py` (`DEFAULT_WEIGHTS`, `SCORING`, `CALIBRATION`); nothing is hidden in the code.

All results below were produced on the **fictional** sample set in `sample_data/` (6 JDs, 35 parsable resumes = 210 JD/resume pairs). See [Limitations](#limitations-and-future-work).

## 1. Pipeline at a glance

```
JD text ──► (1) JD parsing ─────────────► requirements (must / preferred / "X or Y"), min years, degree level
Resume ───► (2) resume parsing ─────────► name, contact, dated roles, education, projects, skills (+ page and source line)
                      │
                      ▼
            (3) skill normalisation ────► every skill mapped to one canonical ontology name (synonyms, aliases)
                      │
                      ▼
            (4) semantic embedding ─────► MiniLM sentence vectors -> cosines (document level and responsibility level)
                      │
                      ▼
            (5) five components (0-100 each) ──► (6) weighted sum ──► overall 0-100 + range + explanation ──► ranking
```

### Step 1. JD parsing (`services/jd_analyzer.py`)
- Splits the JD into sections by heading ("Requirements", "Nice to have", "Responsibilities"). Skills named under *Nice to have* (or in a line with "preferred / plus / bonus") are **preferred**; skills only named in *Responsibilities* are also preferred (they describe the work, not a hard requirement); all others are **must-have**.
- "X or Y" becomes **one** requirement satisfied by either (`any_of`), e.g. `FastAPI or Django`.
- **One concept, one requirement.** "Unit Testing with pytest" names a practice and a tool; counting them separately would penalise a candidate twice for one missing idea. `CONCEPT_TOOLS` merges them into a single `Unit Testing (pytest)` requirement that any of the names satisfies. (Python→FastAPI is *not* merged: a language and a framework are different requirements.)
- Skills in the **job title** are role-defining and weigh x2.
- Minimum years (`3+ years of experience`), degree level (diploma < bachelor < master < doctorate) and responsibilities are extracted. Everything is editable in the UI before saving, including the minimum years and the qualification.

### Step 2. Resume parsing (`services/document_parser.py`, `resume_extractor.py`)
- PDF: PyMuPDF text in reading order (two-column aware); pdfplumber fallback for malformed files; Tesseract OCR for image-only pages. DOCX: paragraphs, list bullets, tables (layout tables read column by column) and **text boxes**.
- Sections are found by heading (`Experience`, `Work History`, `Career History`, `Professional Background`, `Internships`, `Education`, `Skills`, `Projects`, ..., with decoration such as `— CAREER HISTORY —` or `EDUCATION:` stripped).
- Employment dates: `Jan 2020 - Present`, `2019-2023`, `2019-23`, `03.2020 - 05.2021`, `03/2020 to Present`, `Jan '20 - Mar '22`, `2022 to date`, `since 2021`; three-line headers (title / company / dates) are handled.
- When there is **no dated employment** (freshers, or experience only written as text): the role shown is the resume's own headline (title line under the name, else the first clause of the summary), marked "(profile)"; a stated "6+ years of experience" is kept as `claimed_years` and credited at 60 % (it cannot be verified); otherwise experience is `unverified` and shown as "No dated roles".
- **A scanned/image-only file is never silently treated as a normal resume.** With OCR available it is parsed and flagged **needs review** (`scanned_ocr`); without OCR (or if OCR finds no text) it is *not scored* and reported as "Needs review: no extractable text". Other parse-quality flags: low text quality, malformed PDF recovered by the fallback reader, no name found.

### Step 3. Skill normalisation (`services/skill_extractor.py`, `data/skill_ontology.json`)
A 160-skill ontology maps aliases to one canonical name ("postgres", "psql" → PostgreSQL; "k8s" → Kubernetes). Ambiguous names (C, Go, R, Lambda, Spring) only match as exact list items; case-sensitive names (Excel, Oracle) need the right case. For each skill the extractor records every mention with page, section and source line, and whether the skill appears **in context** (experience/projects text) or **only in a skills list**.

### Step 4. Semantic embedding (`services/semantic_matcher.py`)
`all-MiniLM-L6-v2` (384-d, mean pooling, L2-normalised, 256-token limit) run with sentence-transformers when installed, otherwise by the bundled pure-NumPy implementation of the same network. If the model files are missing the engine falls back to TF-IDF and the run records which method was used and why. Two cosines are used:
- **document level**: JD narrative (title + responsibilities + required qualifications) vs resume narrative (summary + experience);
- **responsibility level**: each JD responsibility vs its best-matching resume line, averaged.

### Step 5-6. Components and final score

```
Overall = 0.40·Technical + 0.25·Semantic + 0.20·Experience + 0.10·Education + 0.05·Project/Domain      (weights editable, must total 100 %)
```

Components the JD does not require are dropped and the remaining weights renormalised. A component with **no resume evidence** is `unverified`: **Project/Domain** is then left out of the point estimate (weights renormalised), every other unverified component scores 0. The page always shows the range `low-high`: *low* = left-out components scored 0, *high* = unverified components scored 100; the headline score is between them.

| Component | Weight | How it is scored |
|---|---|---|
| **Technical skills** | 40 % | per requirement `credit x weight`, divided by the total weight (table below) |
| **Semantic relevance** | 25 % | `0.5·doc + 0.5·resp`, each cosine mapped linearly to 0-100 by the calibration ranges below |
| **Relevant experience** | 20 % | `min(1, relevant_years / min_years)`; with a preferred maximum: `0.7·that + 0.3·min(1, relevant_years / preferred)` |
| **Education** | 10 % | 100 if candidate level ≥ required, else `100·candidate / required`; capped at 85 if a preferred higher level is not met |
| **Project/Domain** | 5 % | similarity of project text to the JD, plus a domain-term bonus that can only add |

**Technical credit per requirement** (`SCORING`):

| Evidence | Credit |
|---|---|
| exact or synonym, used in experience/projects text | 1.00 |
| exact or synonym, only in a skills list | 0.85 |
| a **related** skill instead (Flask for Django/FastAPI, MySQL for PostgreSQL, parent skills such as PostgreSQL → SQL) | 0.35 |
| not named, but a resume line is semantically close enough (cosine ≥ 0.50, MiniLM) | 0.10 - 0.25, linear |
| nothing | 0 |

Weights: must = 1.0, preferred = 0.5, title skill x2. "X or Y" takes the best alternative. **Related skills are never shown as matched**: they have their own chip style and say "Related (partial) 35 %" on both the ranking table and the candidate page.

**Experience.** Employment periods become sets of calendar months, so overlapping jobs are never double counted; part-time and internship months count 50 % of months not already covered; year-only dates assume July-June and are flagged uncertain. A role counts as **relevant** by its *fit*: the weighted share of the job's requirements the role demonstrates (a related skill counts 35 %). Fit ≥ 25 % (≥ 15 % if the job title matches the JD title) makes the whole role relevant. Generic tools (Git, Docker) therefore no longer make every developer role "relevant" to every job.

## 2. Worked example (real output)

Job: *Python Backend Developer* (`sample_data/job_descriptions/python_backend_developer.txt`). Candidate: **Sana Qureshi** (`sana_qureshi.docx`, fictional). MiniLM, default weights. Live result: **71.27, "Good match", rank 4 of 17**.

**Requirements (weight m, credit c):**

| Requirement | m | Evidence | c | m·c |
|---|---|---|---|---|
| Python (title skill) | 2.0 | used in experience | 1.00 | 2.00 |
| REST APIs | 1.0 | used in experience | 1.00 | 1.00 |
| Unit Testing (pytest) | 1.0 | "Unit Testing" satisfies the merged requirement | 1.00 | 1.00 |
| Git | 1.0 | only in a skills list | 0.85 | 0.85 |
| FastAPI or Django | 1.0 | has Flask: related, not equivalent | 0.35 | 0.35 |
| PostgreSQL | 1.0 | has MySQL: related, not equivalent | 0.35 | 0.35 |
| Docker | 1.0 | none | 0 | 0 |
| Celery, AWS, Redis, CI/CD, Kubernetes | 0.5 each | none | 0 | 0 |
| **Total** | **10.5** | | | **5.55** |

**A. Technical** = 100 × 5.55 / 10.5 = **52.86**

**B. Semantic.** Document cosine 0.6435 → (0.6435 − 0.25) / (0.75 − 0.25) = 78.69. Responsibility cosines 0.473, 0.156, 0.432, 0.185 → mean 0.3115 → (0.3115 − 0.15) / (0.45 − 0.15) = 53.82. Semantic = 0.5 × 78.69 + 0.5 × 53.82 = **66.25**

**C. Experience.** Role "Python Developer" (Jun 2022 - present): fit 0.448 ≥ 0.25 → relevant, 4.5 years. The 5-month internship has fit 0.19 → not relevant. 4.5 ≥ 3 required → **100**.

**D. Education.** B.Tech (bachelor) vs bachelor required → **100**. **E. Project/Domain.** No projects section → `unverified`, left out.

| Component | Score | Weight | Effective weight (÷ 0.95) | Points |
|---|---|---|---|---|
| Technical | 52.86 | 0.40 | 0.4211 | 22.26 |
| Semantic | 66.25 | 0.25 | 0.2632 | 17.43 |
| Experience | 100 | 0.20 | 0.2105 | 21.05 |
| Education | 100 | 0.10 | 0.1053 | 10.53 |
| Project/Domain | unverified | 0.05 | 0 | 0.00 |
| **Overall** | | | | **71.27** |

Range: low = (0.40·52.86 + 0.25·66.25 + 0.20·100 + 0.10·100) = **67.71**; high = low + 0.05·100 = **72.71**. Headline shown on the candidate page: *"Good match (71/100). Direct evidence for 4 of 7 must-have skills and related evidence for 2 more. Relevant experience 4.5 y (4.7 y total) meets the 3+ y required. Missing must-haves: Docker."*

## 3. Calibration: what was changed and why

**Problem found.** In a demo run of 23 candidates nothing scored above 70 and the best was 64.7 (average 41.6). Two causes were found by measuring all 210 JD/resume pairs against the author's relevance grades (0-3):

1. *The demo batch simply contained no strong candidate for that JD* (the strong ones were not uploaded). Not a bug.
2. *Real calibration problems*: (a) poor-fit candidates still received full Experience credit; (b) the responsibility-level cosine was mapped with the document-level range, so even excellent matches scored ~47 there; (c) a missing Projects section was scored as 0 for everyone.

**Measured raw cosines** (MiniLM, 210 pairs, median / 90th percentile by relevance grade):

| Grade | doc cosine | responsibility cosine |
|---|---|---|
| 3 (strong) | 0.81 / 0.86 | 0.41 / 0.46 |
| 2 | 0.60 / 0.67 | 0.32 / 0.39 |
| 1 | 0.45 / 0.55 | 0.27 / 0.32 |
| 0 (unrelated) | 0.33 / 0.51 | 0.21 / 0.28 |

**Changes** (all in `config.py`, each with a regression test in `tests/test_scoring_calibration.py`):

| # | Change | Reason |
|---|---|---|
| 1 | Role relevance by weighted **fit** (≥ 25 %) instead of "≥ 2 shared skills" | the old rule counted Git + Docker as relevant to any job, giving unrelated candidates 100 on Experience |
| 2 | Separate range for responsibility-level cosine: `0.15 → 0`, `0.45 → 100` (document level `0.25 → 0`, `0.75 → 100`) | responsibility pairs are sentence-to-sentence, so their cosines are systematically lower; ranges are anchored on the table above (unrelated ≈ 0.2 → ~20, strong ≈ 0.41 → ~87) |
| 3 | Unverified Project/Domain is left out of the point estimate (range kept) | "no Projects section" is missing information, not a mismatch; counted as 0 it capped every such resume at 95 |
| 4 | `Unit Testing` + `pytest` merged into one requirement | one concept was counted (and missed) twice |
| 5 | Peer skills give 0.35 related credit | a Flask developer is closer to a Django job than to an accounting job; they are still never shown as exact |

**Not inflated.** Weights, credits and the 0.35 / 0.85 values are unchanged. Poor fits got *lower* (grade-1 median 48 → 34), strong fits got higher only because structural penalties were removed.

| Relevance grade | Median score before → after | Range after | n |
|---|---|---|---|
| 3 strong | 81 → **91** | 67 - 97 | 13 |
| 2 | 63 → 67 | 36 - 82 | 22 |
| 1 | 48 → 34 | 7 - 68 | 48 |
| 0 unrelated | 18 → 18 | 4 - 58 | 127 |

| Evidence of fit | Result |
|---|---|
| ≥ 75 % of must-haves directly evidenced (11 pairs) | 9 of 11 score ≥ 80 (median 91) |
| ≤ 25 % of must-haves evidenced (145 pairs) | 138 of 145 score < 40 |
| Pairs ordered correctly against the grades | 88.5 % → **89.8 %** |

Guard-rail test (`test_scoring_calibration.py`): a clearly strong, a medium and a clearly weak fictional resume must satisfy `strong > medium > weak`, `strong ≥ 80`, `50 ≤ medium < 80`, `weak < 40` with both TF-IDF and MiniLM.

## 4. Confidence, completeness and review flags (kept separate from the score)
- *Confidence* = mean(parse confidence, share of evidence snippets verified as verbatim resume text, date certainty).
- *Completeness* = share of 8 field checks present (name, contact, summary, employment, education, skills, projects, dated roles).
- *Needs review* = parse flag (scanned/OCR, low text quality, recovered PDF, no name) **or** confidence < 60 **or** completeness < 60 **or** score range > 15.

## 5. Ranking and stability
Sort by overall desc, technical desc, candidate id asc (deterministic). Sensitivity re-ranks under ±10 percentage-point changes of each weight (renormalised); a rank is "stable" when its range across scenarios is ≤ 1. A recruiter can override a score with a written reason; the machine score is never rewritten.

## 6. Limitations and future work
- **Synthetic data only.** Skills, years and grades are author-defined; the same 210 pairs were used to choose the calibration ranges and to report the results (no held-out set). Real resumes will have different cosine distributions, so `CALIBRATION` and the 25 % fit threshold should be re-fitted on labelled real data.
- Synthetic resumes reuse the JD's vocabulary, which flatters document-level similarity.
- The related-skill table is hand-made (34 skills with related entries; peer groups only for web frameworks and relational databases).
- Experience relevance depends on the role text naming the job's skills; a role described in vague words scores low.
- 160-skill ontology: unlisted skills are invisible. No layout-aware parsing of images or tables inside PDFs; PDF parsing is in-process (not sandboxed).
- Candidates parsed before a parser upgrade keep their old parse until re-uploaded.
- Future work: learn calibration from recruiter decisions, embed skills with a larger model, per-role fit shown as evidence highlights, human-labelled benchmark, re-parse button.

## 7. What the score is not
It is a similarity-and-evidence signal, **not** a probability of being hired or of job performance. Weights, thresholds and calibration ranges are hand-set heuristics that have not been validated on real hiring outcomes.
