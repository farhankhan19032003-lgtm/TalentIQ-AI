# Technical audit & submission gate

Date: 2026-11-15 · Environment: Linux sandbox, Python 3.11+, Node 22, headless Chrome (Playwright) · Similarity backend: **TF-IDF fallback** (MiniLM not downloadable here).
Everything below was actually run in that environment. Anything not run is listed under "Not verified".

> **Update 2026-11-16 (Windows, Python 3.15).** MiniLM sentence embeddings now run (pure-NumPy runtime, see `docs/ALGORITHM.md`) and the benchmark was re-run with them: mean NDCG@5 **0.9452 vs 0.9434** for TF-IDF (plain baseline 0.9316). That is a tie within noise on this synthetic set, not proof that embeddings rank better here; the advantage that is demonstrated is on paraphrases without shared words (TF-IDF 0.00, MiniLM 0.31–0.57). Rows 6 and 23 and the last checklist item below are superseded by this; the rest of this report is the original 2026-11-15 audit and was not redone. A JD in **PDF** form is now accepted (the UI always offered it, the backend used to answer 400), and the ranking table shows the **names** of matched skills. See `docs/TESTING.md` for the clean-database browser run.

## Test report
| # | Test case | Expected | Actual | Result | Evidence | Remaining issue |
|---|---|---|---|---|---|---|
| 1 | PDF upload (single & two-column layouts) | Parsed with name, sections, skills | 35 synthetic resumes parsed; layouts pdf_single, pdf_two_col | PASS | `test_document_parser`, eval parse 34/34 | Synthetic only |
| 2 | DOCX upload (headings & layout tables) | Parsed | docx_headings and docx_table layouts parsed | PASS | `test_batch_of_10plus_resumes_pdf_and_docx` | No text boxes, no page numbers |
| 3 | Batch of 10+ | All processed, bad files isolated | 41 files: 35 parsed, 2 failed, 1 duplicate, 3 rejected; ~30 ms/resume | PASS | `test_api`, UI run | — |
| 4 | Different JDs | Different rankings, domain experts first | 6 JDs; Sameer Gupta #1 for DevOps, Dev Malhotra #1 for Data Analyst, etc. | PASS | `test_domain_expert_ranks_first` | Author-defined expectations |
| 5 | Skill extraction | High P/R, no known traps | micro-F1 0.993 (1 FP, 3 FN of 275) | PASS (optimistic) | eval `final` | Tuned on same set; bare `R`/`Go`, inflections missed |
| 6 | Semantic similarity | Bounded, symmetric, pool-independent | cos ∈ [0,1]; scores unchanged by other candidates | PASS (TF-IDF) | `test_semantic_matching` | **MiniLM never run** (1 test skipped) |
| 7 | Independent score verification | Stored = recomputed | 210/210 match; formula test | PASS | eval, `test_overall_equals_documented_formula` | Verifies arithmetic, not weight validity |
| 8 | Rankings | Descending, ranks 1..n, deterministic, reproducible | yes; two runs identical | PASS | `test_ranking_sorted…`, `test_two_runs_are_reproducible` | 51 % of ranks move under ±10 pp weight change |
| 9 | Candidate pages | Breakdown, evidence, explanation | rendered and reviewed in screenshot | PASS | UI run, `test_candidate_detail…` | Only 2 screens visually reviewed by me |
| 10 | Missing / ambiguous info | Not treated as mismatch | `unverified` + score range | PASS | `test_missing_sections_are_unverified…` | — |
| 11 | Corrupted / encrypted / fake files | Classified, batch continues | corrupt, password_protected, signature_mismatch, unsupported_type | PASS | `test_one_bad_file_never_fails_batch` | — |
| 12 | Duplicates | Detected | file-hash duplicate; same-email flagged | PASS | tests | Different-format duplicate of same person only flagged by email |
| 13 | CSV / Excel / PDF exports | Valid files, injection-safe | CSV rows = candidates, XLSX sheets OK, PDFs open; browser downloads worked | PASS | `test_csv/excel/pdf_export`, UI run | Report layout only checked via text extraction |
| 14 | DB persistence | Runs, components, evidence stored | verified by direct DB queries | PASS | `test_database_persistence` | SQLite, and the same suite on Postgres 16.4 (2026-11-16) |
| 15 | Frontend ↔ backend integration | Full flow works | 21/21 browser steps passed on the final two consecutive runs | PASS | `scripts/e2e_browser_check.py` (manual tool) | 1 of 5 runs failed several steps; first failure not captured; unexplained, likely timing |
| 16 | Automated tests | All pass | backend 142 passed / 1 skipped; frontend 13 passed; tsc and build clean | PASS | commands in TESTING.md | — |
| 17 | Browser console errors | None | 0 errors/warnings on final runs (after fixing router future-flag warnings, a handled 404 and a missing favicon) | PASS | Playwright console capture | Chrome only |
| 18 | Backend errors | None | 0 tracebacks / 500s in logs; one intended 409 earlier in a flaky run | PASS | uvicorn log | — |
| 19 | Security / privacy | Controls work | see SECURITY.md; audit log has no PII; deletion removes files | PASS (for scope) | `test_security`, `test_api` | No sandbox/AV, no roles, no TLS |
| 20 | Fairness | Twin resumes equal | Δ = 0.0 on 6 JDs | PASS | eval, `test_twin_resumes…` | Synthetic twins only; proxy features untested |
| 21 | Alembic | upgrade/downgrade, in sync with models | pass | PASS | `test_migrations` | also run by hand on Postgres 16.4: upgrade, check, downgrade, upgrade |
| 22 | Docker / Render / Vercel | Builds & runs | **not run** | NOT VERIFIED | — | Files provided only |
| 23 | MiniLM embeddings | Works, better than TF-IDF | **run on 2026-11-16** (pure NumPy): works; NDCG@5 0.945 vs 0.943 | WORKS, NOT SHOWN BETTER on this set | `test_minilm_numpy` | see update note above |
| 24 | Windows execution | Works | **not run** (Linux only) | NOT VERIFIED | — | Commands written for PowerShell but untested |

