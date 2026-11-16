# 5-minute demo plan

**Setup (before the audience arrives):** both servers running, **empty database**, `python scripts/fetch_minilm.py` already run, browser at http://localhost:5173. Use only resumes you have consent to show (your own, or volunteers'). Flow: Jobs → New job → upload a JD (.pdf/.docx/.txt) or paste one → Save; then Upload resumes → select 10+ PDF/DOCX files.

| Min | Do | Say |
|---|---|---|
| 0:00 | Dashboard | "TalentIQ ranks candidates *and shows the resume text behind every score*. It is decision support — it never rejects anyone." |
| 0:30 | Upload resumes → select 10+ PDF/DOCX files (add one corrupted file to show error handling) | "A batch of resumes, PDF and DOCX mixed. One bad file must not stop the batch." Point at the summary chips (parsed, failed, duplicate, rejected). |
| 1:15 | Jobs → open **AI/ML Engineer** (Edit) | "Requirements are extracted from the JD and you can change must/preferred/ignore. 'FastAPI or Django' style alternatives are understood." |
| 1:45 | Rank → **Run matching** | "Hybrid score: 40 technical, 25 semantic, 20 experience, 10 education, 5 project. Open *Scoring weights* to show sliders that must total 100 %." Point at "MiniLM sentence embeddings" in the run line: the semantic part compares meaning, not just shared words (hover it for the model name). |
| 2:30 | Open the #1 candidate | Walk the bar chart and the points table summing to the overall score. |
| 3:00 | Expand a requirement | "Highlighted text is a **verbatim** substring of the resume, with page and section. If a snippet cannot be verified it is discarded." Expand a *missing* one: "No evidence" — never invented. |
| 3:30 | Toggle **Blind screening** | "Names and contacts vanish; ranking is unchanged." |
| 3:45 | What-if | Set min years to 6 → "Preview only, nothing saved." |
| 4:15 | Override | Enter 90 + reason → "The machine score stays; the override sits beside it and is audit-logged." |
| 4:40 | Export PDF/CSV, Analytics | Show score distribution and "most missing skills". |
| 5:00 | Close | State limitations: synthetic benchmark only, tiny margin over the TF-IDF baseline (MiniLM 0.945 vs TF-IDF 0.943 NDCG@5: a tie on this set), weights are hand-set, PostgreSQL tested on one version (16.4) and not under load. |

**Fallback if something breaks:** `docs/AUDIT_REPORT.md` has the recorded test evidence; `python -m pytest -q` runs in about a minute (237 tests). Before recording, tick every box in [PRE_DEMO_CHECKLIST.md](PRE_DEMO_CHECKLIST.md).
