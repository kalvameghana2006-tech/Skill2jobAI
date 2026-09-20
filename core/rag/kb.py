"""KnowledgeBase: wires loaders -> splitter -> embedder -> vector store -> hybrid retriever.

Corpus: markdown study notes (one per skill), curated learning resources, and job postings.
Users can add their own notes at runtime (`add_user_document`).
"""
from __future__ import annotations

import logging
import re

from ..config import DATA_DIR, KNOWLEDGE_DIR, VECTOR_CACHE
from .loaders import Document, load_jobs, load_markdown_dir, load_resources, load_text_file
from .retriever import Hit, HybridRetriever, tokenize
from .splitters import split_documents
from .vectorstore import VectorStore

log = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, taxonomy, embedder, jobs: list[dict], llm=None):
        self.taxonomy, self.embedder, self.llm = taxonomy, embedder, llm
        docs = split_documents(load_markdown_dir(KNOWLEDGE_DIR))
        docs += load_resources(DATA_DIR / "resources.json", taxonomy)
        docs += load_jobs(jobs)
        self.n_chunks = len(docs)
        fp = VectorStore.fingerprint(docs, embedder.name)
        store = VectorStore.load(VECTOR_CACHE, fp)
        if store is None:
            store = VectorStore()
            store.add(docs, embedder.encode([d.text for d in docs]))
            try:
                store.save(VECTOR_CACHE, fp)
            except Exception as exc:  # read-only disk etc.
                log.warning("could not cache vectors: %s", exc)
        self.store = store
        self.retriever = HybridRetriever(store, embedder)

    # ---------------------------------------------------------------- retrieval
    def retrieve(self, query: str, k: int = 4, **filters) -> list[Hit]:
        return self.retriever.retrieve(query, k=k, filters={a: b for a, b in filters.items() if b} or None)

    def notes(self, query: str, skill_id: str | None = None, k: int = 3) -> list[Hit]:
        return self.retrieve(query, k=k, doc_type="note", skill_id=skill_id)

    def resources(self, query: str, skill_id: str, k: int = 8) -> list[Hit]:
        return self.retrieve(query, k=k, doc_type="resource", skill_id=skill_id)

    def add_user_document(self, name: str, data: bytes) -> int:
        from .loaders import Document  # noqa: F401

        docs = split_documents(load_text_file(name, data))
        if docs:
            self.store.add(docs, self.embedder.encode([d.text for d in docs]))
            self.retriever = HybridRetriever(self.store, self.embedder)
        return len(docs)

    # ---------------------------------------------------------------- grounded answering
    def answer(self, question: str, skill_id: str | None = None, k: int = 4) -> dict:
        """Answer only from retrieved chunks. Uses Gemini when available, else extractive answer."""
        ids = [skill_id] if skill_id else list(dict.fromkeys(m.skill_id for m in self.taxonomy.extract(question)))
        hits = self.retrieve(question, k=k, doc_type="note", skill_id=ids or None)
        hits = [h for h in hits if h.lexical > 0 or h.dense >= 0.3]
        if not hits:
            return {"answer": "I couldn't find anything in the knowledge base about that. Try naming the skill (for example Docker or SQL).",
                    "sources": [], "grounded": False}
        context = "\n\n".join(f"[{i}] {h.doc.text}" for i, h in enumerate(hits, 1))
        text = None
        if self.llm and self.llm.available:
            text = self.llm.generate(
                f"Answer the question using ONLY the numbered context. Cite sources like [1]. If the context is insufficient, say so.\n\n"
                f"Context:\n{context}\n\nQuestion: {question}",
                system="You are a precise technical tutor for students. Never invent facts beyond the context.", temperature=0.2)
        if not text:
            text = self._extractive(question, hits)
        return {"answer": text, "sources": [{"n": i, "cite": h.cite, "text": h.doc.text, "score": round(h.score, 4)} for i, h in enumerate(hits, 1)],
                "grounded": True}

    @staticmethod
    def _extractive(question: str, hits: list[Hit]) -> str:
        q = set(tokenize(question))
        scored = []
        for n, h in enumerate(hits, 1):
            for line in h.doc.text.splitlines()[1:]:
                line = line.strip("-* ").strip()
                if len(line) < 20 or line.startswith("Practice:"):
                    continue
                overlap = len(q & set(tokenize(line)))
                scored.append((overlap, -n, line, n))
        scored.sort(reverse=True)
        lines = [f"{l.replace('**', '')} [{n}]" for _, _, l, n in scored[:4]]
        return "\n".join(f"• {l}" for l in lines) or hits[0].doc.text