## Issues found and fixed during the audit
| Severity | Issue | Fix |
|---|---|---|
| High | Format sensitivity: twin resumes differed by 0.8 points (dates leaked into semantic text) | `clean_for_similarity`; Δ = 0 |
| High | Two-column PDFs lost employment/education (centre header misclassified) | rewrote reading-order logic |
| High | Over-broad skill matches ("Excel at", "Spring" in "Spring Boot", degree names as skills) | negation, list-only for ambiguous names, education lines excluded |
| Medium | Project score ≈ 0 for most candidates | doc + responsibility similarity, bonus that can only add |
| Medium | Title skills not weighted | core ×2 (NDCG 0.9425 → 0.9434; disclosed, tiny) |
| Low | Benchmark ground-truth mistakes (my labelling errors) | corrected; documented in MODEL_EVALUATION |
| Low | Console warnings / favicon 404 / avoidable 404 | fixed |
| Low | Demo runs wrote into default upload dir (my wrong env var name) | cleaned; `SAMPLE_DATA_DIR` added |

## Realistic marks estimate (my own estimate — not an examiner's)
| Criterion | Max | Estimate | Reasoning |
|---|---|---|---|
| Functional | 25 | 21 | Complete flow works end-to-end in a real browser; deductions for untested Docker/Windows and no multi-user model |
| Parsing | 15 | 10 | Good and tested on 4 synthetic layouts + failure cases; **no real resumes**; no images/text boxes |
| Matching | 25 | 17 | Sound, verified arithmetic, evidence-grounded; but tiny margin over baseline, MiniLM unevaluated, weights unvalidated |
| Explanation | 15 | 12 | Verbatim evidence, per-point breakdown, missing-info handling; no counterfactual per-candidate beyond what-if |
| UI/UX | 10 | 7 | Works and is clean; Chrome only, no accessibility audit, limited visual review |
| Code & docs | 10 | 8 | 156 automated tests (143 backend + 13 frontend), docs, migrations; some long functions, bundle size |
| **Total** | **100** | **≈ 75** | No credit given for anything under "Not verified" |

## GitHub checklist
- [ ] Review `git status`: no `.db`, `node_modules`, `dist`, uploads, `.env` (see `.gitignore`)
- [ ] Add a LICENSE of your choice
- [ ] Repo description + topics (fastapi, react, nlp, recruitment, explainable-ai)
- [ ] Screenshots: capture your own from a live run (none are shipped; none were fabricated)
- [ ] Run the PowerShell quick start on your Windows laptop and fix anything that differs
- [x] Run MiniLM and re-run `python eval\run_evaluation.py --backend minilm --tag minilm`; numbers recorded honestly in `docs/TESTING.md` (done 2026-11-16)
- [ ] Tag release `v2.0.0`; keep README "Known limitations" intact
- [ ] Do NOT claim production readiness
