"""Small persistent vector store (cosine similarity over a NumPy matrix) with metadata filtering."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .loaders import Document


class VectorStore:
    def __init__(self) -> None:
        self.docs: list[Document] = []
        self.matrix = np.zeros((0, 1), dtype=np.float32)

    def __len__(self) -> int:
        return len(self.docs)

    def add(self, docs: list[Document], vectors: np.ndarray) -> None:
        self.docs.extend(docs)
        self.matrix = vectors.astype(np.float32) if self.matrix.shape[0] == 0 else np.vstack([self.matrix, vectors])

    def mask(self, filters: dict | None) -> np.ndarray:
        if not filters:
            return np.ones(len(self.docs), dtype=bool)
        keep = np.ones(len(self.docs), dtype=bool)
        for i, d in enumerate(self.docs):
            for k, v in filters.items():
                have = d.metadata.get(k)
                ok = have in v if isinstance(v, (list, set, tuple)) else have == v
                if not ok:
                    keep[i] = False
                    break
        return keep

    def similarities(self, qvec: np.ndarray) -> np.ndarray:
        return self.matrix @ qvec if len(self.docs) else np.zeros(0, dtype=np.float32)

    # ---------------------------------------------------------------- persistence
    @staticmethod
    def fingerprint(docs: list[Document], embedder_name: str) -> str:
        h = hashlib.sha1(embedder_name.encode())
        for d in docs:
            h.update(d.text.encode())
        return h.hexdigest()[:16]

    def save(self, directory: Path, fp: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "matrix.npy", self.matrix)
        (directory / "docs.json").write_text(json.dumps({"fp": fp, "docs": [{"text": d.text, "metadata": d.metadata} for d in self.docs]}), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path, fp: str) -> "VectorStore | None":
        try:
            meta = json.loads((directory / "docs.json").read_text(encoding="utf-8"))
            if meta["fp"] != fp:
                return None
            vs = cls()
            vs.docs = [Document(d["text"], d["metadata"]) for d in meta["docs"]]
            vs.matrix = np.load(directory / "matrix.npy")
            return vs
        except Exception:
            return None
