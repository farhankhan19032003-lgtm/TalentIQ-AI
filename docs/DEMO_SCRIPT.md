# Demo script (3 minutes)

Covers: paste a JD and show the extracted requirements, upload 12+ resumes in one batch (with bad files and a duplicate), ranking table, open the top candidate, explain a score with the worked example, open a weaker candidate and show its missing skills, show duplicate handling. Everything is fictional sample data.

## Before recording (2 minutes, once)
```powershell
python scripts/reset_demo_data.py --set none   # wipes the database and uploads and restarts the stack: an EMPTY database (asks you to type 'reset')
docker compose down -v ; docker compose up -d --build   # manual alternative: an EMPTY database, http://localhost:8080 (first build takes several minutes)
```
For the recording the database must be **empty** (the demo uploads the files itself). Have these ready in File Explorer: `sample_data\job_descriptions\python_backend_developer.txt` (open it to copy) and the 15 + 4 files listed in `sample_data\demo_set.json` (select them all in `sample_dataesumes\`). Shortcut that skips the clicking (not for the video): `python scripts/load_samples.py --demo --run`.

Expected, so nothing surprises you (measured on a fresh stack): upload of 19 files ~4 s; first "Run matching" ~8 s (the model loads once), later runs ~1 s.

## The 3 minutes

| Time | Do | Say |
|---|---|---|
| **0:00** | **Jobs → New job.** Paste the JD, click **Analyse requirements**. Point at the line "3+ years of experience · Bachelor's degree", the minimum-years box, the **Minimum qualification** dropdown and the requirement list. Click **Save job**. | "Module 1. I paste a job description, or I could upload a PDF, DOCX or TXT; all three give the same result. It extracts the skills and splits them into must-have and preferred, reads the experience and the degree requirement, and all of it is editable before I save. `Unit Testing (pytest)` is one requirement, and `FastAPI or Django` is satisfied by either." |
| **0:30** | **Upload resumes.** Click the drop zone, select the 19 files, **Upload & parse**. Point at the chips (`16 parsed · 2 failed · 1 duplicate`) and the table. | "Module 2. Fifteen resumes, PDF and DOCX, plus four deliberately hard files, in one batch. The corrupted PDF and the password-protected PDF are rejected with a clear reason, and the rest of the batch is untouched. The scanned PDF was read with OCR so it is flagged *needs review*. And a byte-identical copy of Anika Menon's resume is recognised as a duplicate by its file hash and skipped instead of ranked twice." |
| **1:00** | **Ranking → Run matching.** Show the **Simple view** (on by default): Candidate, Experience, Match %, Matched Skills. Point at the strip above the table ("19 files received → 16 parsed · 2 failed · 1 identical duplicate skipped"). Click **Show duplicates**. Toggle **Simple view** off for a second to show the detailed columns, then back on. | "Module 3 and 4. Every resume gets a score from 0 to 100 from skills, semantic similarity, experience, education and projects. Skills have three looks: **✓ exact**, **≈ related, partial credit**, **✗ missing**. Lakshmi 92, Vikram 89, Manish 73; the weak fits are around 10. Every file is accounted for: 19 received, 16 ranked, 2 failed, 1 duplicate." |
| **1:30** | **Click Lakshmi Narayan.** Scroll: headline sentence, profile, skills, experience comparison. | "Module 5. First a plain sentence: *Strong match, 92. Direct evidence for 7 of 7 must-haves. 11.4 years relevant experience meets the 3+ required.* Then the extracted profile, the skills, and an experience card comparing what the job requires with what she has." |
| **1:50** | **Back, click Sana Qureshi (rank 4).** Show the score table, then the grey note under it. | "The score explained. Sana scores **67.11**. Technical is **52.86**: 5.55 weighted credit out of 10.5. Python, REST APIs and Unit Testing are full credit, Git 0.85 because it is only in a skills list, Flask and MySQL earn **0.35 related credit** for Django and PostgreSQL, Docker is missing. Semantic is **50.45**, experience **100** (4.5 relevant years against 3 required), education **100**. Her resume has no projects section, so that 5% is left out and the other weights are rescaled, which is why Technical counts 42.1% and not 40: 22.26 + 13.28 + 21.05 + 10.53 = **67.11**. The range 63.8 to 68.8 shows what the missing section could change." |
| **2:20** | **Back, click Farah Ali (rank 11).** Show "Skills vs the job" and the experience card. | "A weak match: 29. One of seven must-haves has evidence; FastAPI or Django, REST APIs, PostgreSQL, Git and Python are all ✗ missing. Her 13 years are in a different field, so relevant experience is 0.0 years against the 3 required. The page says so in plain words instead of showing a bare number." |
| **2:40** | **Open the scanned candidate, Ritu Sharma.** Show the amber **Needs review** banner. | "Failures are handled per file and never silently scored: a scanned file is clearly marked for review, and files that cannot be read are rejected with the reason." |
| **2:52** | Close on the ranking page. | "It is decision support: nobody is auto-rejected, and every evidence line is the exact text from the resume." |

## If something goes wrong on camera
- Ranking empty → you are on the wrong **Active job** (top bar); pick *Python Backend Developer*.
- First match is slow → the model loads once; run it once before recording.
- Different numbers → you did not start from an empty database, or you changed weights. `docker compose down -v` and repeat.

## Run-through result (executed, not assumed)
This script was run in a real browser (Chrome driven by Playwright) against a fresh `docker compose` stack with an empty PostgreSQL database, using the file chooser for the upload (2026-11-19).

| Step | Result |
|---|---|
| 1. paste JD, analyse, save | OK: "3+ years of experience · Bachelor's degree", editable fields shown |
| 2. upload 19 files in one batch | OK: 16 parsed, 2 failed (corrupted, password-protected), 1 duplicate; 2 of the 16 flagged "needs review" (the scanned PDF and a resume that states no role) |
| 3. run matching | OK: 16 candidates ranked, Simple view default, no console errors, no failed HTTP calls |
| 4. top candidate | OK: "Strong match (92/100). Direct evidence for 7 of 7 must-have skills ..." |
| 5. Sana Qureshi | OK: 67.11, 4 exact / 2 related / 6 missing skills, experience verdict "Meets the requirement" |
| 5b. weaker candidate (Farah Ali) | OK: "Poor match (29/100)", 1 of 7 must-haves, relevant experience 0.0 y, six must-haves shown as ✗ missing, weight-rescale note visible |
| 6. scanned file | OK: "Needs review. Scanned/image-only file read with OCR ..." banner |
| 7. failed files on Resume batches | OK: both listed with their reasons |
| 8. duplicate handling | OK: "19 files received → 16 parsed · 2 failed · 1 identical duplicate skipped"; list shows "byte-identical to anika_menon.pdf" |

Nothing broke. One thing to know: a candidate parsed before a parser upgrade keeps its old parse until the resume is re-uploaded (there is no re-parse button for already-parsed resumes).
