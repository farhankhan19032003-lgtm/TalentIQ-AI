# Matching algorithm (v2.0.0)

## Final score
```
Overall = Σ  w_eff(c) · score(c)         c ∈ {technical, semantic, experience, education, project/domain}
w_eff   = w(c) / Σ w(active components)   (components the JD does not require are dropped)
default w = 0.40, 0.25, 0.20, 0.10, 0.05
```
Each component score is 0–100. `score_low = Overall`; `score_high` = Overall if every *unverified* component were scored 100. The UI shows `score_low–score_high` only when they differ.

## A. Technical skills (40 %)
For each job requirement `r` with importance weight `m(r)` (must = 1.0, preferred = 0.5, ignored = 0; skills named in the **job title** are core and ×2):

| Match type | Condition | Credit |
|---|---|---|
| exact / synonym with context | skill (or alias) appears in experience/projects/summary text | 1.00 |
| listed only | appears only in a skills list | 0.85 |
| partial | candidate has a directional *related* skill (e.g. XGBoost → Machine Learning) | 0.35 |
| semantic | requirement query is similar to a resume line above the method's evidence threshold | 0.10–0.25 (linear in similarity) |
| none | no evidence | 0 |

`Technical = 100 · Σ m(r)·credit(r) / Σ m(r)`. "X or Y" requirements take the best credit among the alternatives. Ambiguous names (C, Go, R, Swift, Lambda, Spring) only match as exact list items; case-sensitive names (Excel, Oracle, IAM) require exact case; "Excel at …" is not Excel.

## B. Semantic relevance (25 %)
`cos(u, v) = u·v / (‖u‖‖v‖)` between vector representations of text.
- Document level: JD narrative vs candidate narrative (summary + experience; **disjoint from the skills list** to avoid double counting).
- Responsibility level: each JD responsibility vs its best-matching resume line; mean of best similarities.
- Raw cosine → 0–100 by linear calibration per method (`minilm`: 0.20→0, 0.65→100; `tfidf`: 0.02→0, 0.40→100). These ranges are **documented heuristics**, not learned.
- Score = 0.5·document + 0.5·responsibility (document only if the JD lists no responsibilities).
- Backend (`EMBEDDING_BACKEND`, default `auto`): **all-MiniLM-L6-v2 sentence embeddings** (384-dimensional, mean pooling, L2-normalised, max 256 tokens; lazy singleton, SHA-1 embedding cache). They are computed by `sentence-transformers` when installed, otherwise by `app/services/minilm_numpy.py`, a pure-NumPy implementation of the same network that loads the same published weights (`python scripts/fetch_minilm.py`, hash-verified) and needs no torch. If the model files are missing the engine falls back to TF-IDF (1–2-gram, sublinear tf) fitted on JD + ontology only. The run records which backend was used, which runtime ran it ("pure NumPy inference" is part of the stored model name) and, for a fallback, why.
- Why embeddings and not only keywords: TF-IDF only sees shared words. "Build REST services for a payments platform" vs "Developed HTTP APIs for the checkout system" has no word in common, so TF-IDF gives 0.00 while MiniLM gives 0.57 (unrelated text: about 0.0 to 0.1). The skill-level credit (synonyms, related skills, 0.10–0.25 for a semantic-only match) and the semantic component both use this similarity.

## C. Experience (20 %)
- Employment periods become sets of calendar months; full-time/contract are unioned (no double counting), part-time and internships count 50 % of months not already covered. Year-only dates assume Jul start / Jun end and are flagged *uncertain*. Employment gaps are shown but never penalised.
- A role is relevant if it mentions ≥ 2 JD skills, or ≥ 1 skill plus a title-token match.
- `score = min(1, relevant_years / min_years)`; if a preferred number of years exists above the minimum: `0.7·that + 0.3·min(1, relevant_years / preferred)`. No dated employment → `unverified`.

## D. Education (10 %)
Levels: diploma < bachelor < master < doctorate. `100` if candidate level ≥ required, else `100·cand/required`; capped at 85 if a preferred higher level exists and is not met. Not required by the JD → component dropped. Missing education → `unverified`.

## E. Projects & domain (5 %)
Base = mean of document-level and responsibility-level similarity against project text; plus a bonus `(100 − base)·0.5·(domain hits / domains)` that can only **add**. No projects section → `unverified`.

## Confidence and completeness (kept separate from the score)
- *Confidence* = mean(parse confidence, share of evidence snippets verified, date certainty).
- *Completeness* = share of 8 field checks present (name, contact, summary, employment, education, skills, projects, dates).
- *Needs review* flag: confidence < 60, completeness < 60, or score range > 15.

## Ranking & stability
Sort by overall desc, technical desc, candidate id asc (deterministic). Sensitivity re-ranks under ±10 percentage-point changes of each weight (renormalised); a rank is "stable" when its range across scenarios ≤ 1.

## What the score is not
It is a similarity-and-evidence signal, **not** a probability of being hired or of job performance. Weights, thresholds and calibration ranges are hand-set heuristics that have not been validated on real hiring outcomes.
