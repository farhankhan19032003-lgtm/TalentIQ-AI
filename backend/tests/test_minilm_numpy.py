"""The pure-NumPy all-MiniLM-L6-v2 runtime: tokenizer, weight reader, embeddings and the SimilarityEngine integration."""
import json
import struct

import numpy as np
import pytest

from app.core.config import settings
from app.services import minilm_numpy as mn
from app.services.minilm_numpy import MiniLMNumpy, WordPieceTokenizer, read_safetensors
from app.services.semantic_matcher import SimilarityEngine

MODEL_DIR = settings.embedding_model_dir
HAVE_MODEL = all((MODEL_DIR / n).is_file() for n in ("config.json", "vocab.txt", "model.safetensors"))
needs_model = pytest.mark.skipif(not HAVE_MODEL, reason="model files not downloaded (python scripts/fetch_minilm.py)")


@pytest.fixture(scope="module")
def model():
    return MiniLMNumpy.load(MODEL_DIR)


def cos(m, a, b):
    va, vb = m.encode([a, b])
    return float(va @ vb)


# ---- tokenizer (BERT uncased) -------------------------------------------------------------------------------------------------
@needs_model
class TestTokenizer:
    @pytest.fixture(scope="class")
    def tok(self):
        return WordPieceTokenizer(MODEL_DIR / "vocab.txt")

    def decode(self, tok, ids):
        inv = {i: t for t, i in tok.vocab.items()}
        return [inv[i] for i in ids]

    def test_special_tokens_lowercase_and_punctuation(self, tok):
        assert self.decode(tok, tok.encode("Hello, World!")) == ["[CLS]", "hello", ",", "world", "!", "[SEP]"]

    def test_wordpiece_splits_unknown_words_into_pieces(self, tok):
        pieces = self.decode(tok, tok.encode("embeddings"))[1:-1]
        assert len(pieces) >= 2 and pieces[0] in tok.vocab and all(p.startswith("##") for p in pieces[1:])
        assert "".join(p.removeprefix("##") for p in pieces) == "embeddings"

    def test_accents_are_stripped_and_unicode_normalised(self, tok):
        assert tok.encode("Résumé naïve café") == tok.encode("resume naive cafe")

    def test_cjk_characters_are_separated_and_unknown_words_become_unk(self, tok):
        ids = tok.encode("ab日本")
        assert len(ids) >= 4
        assert tok.encode("x" * 150)[1:-1] == [tok.unk], "words over 100 characters are [UNK], as in BERT"

    def test_control_characters_and_odd_whitespace_are_cleaned(self, tok):
        assert tok.encode("a\u0000b​c\t\n d") == tok.encode("ab c d") or tok.encode("a\tb") == tok.encode("a b")
        assert tok.encode("a b") == tok.encode("a b")

    def test_truncation_keeps_cls_and_sep(self, tok):
        ids = tok.encode("word " * 1000, max_len=256)
        assert len(ids) == 256 and ids[0] == tok.cls and ids[-1] == tok.sep

    def test_empty_text(self, tok):
        assert tok.encode("") == [tok.cls, tok.sep]


# ---- weight file reader --------------------------------------------------------------------------------------------------------
def test_safetensors_reader_roundtrip(tmp_path):
    a = np.arange(6, dtype="<f4").reshape(2, 3)
    b = np.array([1.5, -2.5], dtype="<f4")
    ints = np.arange(4, dtype="<i8")
    payload = a.tobytes() + b.tobytes() + ints.tobytes()
    header = {"__metadata__": {"format": "pt"},
              "a": {"dtype": "F32", "shape": [2, 3], "data_offsets": [0, 24]},
              "b": {"dtype": "F32", "shape": [2], "data_offsets": [24, 32]},
              "ids": {"dtype": "I64", "shape": [4], "data_offsets": [32, 64]}}
    h = json.dumps(header).encode()
    f = tmp_path / "t.safetensors"
    f.write_bytes(struct.pack("<Q", len(h)) + h + payload)
    out = read_safetensors(f)
    assert set(out) == {"a", "b"}, "integer tensors are skipped"
    assert np.array_equal(out["a"], a) and np.array_equal(out["b"], b) and out["a"].dtype == np.float32


