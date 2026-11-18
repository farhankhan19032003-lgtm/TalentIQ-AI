"""Similarity engine. Primary: the all-MiniLM-L6-v2 sentence-embedding model (loaded lazily, once, cached), run either by
sentence-transformers (if installed) or by the bundled pure-NumPy implementation (same weights, no torch needed).
Fallback: TF-IDF (fit only on the job + the skill ontology so scores never depend on other candidates)."""
from __future__ import annotations

import hashlib
import logging
import threading
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from ..core.config import CALIBRATION, settings  # noqa: F401  (CALIBRATION re-exported for the settings endpoint)

log = logging.getLogger("talentiq.semantic")


class SimilarityEngine:
    _model = None
    _runtime: str | None = None            # "sentence-transformers" or "numpy"
    _model_failed: str | None = None
    _lock = threading.Lock()
    _cache: dict[str, np.ndarray] = {}

    def __init__(self, backend: str | None = None, ontology_texts: list[str] | None = None):
        self.requested = (backend or settings.embedding_backend).lower()
        self.ontology_texts = ontology_texts or []
        self._tfidf: TfidfVectorizer | None = None
        self.fallback_reason: str | None = None
        self.method = self._resolve()

    # -- backend selection ---------------------------------------------------------
    def _resolve(self) -> str:
        if self.requested == "tfidf":
            return "tfidf"
        if self._load_model():
            return "minilm"
        self.fallback_reason = SimilarityEngine._model_failed
        if self.requested == "minilm":
            log.warning("MiniLM requested but unavailable (%s); using TF-IDF fallback", self.fallback_reason)
        return "tfidf"

    @classmethod
    def _load_model(cls) -> bool:
        if cls._model is not None:
            return True
        if cls._model_failed:
            return False
        with cls._lock:
            if cls._model is not None:
                return True
            t0 = time.time()
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer(settings.embedding_model, device="cpu")
                cls._runtime = "sentence-transformers"
                log.info("Loaded %s with sentence-transformers in %.1fs", settings.embedding_model, time.time() - t0)
                return True
            except Exception as first:  # not installed / blocked / no network: try the NumPy runtime with the local model files
                try:
                    from .minilm_numpy import MiniLMNumpy
                    cls._model = MiniLMNumpy.load(settings.embedding_model_dir)
                    cls._runtime = "numpy"
                    log.info("Loaded %s with the NumPy runtime in %.1fs (sentence-transformers unavailable: %s)", settings.embedding_model, time.time() - t0, type(first).__name__)
                    return True
                except Exception as second:
                    cls._model_failed = f"{str(second)[:200]} (sentence-transformers: {type(first).__name__})"[:280]
                    return False

    @property
    def model_name(self) -> str:
        if self.method != "minilm":
            return "tfidf(word 1-2gram, sublinear tf)"
        return settings.embedding_model + (" (pure NumPy inference)" if SimilarityEngine._runtime == "numpy" else "")

    @property
    def calibration(self) -> dict:
        return CALIBRATION[self.method]

    # -- fitting (TF-IDF only) -------------------------------------------------------
    def prepare(self, job_texts: list[str]):
        if self.method != "tfidf":
            return
        self._tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english",
                                      token_pattern=r"(?u)\b\w[\w+#]*\b", norm="l2")
        self._tfidf.fit(list(job_texts) + self.ontology_texts)

    # -- encode / similarity ---------------------------------------------------------
    def _encode_minilm(self, texts: list[str]) -> np.ndarray:
        keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if k not in self._cache]
        if missing:
            uniq = {k: t for k, t in missing}
            vecs = self._model.encode(list(uniq.values()), batch_size=16, normalize_embeddings=True, show_progress_bar=False)
            for k, v in zip(uniq.keys(), vecs):
                if len(self._cache) > 20000:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[k] = np.asarray(v, dtype=np.float32)
        return np.vstack([self._cache[k] for k in keys])

    def similarity(self, a: list[str], b: list[str]) -> np.ndarray:
        """Cosine similarity matrix (len(a) x len(b)), values in [0, 1] for TF-IDF and ~[-1, 1] for MiniLM."""
        if not a or not b:
            return np.zeros((len(a), len(b)))
        if self.method == "minilm":
            # float64, not float32: these numbers end up inside the JSON columns of a match result, and json cannot store numpy.float32
            return (self._encode_minilm(a) @ self._encode_minilm(b).T).astype(np.float64)
        if self._tfidf is None:
            self.prepare([])
        A, B = self._tfidf.transform(a), self._tfidf.transform(b)
        return (A @ B.T).toarray()

    def to_score(self, cos: float, level: str = "doc") -> float:
        """Linear calibration of a raw cosine to a 0..100 component score (documented heuristic).
        `level` is "doc" (narrative vs narrative) or "resp" (one JD responsibility vs its best resume line)."""
        lo, hi = self.calibration[level]
        return float(max(0.0, min(100.0, (cos - lo) / (hi - lo) * 100)))
