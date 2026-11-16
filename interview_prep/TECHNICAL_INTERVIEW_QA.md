# Technical interview Q&A

Every answer describes the implementation as it exists in this repository and numbers measured in the sandbox (see `MODEL_EVALUATION.md`, `PERFORMANCE_REPORT.md`). Where something is unverified, the answer says so.

## Overview

**Q1. What does TalentIQ do in one sentence?**  
It ranks resumes against a job description and shows, for every score, the exact resume text that supports it, as decision support rather than automated rejection.

**Q2. Why not just use an LLM?**  
The brief required CPU-only, offline, no paid APIs on an 8 GB laptop. Rule-based extraction plus an ontology is also deterministic, fast (about 29 ms per resume) and traceable to text. The cost is lower recall on unusual phrasing and unlisted skills.

**Q3. What is the hardest problem you solved?**  
Making scores independent of resume formatting. Twin resumes with identical content but different date formats differed by 0.8 points because date tokens leaked into the similarity text. I stripped dates and separators before embedding (`clean_for_similarity`) and the twin difference became 0.0.

**Q4. What would you do differently?**  
Collect a small real, consented, double-annotated dataset first and build the evaluation before the matcher. My benchmark is synthetic and labelled by me, so it cannot tell me how it behaves on real resumes.

## Parsing

**Q5. How do you parse PDFs?**  
PyMuPDF extracts text blocks with coordinates; pdfplumber is a fallback. For two-column layouts I cluster x positions to detect columns and read the header, then the left column, then the right. Scanned pages are detected by low text per page and sent to Tesseract if installed.

**Q6. How do you handle DOCX?**  
python-docx reads paragraphs and headings in order; layout tables (a common two-column resume trick) are read column by column rather than row by row.

**Q7. What if a resume has no clear sections?**  
Sections are found by heading keywords. If none are found, fields that cannot be located are marked `unverified` or missing, completeness drops, and the score range widens. The system does not guess.

**Q8. How do you extract skills?**  
A 160-skill editable ontology with aliases. Matching is regex-based with guards: ambiguous names (C, Go, R, Swift, Lambda, Spring) only match as exact list items; case-sensitive names (Excel, Oracle, IAM) need exact case; 'Excel at teamwork' is excluded by a negative-lookahead list; degree lines in the education section are excluded.

**Q9. What are known weaknesses of the extractor?**  
Bare `R`/`Go` outside lists, inflections like 'recommender', skills not in the ontology, and the vendor 'Oracle' can false-positive. Skill F1 of 0.993 is optimistic because I refined the ontology after seeing errors on the same set.

**Q10. How do you detect corrupted or protected files?**  
Magic bytes catch fake extensions; PyMuPDF open errors are classified as `corrupt`; `needs_pass` gives `password_protected`; a corrupted DOCX fails the zip check and is `rejected`. Each file is isolated so one failure never stops the batch.

**Q11. How do you handle duplicates?**  
SHA-256 of the file content catches exact duplicates (reported, not re-parsed). Same email in a different file is flagged as a possible duplicate person.

**Q12. How is experience computed?**  
Each employment period becomes a set of calendar months. Full-time and contract months are unioned, so overlaps are not double counted; part-time and internship months not already covered count at 50 %. Year-only dates assume July start/June end and are flagged uncertain. Gaps are shown but never penalised.

**Q13. What counts as 'relevant' experience?**  
A role mentioning at least two JD skills, or one skill plus a title-token match. It is a heuristic and can misclassify unusual role descriptions.

## Matching and scoring

**Q14. State the scoring formula.**  
Overall = 0.40 Technical + 0.25 Semantic + 0.20 Experience + 0.10 Education + 0.05 Project/Domain. Components the job does not require are dropped and the remaining weights renormalised.

**Q15. Why those weights?**  
They come from the assignment brief and reflect that skills and meaning matter most. They are heuristics: I did not fit them to outcomes. The UI lets a recruiter change them and the what-if page previews the effect.

**Q16. How is the technical score computed?**  
100 · Σ m(r)·credit(r) / Σ m(r), where m is requirement importance (must 1.0, preferred 0.5, title skills ×2) and credit depends on match type: exact with context 1.0, listed-only 0.85, related 0.35, semantic 0.10–0.25, none 0.

**Q17. Why is a skills-list-only mention worth 0.85, not 1.0?**  
A list proves a claim, not use. Context in experience or projects is stronger evidence. The 0.85 value is a judgement call and is shown to the recruiter.

**Q18. What is partial credit?**  
A directional ontology relation: XGBoost supports Machine Learning. It earns 0.35 and the UI labels it 'Related', never 'Exact'.