def test_missing_model_files_give_an_actionable_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_minilm.py"):
        MiniLMNumpy.load(tmp_path)


# ---- embeddings ---------------------------------------------------------------------------------------------------------------
@needs_model
def test_matches_the_published_sentence_transformers_example_scores(model):
    """Scores printed in the Sentence-Transformers quickstart for all-MiniLM-L6-v2 (4 decimals)."""
    assert cos(model, "The new movie is awesome", "The new movie is so great") == pytest.approx(0.8939, abs=1e-3)
    assert cos(model, "The cat sits outside", "The cat plays in the garden") == pytest.approx(0.6788, abs=1e-3)
    assert cos(model, "I love pasta", "Do you like pizza?") == pytest.approx(0.5096, abs=1e-3)


@needs_model
def test_embeddings_are_unit_length_float32_and_384_dimensional(model):
    v = model.encode(["Built REST APIs", "x", ""])
    assert v.shape == (3, 384) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    raw = model.encode(["Built REST APIs"], normalize_embeddings=False)
    assert abs(np.linalg.norm(raw[0]) - 1.0) > 1e-3, "normalisation is optional"


@needs_model
def test_result_does_not_depend_on_batching_or_order(model):
    texts = ["Built REST APIs with FastAPI", "x", "Led a team of five engineers " * 8, "Résumé naïve café", "日本語 text"]
    solo = np.vstack([model.encode([t]) for t in texts])
    assert np.abs(solo - model.encode(texts, batch_size=2)).max() < 1e-5
    assert np.abs(solo[::-1] - model.encode(texts[::-1], batch_size=3)).max() < 1e-5
    assert model.encode("a single string").shape == (1, 384), "a bare string is accepted"


@needs_model
def test_embeddings_capture_meaning_not_just_shared_words(model):
    """The reason this runtime exists: paraphrases with no shared keywords still score high, unrelated text does not."""
    jd = "Build REST services for a payments platform"
    assert cos(model, jd, "Developed HTTP APIs for the checkout system") > 0.45
    assert cos(model, jd, "Cooked pasta for the family dinner") < 0.15
    assert cos(model, "machine learning", "predictive modeling with XGBoost") > cos(model, "machine learning", "baking bread") + 0.1
    assert cos(model, "Kubernetes", "container orchestration") > cos(model, "Kubernetes", "accounting spreadsheets")


@needs_model
def test_embeddings_beat_tfidf_on_paraphrases_with_no_shared_words(model):
    """The claim made in the README: where keyword overlap is zero, TF-IDF sees nothing and MiniLM still sees the meaning."""
    pairs = [("Build REST services for a payments platform", "Developed HTTP APIs for the checkout system"),
             ("Experience with container orchestration", "Ran production workloads on Kubernetes"),
             ("Strong communication with stakeholders", "Presented progress to clients every week")]
    tfidf = SimilarityEngine("tfidf", [])
    tfidf.prepare([a for a, _ in pairs] + [b for _, b in pairs])
    for a, b in pairs:
        lexical = float(tfidf.similarity([a], [b])[0][0])
        semantic = cos(model, a, b)
        unrelated = cos(model, a, "Cooked pasta for the family dinner")
        assert lexical < 0.05, f"no shared words, so TF-IDF should see nothing: {lexical:.2f} for {a!r}"
        assert semantic > 0.25 and semantic > lexical + 0.25, f"MiniLM should see the meaning: {semantic:.2f} for {a!r}"
        assert semantic > unrelated + 0.15, f"and rank it well above an unrelated sentence ({semantic:.2f} vs {unrelated:.2f}) for {a!r}"


@needs_model
def test_long_text_is_truncated_not_rejected(model):
    long_ = model.encode(["engineer " * 300])                  # already past 256 tokens
    huge = model.encode(["engineer " * 5000])
    assert np.abs(long_ - huge).max() < 1e-5, "everything past 256 tokens is ignored, as in sentence-transformers"
    assert np.abs(model.encode(["engineer " * 100]) - huge).max() > 1e-3, "text under the limit is not truncated"


