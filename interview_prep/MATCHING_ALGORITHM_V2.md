# Matching algorithm v2.0.0 — interview version

Authoritative description: `../docs/ALGORITHM.md`.

**Formula:** `Overall = 0.40·Technical + 0.25·Semantic + 0.20·Experience + 0.10·Education + 0.05·Project`, with absent components dropped and weights renormalised.

**What v2 changed relative to a naive keyword/embedding matcher (all implemented):**
1. Match types with different credit (exact 1.0, listed-only 0.85, related 0.35, semantic 0.10–0.25, none 0).
2. Directional ontology: "XGBoost" supports "Machine Learning" as *partial* credit, never as an exact claim.
3. "X or Y" requirements take the best alternative.
4. Title skills are core (×2).
5. Missing evidence is `unverified` and widens a score range instead of being scored as a mismatch.
6. Evidence snippets must be verbatim resume substrings or they are dropped.
7. Semantic text excludes dates/separators (fixed a measurable format-sensitivity bug) and is disjoint from the skills list (no double counting).
8. TF-IDF is fitted on the JD + ontology only, so scores do not depend on who else was uploaded.
9. Deterministic tie-breaks and a rank-sensitivity analysis.

**Honest caveat:** weights, credits and calibration ranges are hand-set. They were never fitted to real hiring outcomes.