**Q19. How do you handle 'FastAPI or Django'?**  
The JD analyser creates an `any_of` requirement. The matcher scores each alternative and takes the best, recording which one satisfied it.

**Q20. Explain cosine similarity.**  
cos(u,v) = u·v / (‖u‖‖v‖): the angle between two vectors, ignoring length. With non-negative TF-IDF vectors it lies in [0,1]. 1 means same direction (same word mix), 0 means no shared terms.

**Q21. Which embedding model do you use?**  
all-MiniLM-L6-v2 through sentence-transformers if installed, with a lazy singleton and an embedding cache; otherwise TF-IDF. In my sandbox the model could not be downloaded, so every reported number uses TF-IDF. The ranking page states which backend ran.

**Q22. Why fit TF-IDF only on the JD and ontology?**  
If it were fit on all candidates, one candidate's score would change when another was uploaded. Fitting on the JD plus ontology keeps scores independent of the pool.

**Q23. How do you turn cosine into a 0–100 score?**  
A linear calibration per method (TF-IDF 0.02→0, 0.40→100; MiniLM 0.20→0, 0.65→100). These ranges are documented heuristics, not learned, and the MiniLM range is unverified.

**Q24. What is 'unverified' and why does it exist?**  
When the resume lacks the data (no education section, no dated employment, no projects), the component scores 0 but is marked `unverified`. `score_high` shows what the overall would be if that evidence existed, so absence is visible without being treated as a mismatch.

**Q25. How are ties broken?**  
Overall score desc, technical score desc, candidate id asc, so rankings are deterministic and reproducible.

**Q26. What is rank sensitivity?**  
I re-rank under ±10 percentage-point changes of each weight (11 scenarios). A rank is 'stable' if it moves by at most 1. On the benchmark only about 51 % of results keep their rank, which is why the UI marks sensitive ranks.

**Q27. How do you know the score arithmetic is right?**  
A test recomputes the overall from stored components along a separate path, and the evaluation harness re-checks 210/210 stored results. That verifies the arithmetic, not that the weights are good.

**Q28. Does a higher score predict job performance?**  
No. It measures similarity of resume evidence to requirements. The UI and PDFs say it is not a hiring probability.

## Explainability and evidence

**Q29. How do you prevent fabricated evidence?**  
Every snippet must be a verbatim substring of the page text. Statuses: verified, inferred, unverified, failed_verification. A snippet that fails the check is discarded and the requirement shows 'No evidence'. A test asserts that all stored evidence exists in the resume text.

**Q30. What does 'inferred' mean?**  
Evidence that is real resume text but supports the requirement indirectly: related skills or semantic similarity, rather than a direct mention.

**Q31. How is confidence different from the score?**  
Confidence = mean(parse confidence, share of evidence verified, date certainty). It describes how much to trust the extraction, not how good the candidate is. Completeness counts 8 field checks. Both are shown separately.

**Q32. What does the explanation contain?**  
Summary, points per component (score × effective weight), why matched, why not, missing information, evidence list and a disclaimer. All are generated from structured results by templates, not by a language model.

## Evaluation

**Q33. How did you evaluate?**  
A synthetic benchmark: 35 parseable resumes in four layouts and 6 JDs, with ground truth defined at generation and reviewed by me. Metrics: skill P/R/F1, field and experience accuracy, NDCG@5, P@5, R@5, a TF-IDF baseline, a random baseline, score recomputation, a twin test and timings.

**Q34. Give your headline results.**  
Skill micro-F1 0.993, experience accuracy 1.00, NDCG@5 0.943 vs 0.932 for plain TF-IDF and 0.253 random, twin difference 0.0. I add immediately that the benchmark is synthetic and my own.

**Q35. Is hybrid better than TF-IDF?**  
Only marginally on this set (+0.012 NDCG@5, same P@5) and worse on the AI/ML JD (0.871 vs 0.884). It adds structure, evidence and explanations; I do not claim a significant accuracy gain.

**Q36. Isn't your evaluation circular?**  
Partly, yes. Ground truth comes from my generator and my labels, and I refined the ontology after seeing errors on the same set, so dev equals test. That is why I label skill metrics optimistic and call for independent annotation.

**Q37. What tuning did you do and how do you disclose it?**  
Parsing/ontology/JD fixes and correcting my own labelling errors, then title-core weighting, which moved NDCG@5 from 0.9425 to 0.9434, a change within noise. I stopped tuning to avoid overfitting and recorded the before/after in MODEL_EVALUATION.

