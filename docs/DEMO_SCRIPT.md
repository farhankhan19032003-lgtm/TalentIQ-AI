# Demo script (3 minutes)

Covers: create a JD by pasting, upload 12+ resumes in one batch, show the ranking, open the top candidate, explain a score with the worked example, show failed files handled gracefully. Everything is fictional sample data.

## Before recording (2 minutes, once)
```powershell
docker compose down -v                  # empty database, so the ranking contains only the demo resumes
docker compose up -d --build            # http://localhost:8080  (first build takes several minutes)
```
Have these ready in File Explorer: `sample_data\job_descriptions\python_backend_developer.txt` (open it to copy) and the 15 + 3 files listed in `sample_data\demo_set.json` (select them all in `sample_data\resumes\`). Shortcut that skips the clicking (not for the video): `python scripts/load_samples.py --demo --run`.

Expected, so nothing surprises you (measured on a fresh stack): upload of 18 files ~4 s; first "Run matching" ~9 s (the model loads once), later runs ~1 s.

## The 3 minutes

| Time | Do | Say |
|---|---|---|
| **0:00** | **Jobs → New job.** Paste the JD, click **Analyse requirements**. Point at the line "3+ years of experience · Bachelor's degree", the minimum-years box and the **Minimum qualification** dropdown, then the requirement list. Click **Save job**. | "Module 1. I paste a job description, or I could upload a PDF, DOCX or TXT. It extracts the skills and splits them into must-have and preferred, reads the experience and the degree requirement, and all of it is editable before I save. Note `Unit Testing (pytest)` is one requirement, not two, and `FastAPI or Django` is satisfied by either." |
| **0:35** | **Upload resumes.** Click the drop zone, select the 18 files, **Upload & parse**. When the result appears, point at the chips (`16 parsed · 2 failed`) and the table. | "Module 2. Fifteen resumes, a mix of PDF and DOCX, plus three deliberately hard files, in one batch. 16 parsed. The corrupted PDF and the password-protected PDF are rejected with a clear reason and the rest of the batch is untouched." Point at the two amber rows (**parsed: needs review**): "The scanned, image-only PDF was read with OCR, so it is flagged for review instead of being treated like a normal resume." |
| **1:15** | **Ranking → Run matching.** Show the **Simple view** (on by default): Candidate, Experience, Match %, Matched Skills. Mention the strip above the table ("18 files received → 16 parsed · 2 failed"). Hover a related chip. Toggle **Simple view** off for one second to show the detailed columns. | "Module 3 and 4. It scores every resume from 0 to 100 using skills, semantic similarity from MiniLM embeddings, experience, education and projects, and ranks them. Skills have three looks: **✓ exact**, **≈ related, partial credit**, **✗ missing**. The top three are Lakshmi 92, Vikram 89, Manish 73; the weak fits, an accountant and a statistician, are around 10." |
| **1:40** | **Click Lakshmi Narayan.** Scroll slowly: headline sentence, profile, skills, experience comparison. | "Module 5. The first thing is a plain sentence: *Strong match, 92. Direct evidence for 7 of 7 must-haves. 11.4 years relevant experience meets the 3+ required.* Below it: the extracted profile, the skills, and an experience card that compares what the job requires with what she has." |
| **2:05** | **Back to ranking, click Sana Qureshi (rank 4).** Show the score table and "Skills vs the job". | "Now the score explained. Sana scores **67.11**. Technical is **52.86**: 5.55 weighted credit out of 10.5. Python, REST APIs and Unit Testing are full credit, Git is 0.85 because it is only in a skills list, and Flask and MySQL earn **0.35 related credit** for Django and PostgreSQL. Docker is missing. Semantic is **50.45**, experience **100** because 4.5 relevant years beats the 3 required, education **100**. Weights 40, 25, 20 and 10, with projects left out because her resume has no project section: that is 22.26 + 13.28 + 21.05 + 10.53 = **67.11**, and the range 63.8 to 68.8 shows what the missing section could change." |
| **2:40** | **Open the scanned candidate, Ritu Sharma, or the Resume batches page.** Show the amber **Needs review** banner or the failure reasons. | "Failures are handled per file and never silently scored: a scanned file is clearly marked for review, and files that cannot be read are rejected with the reason." |
| **2:55** | Close on the ranking page. | "It is decision support: no one is auto-rejected, and every evidence line is the exact text from the resume." |

## If something goes wrong on camera
- Ranking empty → you are on the wrong **Active job** (top bar); pick *Python Backend Developer*.
- First match is slow → the model loads once; run it once before recording.
- Different numbers → you did not start from an empty database, or you changed weights. `docker compose down -v` and repeat.

## Run-through result (executed, not assumed)
This script was run in a real browser (Chrome driven by Playwright) against a fresh `docker compose` stack with an empty PostgreSQL database, using the file chooser for the upload.

| Step | Result |
|---|---|
| 1. paste JD, analyse, save | OK: "3+ years of experience · Bachelor's degree", editable fields shown |
| 2. upload 18 files in one batch | OK: 16 parsed, 2 failed (corrupted, password-protected), 2 of the 16 flagged "needs review" (the scanned PDF and the near-empty resume) |
| 3. run matching | OK: 16 candidates ranked, no console errors, no failed HTTP calls |
| 4. top candidate | OK: "Strong match (92/100). Direct evidence for 7 of 7 must-have skills ..." |
| 5. Sana Qureshi | OK: 67.11, 4 exact / 2 related / 6 missing skills, experience verdict "Meets the requirement" |
| 6. scanned file | OK: "Needs review. Scanned/image-only file read with OCR ..." banner |
| 7. failed files on Resume batches | OK: both listed with their reasons |

Nothing broke. One thing to know: a candidate parsed before a parser upgrade keeps its old parse until the resume is re-uploaded.
