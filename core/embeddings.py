"""Embedding backends.

* SentenceTransformerEmbedder – real semantic vectors (all-MiniLM-L6-v2 by default).
* HashingEmbedder – dependency-free offline fallback (word + character n-gram hashing). It gives useful
  lexical/subword similarity, so the app keeps working without any model download, but it is NOT
  a semantic model; `is_semantic` is False and downstream code becomes more conservative.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from functools import lru_cache

import numpy as np

from .config import EMBEDDING_BACKEND, EMBEDDING_MODEL

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"[a-z0-9+#.]+")


class HashingEmbedder:
    name = "hashing-ngram (offline fallback)"
    is_semantic = False

    def __init__(self, dim: int = 768):
        self.dim = dim

    @staticmethod
    def _h(s: str) -> int:
        return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "little")

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = _TOKEN.findall(text.lower())
        for t in toks:
            v[self._h("w:" + t) % self.dim] += 2.0
            padded = f"<{t}>"
            for n in (3, 4):
                for i in range(len(padded) - n + 1):
                    v[self._h("c:" + padded[i:i + n]) % self.dim] += 0.5
        for a, b in zip(toks, toks[1:]):
            v[self._h(f"b:{a}_{b}") % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)


class SentenceTransformerEmbedder:
    is_semantic = True

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import, lazy

        self.model = SentenceTransformer(model_name)
        self.name = model_name

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), np.float32)
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


class CachedEmbedder:
    """Wraps a backend with a small in-memory cache (skill names / queries repeat a lot)."""

    def __init__(self, inner):
        self.inner = inner
        self._cache: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def is_semantic(self) -> bool:
        return self.inner.is_semantic

    def encode(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
            if missing:
                vecs = self.inner.encode(missing)
                for t, v in zip(missing, vecs):
                    self._cache[t] = v
            return np.vstack([self._cache[t] for t in texts]) if texts else self.inner.encode([])


@lru_cache(maxsize=1)
def get_embedder() -> CachedEmbedder:
    if EMBEDDING_BACKEND.lower() != "hash":
        try:
            emb = SentenceTransformerEmbedder(EMBEDDING_MODEL)
            log.info("Using sentence-transformers model %s", EMBEDDING_MODEL)
            return CachedEmbedder(emb)
        except Exception as exc:  # missing package, offline, download blocked ...
            log.warning("Sentence-Transformers unavailable (%s) – using offline hashing embedder", exc)
    return CachedEmbedder(HashingEmbedder())
