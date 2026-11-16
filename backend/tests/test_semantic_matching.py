import importlib.util

import numpy as np
import pytest

from app.services.semantic_matcher import SimilarityEngine
from app.services.pipeline import ontology, ontology_texts

TEXTS = ["Machine learning engineer training classification models with scikit-learn", "Predictive modelling and regression with XGBoost",
         "Pastry chef baking sourdough bread", "Accountant preparing tax filings"]


def eng():
    e = SimilarityEngine("tfidf", ontology_texts())
    e.prepare(["machine learning engineer training models scikit-learn classification regression XGBoost"])
    return e


def test_cosine_identity_and_range():
    e = eng()
    M = e.similarity(TEXTS, TEXTS)
    assert np.allclose(np.diag(M)[:2], 1.0, atol=1e-6)      # in-vocabulary texts are identical to themselves
    assert np.diag(M)[2] == 0.0                               # out-of-vocabulary text has no representation (documented limitation)
    assert (M >= -1e-9).all() and (M <= 1 + 1e-9).all()
    assert np.allclose(M, M.T, atol=1e-9)


def test_related_text_scores_higher_than_unrelated():
    e = eng()
    s = e.similarity(["machine learning models scikit-learn"], TEXTS)[0]
    assert s[0] > s[2] and s[0] > s[3]
    # ontology expansion: 'Machine Learning' query also carries related terms (XGBoost, regression, ...), so related evidence scores > 0
    s2 = e.similarity([ontology.semantic_query("Machine Learning")], TEXTS)[0]
    assert s2[1] > s2[2] and s2[1] > s2[3]


def test_cosine_math_matches_manual_computation():
    e = eng()
    a, b = TEXTS[0], TEXTS[1]
    A, B = e._tfidf.transform([a]).toarray()[0], e._tfidf.transform([b]).toarray()[0]
    manual = float(A @ B / (np.linalg.norm(A) * np.linalg.norm(B)))
    assert e.similarity([a], [b])[0][0] == pytest.approx(manual, abs=1e-9)


def test_empty_inputs():
    assert eng().similarity([], ["x"]).shape == (0, 1)


def test_score_calibration_bounds():
    e = eng()
    assert e.to_score(-1) == 0.0 and e.to_score(2) == 100.0 and 0 < e.to_score(0.2) < 100


def test_deterministic_and_independent_of_other_texts():
    e1, e2 = eng(), eng()
    assert e1.similarity([TEXTS[0]], [TEXTS[1]])[0][0] == e2.similarity([TEXTS[0]], [TEXTS[1], TEXTS[2]])[0][0]


def test_model_load_failure_falls_back_to_tfidf(monkeypatch):
    monkeypatch.setattr(SimilarityEngine, "_model", None)
    monkeypatch.setattr(SimilarityEngine, "_model_failed", "forced for test")
    e = SimilarityEngine("auto", ontology_texts())
    assert e.method == "tfidf" and e.fallback_reason == "forced for test"


def test_minilm_semantic_similarity_if_available():
    """Runs with sentence-transformers or with the bundled NumPy runtime (needs the model files from scripts/fetch_minilm.py)."""
    e = SimilarityEngine("minilm", [])
    if e.method != "minilm":
        pytest.skip("MiniLM weights could not be loaded (run python scripts/fetch_minilm.py)")
    s = e.similarity(["machine learning"], ["predictive modeling with XGBoost", "baking bread"])[0]
    assert s[0] > s[1]
