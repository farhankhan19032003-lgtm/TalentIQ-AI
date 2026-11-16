"""all-MiniLM-L6-v2 sentence embeddings in pure NumPy.

Same published weights and the same recipe as sentence-transformers (BERT uncased WordPiece, 6 transformer layers, mean pooling,
L2 normalisation, max 256 tokens), but without torch. It exists because torch/ONNX cannot always be installed (for example on
locked-down machines or brand-new Python versions). Speed is fine for resume matching: a few hundred short sentences take seconds
and every embedding is cached by the caller.

The model files are fetched once with `python scripts/fetch_minilm.py` (hash-verified) into backend/storage/models/all-MiniLM-L6-v2.
"""
from __future__ import annotations

import json
import math
import struct
import unicodedata
from pathlib import Path

import numpy as np
from scipy.special import erf

MAX_SEQ_LENGTH = 256          # sentence-transformers' setting for all-MiniLM-L6-v2 (the BERT limit is 512)


# ---------------------------------------------------------------------------------------------------- tokenizer
def _is_whitespace(ch: str) -> bool:
    return ch in (" ", "\t", "\n", "\r") or unicodedata.category(ch) == "Zs"


def _is_control(ch: str) -> bool:
    return ch not in ("\t", "\n", "\r") and unicodedata.category(ch) in ("Cc", "Cf")


def _is_punctuation(ch: str) -> bool:
    cp = ord(ch)
    return 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126 or unicodedata.category(ch).startswith("P")


def _is_cjk(cp: int) -> bool:
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF or 0x2A700 <= cp <= 0x2B73F or
            0x2B740 <= cp <= 0x2B81F or 0x2B820 <= cp <= 0x2CEAF or 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F)


