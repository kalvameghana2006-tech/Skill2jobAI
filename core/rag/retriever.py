"""Hybrid retriever: dense cosine + BM25, fused with Reciprocal Rank Fusion, optional metadata filters."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from .loaders import Document
from .vectorstore import VectorStore

_TOK = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = set("the a an and or of to in for on with is are be as at by it this that from you your".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOK.findall(text.lower()) if t not in _STOP]


@dataclass
class Hit:
    doc: Document
    score: float
    dense: float
    lexical: float
    rank: int

    @property
    def cite(self) -> str:
        m = self.doc.metadata
        return f"{m.get('title') or m.get('source')} › {m.get('heading', '')}".strip(" ›")


class BM25:
    def __init__(self, docs: list[Document], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [self._count(tokenize(d.text)) for d in docs]
        self.len = np.array([sum(t.values()) for t in self.tf], dtype=np.float32)
        self.avg = float(self.len.mean()) if len(docs) else 1.0
        df: dict[str, int] = {}
        for t in self.tf:
            for w in t:
                df[w] = df.get(w, 0) + 1
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    @staticmethod
    def _count(tokens: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in tokens:
            out[t] = out.get(t, 0) + 1
        return out

    def scores(self, query: str) -> np.ndarray:
        q = tokenize(query)
        s = np.zeros(len(self.tf), dtype=np.float32)
        for i, tf in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
            for w in q:
                f = tf.get(w)
                if f:
                    s[i] += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + norm)
        return s


class HybridRetriever:
    def __init__(self, store: VectorStore, embedder, rrf_k: int = 30):
        self.store, self.embedder, self.rrf_k = store, embedder, rrf_k
        self.bm25 = BM25(store.docs)

    def retrieve(self, query: str, k: int = 4, filters: dict | None = None, min_score: float = 0.0) -> list[Hit]:
        if not len(self.store):
            return []
        keep = self.store.mask(filters)
        if not keep.any():
            return []
        q = self.embedder.encode([query])[0]
        dense = self.store.similarities(q)
        lex = self.bm25.scores(query)
        idx = np.where(keep)[0]
        d_rank = {i: r for r, i in enumerate(idx[np.argsort(-dense[idx])])}
        l_rank = {i: r for r, i in enumerate(idx[np.argsort(-lex[idx])])}
        fused = {i: 1 / (self.rrf_k + d_rank[i]) + (1 / (self.rrf_k + l_rank[i]) if lex[i] > 0 else 0) for i in idx}
        order = sorted(fused, key=fused.get, reverse=True)
        hits = []
        for r, i in enumerate(order):
            if len(hits) >= k:
                break
            if fused[i] < min_score:
                continue
            hits.append(Hit(self.store.docs[i], float(fused[i]), float(dense[i]), float(lex[i]), len(hits) + 1))
        return hits
