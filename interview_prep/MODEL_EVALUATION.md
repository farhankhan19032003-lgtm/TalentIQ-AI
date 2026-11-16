# Model evaluation

Source of numbers: `backend/eval/results/evaluation_20261115_final.json` (also `latest.json`), produced by `python eval/run_evaluation.py --backend tfidf --tag final`.

## Method
- 34 synthetic profiles + 1 scanned-image resume (OCR) = 35 parseable resumes, 4 layouts, 6 job descriptions. Ground truth (skills, employment dates, relevance grade 0–3 per candidate per JD) is defined **by construction** when the files are generated, then reviewed by the author.
- Metrics: skill precision/recall/F1 (micro/macro), name/email accuracy, experience accuracy (±0.1 y), JD extraction F1, NDCG@5 (linear gain), P@5, R@5, TF-IDF-only baseline, random baseline (mean over shuffles), score recomputation, twin-resume test, timing.

## Results (TF-IDF backend)
| Metric | Value |
|---|---|
| Parse success (parseable) / failure classification | 34/34 · 6/6 |
| Skill micro P / R / F1 | 0.996 / 0.989 / 0.993 |
| Name / email accuracy | 1.00 / 0.97 |
| Experience accuracy | 1.00 (n = 35) |
| JD skill F1 / importance / experience-req / education-req | 0.978 / 0.986 / 1.00 / 1.00 |
| NDCG@5: hybrid / TF-IDF baseline / random | 0.9434 / 0.9316 / 0.2528 |
| P@5: hybrid / baseline | 0.80 / 0.80 |
| Score recomputation | 210/210 |
| Twin resumes max Δ | 0.0 |

Per-JD NDCG@5 (hybrid / baseline): AI-ML 0.871/0.884 · Python backend 0.956/0.956 · Data analyst 0.968/0.968 · Java backend 0.936/0.878 · DevOps 1.000/1.000 · Full-stack 0.929/0.903.

## Tuning disclosure (before/after)
- Baseline run → fixes for parsing, ontology, JD analysis and ground-truth errors (several labels were *my* mistakes) → final. Those fixes improved skill F1 and parsing; the ontology was edited after looking at errors **on the same set**, so skill metrics are optimistic.
- Title-core weighting (×2) changed mean NDCG@5 from 0.9425 to 0.9434. A 0.0009 change is noise on 6 JDs; it was kept for being logically sensible, not because the data proves it.
- Tuning was stopped deliberately to avoid fitting the benchmark.

## How to read this
- The hybrid beats the plain TF-IDF baseline by 0.012 NDCG@5 and loses on one JD. **Do not claim it is significantly better.** The honest claim: it is at least as good on this set while adding structure, evidence and explanations that a bare similarity score cannot give.
- P@5 is limited by how many relevant candidates exist (some JDs have only 3 graded ≥ 2).
- **Not evaluated:** MiniLM embeddings, real resumes, inter-annotator agreement, calibration of scores to outcomes.