# ---- integration with the SimilarityEngine -----------------------------------------------------------------------------------------
@needs_model
def test_engine_uses_minilm_through_the_numpy_runtime_when_sentence_transformers_is_missing(monkeypatch):
    monkeypatch.setattr(SimilarityEngine, "_model", None)
    monkeypatch.setattr(SimilarityEngine, "_runtime", None)
    monkeypatch.setattr(SimilarityEngine, "_model_failed", None)
    import builtins
    real_import = builtins.__import__

    def no_st(name, *a, **k):
        if name == "sentence_transformers":
            raise ModuleNotFoundError("No module named 'sentence_transformers'")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_st)
    e = SimilarityEngine("auto", [])
    assert e.method == "minilm" and e.fallback_reason is None and SimilarityEngine._runtime == "numpy"
    assert "pure NumPy" in e.model_name
    s = e.similarity(["Build REST services"], ["Developed HTTP APIs", "Cooked pasta"])[0]
    assert s[0] > s[1] + 0.3


def test_engine_falls_back_to_tfidf_with_a_clear_reason_when_the_model_files_are_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(SimilarityEngine, "_model", None)
    monkeypatch.setattr(SimilarityEngine, "_runtime", None)
    monkeypatch.setattr(SimilarityEngine, "_model_failed", None)
    monkeypatch.setattr(settings, "embedding_model_dir", tmp_path / "nothing-here")
    import builtins
    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda n, *a, **k: (_ for _ in ()).throw(ModuleNotFoundError(n)) if n == "sentence_transformers" else real_import(n, *a, **k))
    e = SimilarityEngine("auto", [])
    assert e.method == "tfidf" and "run: python scripts/fetch_minilm.py" in (e.fallback_reason or ""), "the instruction survives truncation"
    assert len(e.fallback_reason) <= 300, "fits the database column"


@needs_model
def test_similarities_are_plain_python_compatible_floats(monkeypatch):
    """float32 numbers cannot be stored in the JSON columns of a match result (this crashed a real matching run)."""
    import json
    monkeypatch.setattr(SimilarityEngine, "_model", None)
    monkeypatch.setattr(SimilarityEngine, "_runtime", None)
    monkeypatch.setattr(SimilarityEngine, "_model_failed", None)
    e = SimilarityEngine("minilm", [])
    assert e.method == "minilm"
    S = e.similarity(["Build REST services", "Machine learning"], ["Developed HTTP APIs", "Baking bread", "Predictive modeling"])
    assert S.dtype == np.float64
    json.dumps({"similarity": S[0][0], "row": [S[1][1], S[1][2]], "nested": {"x": float(S[0][1]), "to_score": e.to_score(S[0][0])}})   # must not raise


@needs_model
def test_a_full_matching_run_with_minilm_stores_every_result(client, loaded, monkeypatch):
    """End to end through the API with real embeddings: every sample job ranks every candidate and the results are saved."""
    monkeypatch.setattr(settings, "embedding_backend", "minilm")
    monkeypatch.setattr(SimilarityEngine, "_model", None)
    monkeypatch.setattr(SimilarityEngine, "_runtime", None)
    monkeypatch.setattr(SimilarityEngine, "_model_failed", None)
    try:
        for key, job in loaded["jobs"].items():
            r = client.post(f"/api/matching/run/{job['id']}", json={})
            assert r.status_code == 201, f"{key}: {r.status_code} {r.text}"
            assert r.json()["similarity_method"] == "minilm" and "NumPy" in r.json()["model_name"]
            items = client.get(f"/api/matching/results/{job['id']}?page_size=100").json()["items"]
            assert len(items) >= 30 and all(0 <= i["overall"] <= 100 for i in items), key
            assert client.get(f"/api/matching/candidate/{items[0]['candidate_id']}?job_id={job['id']}").status_code == 200, key
    finally:
        for job in loaded["jobs"].values():                      # leave the shared session database with default (TF-IDF) runs
            monkeypatch.setattr(settings, "embedding_backend", "tfidf")
            client.post(f"/api/matching/run/{job['id']}", json={})


def test_default_backend_is_auto(monkeypatch):
    monkeypatch.delenv("EMBEDDING_BACKEND", raising=False)
    from app.core.config import load_settings
    assert load_settings().embedding_backend == "auto"
