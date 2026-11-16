# Pre-demo checklist

Tick every box before you record or present. Items marked **YOU** cannot be done by the assistant (needs your accounts, screen or eyes).
Status written 2026-11-16, Windows. Everything under "Already verified" was run; nothing there is assumed.

## 0. Already verified (no action, just know it)
- [x] Backend suite 237 passed on SQLite and on PostgreSQL 16.4; frontend 31 passed; `tsc` + `vite build` clean.
- [x] Assignment Modules 1-5 worked in a real browser on an empty database (JD pdf/docx/txt, 12-file and 50-file batch upload, ranking table with matched skills, candidate analysis).
- [x] Semantic matching uses MiniLM (pure NumPy runtime) and the ranking page says so.
- [x] 50-resume pack: 50 parsed, 10/10 strong matches in the top 10 (details and weaknesses in README and docs/TESTING.md).
- [x] Interview-notes form: create, edit, delete, both Cancel paths, score unchanged.

## 1. Data and privacy (do this first)
- [ ] **YOU** Delete any real personal resume (a PDF of your own, for example) from your Downloads folder or keep it far away from the demo folders; the assignment forbids real personal data. Real resumes were removed from the app, the uploads folder and the database.
- [ ] Decide which database to demo with:
  - **Option A (recommended): empty database.** Stop the app (`.\start.ps1 -Stop`), rename `backend\talentiq.db` to `backend\talentiq_backup.db` (keep it, or delete it), start again (`.\start.ps1`). Then upload live: JD from `AI_ML_Resume_Test_Pack_50\sample_job_description.txt`, resumes from `AI_ML_Resume_Test_Pack_50\50_synthetic_resumes`.
  - Option B: keep the current database (84 synthetic candidates, 6 sample jobs). Fine to show, but the "upload" step then has nothing new to show unless you use different files.
- [ ] Only synthetic files are visible in the file chooser while recording (open the chooser once beforehand and check that no personal folders are in the path bar).
- [ ] The two e-mail domains you will see are `example.test`; nothing else.
- [ ] The reports in `Downloads\TalentIQ_reports` and `TalentIQ_reports.zip` come from the synthetic data (scanned: no real name). Regenerate them if you change the database.

> Done on 2026-11-16: the app was restarted on an **empty database**. The previous one (84 synthetic candidates, 6 jobs) is kept as `backend\talentiq_backup.db` with its files in `backend\storage\uploads_backup\` (both git-ignored). To get it back: `.\start.ps1 -Stop`, move `talentiq_backup.db` to `talentiq.db` and the files back into `backend\storage\uploads\`, `.\start.ps1`. Delete both backups if you do not need them.

## 2. Start-up (5 minutes before)
- [ ] `cd` to the project, run `.\start.ps1`. Backend http://localhost:8000/api/docs and frontend http://localhost:5173 both open.
- [ ] Dashboard loads with no red error box.
- [ ] Ranking page: after **Run matching** the run line says "MiniLM sentence embeddings". If it says TF-IDF, run `python scripts\fetch_minilm.py` (about 90 MB, hash-checked) and restart.
- [ ] Tesseract installed if you want to show the scanned resume (`C:\Program Files\Tesseract-OCR`); otherwise skip that file.
- [ ] Browser zoom 100 %, window wide enough that the Ranking table shows the Matched skills column; close other tabs and notifications.
- [ ] Screen recorder tested: microphone level, the right monitor, 1080p.

## 3. Demo run-through (follow docs/DEMO_SCRIPT.md, 5 minutes)
- [ ] Module 1: Jobs > New job > paste or upload the JD > **Analyse requirements** > check must/preferred > **Save job**.
- [ ] Module 2: Upload resumes > select 10 or more PDF/DOCX > **Upload & parse** > show the summary chips (parsed / failed / duplicate / rejected).
- [ ] Module 3 and 4: Ranking > **Run matching** > point at Experience, Match % and Matched skills columns; mention hybrid weights 40/25/20/10/5.
- [ ] Module 5: open the #1 candidate > matched and missing skills, experience comparison, "Why this score", verbatim evidence.
- [ ] Extras worth 20 seconds each: Blind screening, What-if, Override with reason, PDF/Excel report, Interview notes.
- [ ] Rehearse once end to end. Time it; the plan is 5 minutes.

## 4. Say these limitations out loud (graders value honesty)
- [ ] Tested on synthetic data only; no real resumes; the answer keys are author-defined or "intended profile", not human judgements.
- [ ] MiniLM vs TF-IDF is a tie on the author's benchmark (0.945 vs 0.943 NDCG@5); embeddings help mainly on paraphrases (TF-IDF 0.00, MiniLM 0.31 to 0.57).
- [ ] Weak profiles are not always pushed to the bottom (best "Adjacent/weak" resume ranks 13th because its skills genuinely match; see docs/TESTING.md).
- [ ] It is decision support: it never rejects anyone; a recruiter decides.
- [ ] PostgreSQL tested on one version (16.4), not under load; PyTorch runtime and Linux/macOS not tested.

## 5. Repository (GitHub)
- [ ] **YOU** Install Git (it is not installed on this machine): https://git-scm.com/download/win
- [ ] **YOU** From the project root: `git init`, `git add .`, then check `git status` before committing: it must NOT list `*.db`, `backend/storage/uploads/*`, `backend/storage/models/`, `.venv`, `node_modules` or `.env` (the `.gitignore` already excludes them).
- [ ] **YOU** Search for personal data before the first commit: `git grep -i -E "gmail|linkedin|<your name>"` should find nothing except the synthetic `-demo` LinkedIn links in `scripts/generate_sample_data.py`; remove anything that is a real address.
- [ ] **YOU** Create the GitHub repository, `git remote add origin ...`, `git push`. The assistant does not push or create accounts.
- [ ] **YOU** Open the repository page in a private window: README renders, the folder `docs/` is there, no database or model file was uploaded.
- [ ] README top section says what the project is, how to run it (Quick start), and links to docs. It does.

## 6. Deliverables the assignment names
- [ ] GitHub repository link (section 5).
- [ ] README with setup + usage: done. Algorithm explanation: `docs/AI_MATCHING_ALGORITHM.md`. Architecture: `docs/ARCHITECTURE.md`. Test evidence: `docs/TESTING.md`, `docs/AUDIT_REPORT.md`.
- [ ] **YOU** Demo video recorded (use section 3), saved as MP4, link or file ready.
- [ ] **YOU** Open the final video once from start to end: audio audible, text readable, no personal data on screen, no error boxes.

## 7. Last-minute fallbacks
- Blank page: open the browser console; restart with `.\start.ps1 -Stop` then `.\start.ps1`.
- Matching error: check `GET http://localhost:8000/api/health`; `"database":"ok"` expected.
- Something looks wrong on camera: pause, fix, re-record; never show an error as if it were a feature.
- Evidence of correctness if asked: `python -m pytest -q` (about 1 minute, 237 tests) and `docs/AUDIT_REPORT.md`.
- Not covered by any test or check: how the Word and PowerPoint reports **look** in Office (only their contents were checked). Open one of each yourself before claiming they look good, or leave them out of the demo.
