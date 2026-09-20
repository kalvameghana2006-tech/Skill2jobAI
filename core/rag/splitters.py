"""Structure-aware splitting: markdown headings first, then sentence-based windows with overlap."""
from __future__ import annotations

import re

from .loaders import Document

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9*\-])")


def split_text(text: str, max_chars: int = 700, overlap: int = 100) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    sents = [s for s in _SENT.split(text) if s.strip()]
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) + 1 > max_chars and cur:
            chunks.append(cur.strip())
            cur = cur[-overlap:] + " " if overlap else ""
        cur += s + " "
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def split_markdown(doc: Document, max_chars: int = 700, overlap: int = 100) -> list[Document]:
    """One chunk per '## heading' section (prefixed with the document title so it is self-contained)."""
    lines = doc.text.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), doc.metadata.get("source", ""))
    sections: list[tuple[str, list[str]]] = []
    heading, buf = "Overview", []
    for l in lines:
        if l.startswith("## "):
            if any(x.strip() for x in buf):
                sections.append((heading, buf))
            heading, buf = l[3:].strip(), []
        elif not l.startswith("# "):
            buf.append(l)
    if any(x.strip() for x in buf):
        sections.append((heading, buf))
    out: list[Document] = []
    for h, body in sections:
        body_txt = "\n".join(body).strip()
        for i, piece in enumerate(split_text(body_txt, max_chars, overlap)):
            meta = dict(doc.metadata) | {"heading": h, "title": title, "chunk_id": f"{doc.metadata.get('source', 'doc')}#{len(out)}"}
            out.append(Document(f"{title} — {h}\n{piece}", meta))
    return out


def split_documents(docs: list[Document], max_chars: int = 700, overlap: int = 100) -> list[Document]:
    out: list[Document] = []
    for d in docs:
        if d.metadata.get("doc_type") == "note":
            if d.text.lstrip().startswith("#"):
                out.extend(split_markdown(d, max_chars, overlap))
            else:
                for i, piece in enumerate(split_text(d.text, max_chars, overlap)):
                    out.append(Document(piece, dict(d.metadata) | {"heading": "text", "title": d.metadata.get("source", ""),
                                                                   "chunk_id": f"{d.metadata.get('source')}#{i}"}))
        else:
            out.append(d)
    return out