class WordPieceTokenizer:
    """BERT's BasicTokenizer (clean, CJK spacing, lower-case, strip accents, split punctuation) followed by greedy WordPiece."""

    def __init__(self, vocab_path: Path, max_chars_per_word: int = 100):
        self.vocab: dict[str, int] = {}
        with open(vocab_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                self.vocab[line.rstrip("\n")] = i
        self.unk, self.cls, self.sep = self.vocab["[UNK]"], self.vocab["[CLS]"], self.vocab["[SEP]"]
        self.max_chars = max_chars_per_word

    @staticmethod
    def _basic_tokens(text: str) -> list[str]:
        cleaned = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or _is_control(ch):
                continue
            cleaned.append(" " if _is_whitespace(ch) else ch)
        spaced = []
        for ch in "".join(cleaned):
            spaced.append(f" {ch} " if _is_cjk(ord(ch)) else ch)
        out: list[str] = []
        for token in "".join(spaced).split():
            token = unicodedata.normalize("NFD", token.lower())
            token = "".join(c for c in token if unicodedata.category(c) != "Mn")
            piece: list[str] = []
            for ch in token:
                if _is_punctuation(ch):
                    if piece:
                        out.append("".join(piece))
                        piece = []
                    out.append(ch)
                else:
                    piece.append(ch)
            if piece:
                out.append("".join(piece))
        return out

    def _wordpiece(self, token: str) -> list[int]:
        if len(token) > self.max_chars:
            return [self.unk]
        ids, start = [], 0
        while start < len(token):
            end, found = len(token), None
            while start < end:
                sub = token[start:end]
                if start > 0:
                    sub = "##" + sub
                if sub in self.vocab:
                    found = self.vocab[sub]
                    break
                end -= 1
            if found is None:
                return [self.unk]                     # one unknown piece makes the whole word [UNK], as in BERT
            ids.append(found)
            start = end
        return ids

    def encode(self, text: str, max_len: int = MAX_SEQ_LENGTH) -> list[int]:
        body: list[int] = []
        for tok in self._basic_tokens(text):
            body.extend(self._wordpiece(tok))
        return [self.cls, *body[: max_len - 2], self.sep]


# ---------------------------------------------------------------------------------------------------- weights
def read_safetensors(path: Path) -> dict[str, np.ndarray]:
    """Minimal reader for the safetensors format (8-byte header length, JSON header, raw little-endian tensors)."""
    mm = np.memmap(path, dtype=np.uint8, mode="r")
    n = struct.unpack("<Q", bytes(mm[:8]))[0]
    header = json.loads(bytes(mm[8:8 + n]))
    header.pop("__metadata__", None)
    base = 8 + n
    out: dict[str, np.ndarray] = {}
    for name, info in header.items():
        if info["dtype"] != "F32":
            continue                                   # position_ids etc. are integers and not needed
        b, e = info["data_offsets"]
        out[name] = np.frombuffer(mm, dtype="<f4", count=(e - b) // 4, offset=base + b).reshape(info["shape"]).astype(np.float32)
    return out


def _layer_norm(x: np.ndarray, w: np.ndarray, b: np.ndarray, eps: float) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps) * w + b


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------------------------------- model
class MiniLMNumpy:
    """Drop-in for `SentenceTransformer.encode` (same signature subset)."""

    def __init__(self, folder: Path):
        cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        self.hidden, self.heads, self.n_layers = cfg["hidden_size"], cfg["num_attention_heads"], cfg["num_hidden_layers"]
        self.eps = float(cfg["layer_norm_eps"])
        self.tokenizer = WordPieceTokenizer(folder / "vocab.txt")
        w = read_safetensors(folder / "model.safetensors")
        self.word, self.pos, self.type0 = w["embeddings.word_embeddings.weight"], w["embeddings.position_embeddings.weight"], w["embeddings.token_type_embeddings.weight"][0]
        self.emb_ln = (w["embeddings.LayerNorm.weight"], w["embeddings.LayerNorm.bias"])
        self.layers = []
        for i in range(self.n_layers):
            p = f"encoder.layer.{i}."
            lin = lambda name: (np.ascontiguousarray(w[p + name + ".weight"].T), w[p + name + ".bias"])   # stored [out, in] -> x @ W.T
            self.layers.append({
                "q": lin("attention.self.query"), "k": lin("attention.self.key"), "v": lin("attention.self.value"),
                "o": lin("attention.output.dense"), "ln1": (w[p + "attention.output.LayerNorm.weight"], w[p + "attention.output.LayerNorm.bias"]),
                "i": lin("intermediate.dense"), "f": lin("output.dense"), "ln2": (w[p + "output.LayerNorm.weight"], w[p + "output.LayerNorm.bias"]),
            })

    @classmethod
    def load(cls, folder) -> "MiniLMNumpy":
        folder = Path(folder)
        missing = [n for n in ("config.json", "vocab.txt", "model.safetensors") if not (folder / n).is_file()]
        if missing:
            # the instruction comes first: this text is stored (truncated) as the reason for a TF-IDF fallback, and the path is long
            raise FileNotFoundError(f"MiniLM model files not found - run: python scripts/fetch_minilm.py (missing {', '.join(missing)} in {folder})")
        return cls(folder)

    # -- forward pass -------------------------------------------------------------------------------
    def _forward(self, ids: np.ndarray, mask: np.ndarray) -> np.ndarray:
        B, L = ids.shape
        H, D = self.heads, self.hidden // self.heads
        x = self.word[ids] + self.pos[:L][None, :, :] + self.type0
        x = _layer_norm(x, *self.emb_ln, self.eps)
        bias = (1.0 - mask[:, None, None, :]) * np.float32(-1e9)             # padding positions get ~0 attention
        for ly in self.layers:
            def heads(t):
                return t.reshape(B, L, H, D).transpose(0, 2, 1, 3)
            q = heads(x @ ly["q"][0] + ly["q"][1])
            k = heads(x @ ly["k"][0] + ly["k"][1])
            v = heads(x @ ly["v"][0] + ly["v"][1])
            scores = q @ k.transpose(0, 1, 3, 2) / math.sqrt(D) + bias
            scores -= scores.max(axis=-1, keepdims=True)
            attn = np.exp(scores)
            attn /= attn.sum(axis=-1, keepdims=True)
            ctx = (attn @ v).transpose(0, 2, 1, 3).reshape(B, L, self.hidden)
            x = _layer_norm(x + ctx @ ly["o"][0] + ly["o"][1], *ly["ln1"], self.eps)
            x = _layer_norm(x + _gelu(x @ ly["i"][0] + ly["i"][1]) @ ly["f"][0] + ly["f"][1], *ly["ln2"], self.eps)
        m = mask[:, :, None]
        return (x * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)          # mean pooling over real tokens

    def encode(self, texts, batch_size: int = 16, normalize_embeddings: bool = True, show_progress_bar: bool = False, **_ignored) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        tokens = [self.tokenizer.encode(t) for t in texts]
        order = sorted(range(len(texts)), key=lambda i: len(tokens[i]))           # similar lengths together = less padding
        out = np.zeros((len(texts), self.hidden), dtype=np.float32)
        for s in range(0, len(order), batch_size):
            idx = order[s:s + batch_size]
            L = max(len(tokens[i]) for i in idx)
            ids = np.zeros((len(idx), L), dtype=np.int64)
            mask = np.zeros((len(idx), L), dtype=np.float32)
            for r, i in enumerate(idx):
                ids[r, :len(tokens[i])] = tokens[i]
                mask[r, :len(tokens[i])] = 1.0
            out[idx] = self._forward(ids, mask)
        if normalize_embeddings:
            out /= np.clip(np.linalg.norm(out, axis=1, keepdims=True), 1e-12, None)
        return out