**Q38. What is NDCG@5?**  
Normalised discounted cumulative gain over the top 5: sum of grade/log2(rank+1) divided by the best possible ordering. 1.0 is a perfect top 5. I use linear gain on author-assigned grades 0–3.

**Q39. What does P@5 = 0.8 mean?**  
On average 4 of the top 5 candidates had a relevance grade of at least 2. It is capped by how many relevant candidates exist for a JD.

**Q40. How would you evaluate it properly?**  
Collect consented real resumes, have two recruiters grade independently, report agreement (Cohen's kappa), split dev/test, compare against baselines with confidence intervals, and audit selection rates by group.

## Fairness, privacy, security

**Q41. How do you reduce bias?**  
Labelled protected-attribute lines such as 'Date of birth:', 'Gender:', 'Marital status:', 'Religion:', 'Nationality:', 'Age:' are removed before matching and storage (free-text mentions inside sentences are not removed); blind mode masks name and contacts in API output; the twin test checks identical content scores identically; overrides need a reason and are logged.

**Q42. Is your system fair?**  
I can only say it does not use explicit protected attributes and passed a synthetic twin test. Proxies such as school, location or career gaps are untested, and no statistical audit on real data exists.

**Q43. Does it auto-reject?**  
Never. Statuses are set by recruiters only, and the UI states that.

**Q44. How do you handle malicious uploads?**  
Allow-listed extensions, magic bytes, size/page limits, PDF active-content markers, DOCX macros and zip-bomb checks, random storage names, path-traversal-safe reads/deletes. Parsing is still in-process, so a parser exploit would hit the server: a documented gap.

**Q45. What about prompt injection?**  
No LLM sees resume text here. Instruction-like phrases are flagged and ignored so the control still holds if someone later feeds text to an LLM.

**Q46. How is personal data protected?**  
PII-free audit log, per-candidate deletion that removes rows and the stored file, retention purge, optional `STORE_ORIGINAL_FILES=false`. Not covered: encryption at rest, consent management, GDPR/DPDP compliance.

**Q47. How does authentication work?**  
An optional shared API key checked with constant-time comparison. It is not user authentication and is not enough for production.

**Q48. What is CSV formula injection?**  
A cell beginning with =, +, - or @ can run as a formula when opened in Excel. Exports prefix such cells with an apostrophe.

## Engineering

**Q49. Why FastAPI, SQLAlchemy and SQLite?**  
FastAPI gives typed validation and OpenAPI docs; SQLAlchemy 2 keeps the schema portable to Postgres; SQLite means zero setup on a student laptop. It was also run on PostgreSQL 16.4 (full test suite, migrations and the 50-resume flow pass); other versions and load are untested.

**Q50. How do you handle errors?**  
A central handler returns one envelope with a code and message. Validation errors are 422, domain errors use `AppError`, and unexpected exceptions become a generic 500 without internals; a test monkeypatches a failure to prove no details leak.

**Q51. How do migrations work?**  
Alembic with an initial migration generated from the models; a test checks upgrade, `alembic check` (models in sync) and downgrade.

**Q52. How did you test the frontend?**  
13 vitest tests for utilities and components (evidence highlighting, weights validation, pager, score badge), TypeScript strict mode, and a manual Playwright script that drives all pages in Chrome and reports console errors and failed requests.

**Q53. Were there flaky results?**  
Across 5 browser-script runs in my sandbox, 4 passed 21/21 and 1 failed several steps; I did not capture its first failure, so the cause is unknown (probably timing). I report it rather than hide it.

**Q54. What does the what-if page do?**  
It recomputes scores in memory for changed weights, minimum years, extra requirements or importance changes and returns rank/score deltas. It never writes to the database; a test asserts the stored run is unchanged.

**Q55. What are manual overrides?**  
A recruiter-entered score with a required reason, stored in a separate table and shown beside the machine score. The machine score and rank are never rewritten, and the action is audit-logged.

**Q56. How big is the app and what is its footprint?**  
Backend peak memory was about 307 MB for the whole benchmark on TF-IDF; the frontend bundle is 690 kB (204 kB gzip). MiniLM's footprint was not measured.

**Q57. Is it production-ready?**  
No. It lacks real-data validation, user management, parser sandboxing, TLS, CI and compliance work, and Docker, Linux/macOS, the PyTorch MiniLM runtime and load behaviour are untested (Windows, PostgreSQL 16.4 and the pure-NumPy MiniLM were run).

**Q58. What would you add first?**  
A real annotated dataset and held-out evaluation, then MiniLM evaluation, then a worker queue with sandboxed parsing and proper authentication.
