"""Document loaders: markdown study notes, learning resources, job postings, PDFs and plain text."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.metadata.get("chunk_id") or self.metadata.get("source", "doc")


def load_markdown_dir(directory: Path) -> list[Document]:
    docs = []
    for f in sorted(Path(directory).glob("**/*.md")):
        docs.append(Document(f.read_text(encoding="utf-8"), {"source": f.name, "doc_type": "note", "skill_id": f.stem}))
    for f in sorted(Path(directory).glob("**/*.txt")):
        docs.append(Document(f.read_text(encoding="utf-8"), {"source": f.name, "doc_type": "note", "skill_id": f.stem}))
    return docs


def load_resources(path: Path, taxonomy=None) -> list[Document]:
    out = []
    for r in json.loads(Path(path).read_text(encoding="utf-8")):
        skill = taxonomy.name(r["skill"]) if taxonomy else r["skill"]
        text = (f"{r['title']}. A {r['difficulty']} {r['type']} on {skill} from {r['source']}, about {r['duration_min']} minutes. {r['why']}")
        out.append(Document(text, {"source": r["source"], "doc_type": "resource", "skill_id": r["skill"], "chunk_id": r["id"],
                                   "resource": r}))
    return out


def load_jobs(jobs: list[dict]) -> list[Document]:
    return [Document(f"{j['title']} at {j['company']} ({j.get('city', '')}). " + j["description"],
                     {"source": j["id"], "doc_type": "job", "chunk_id": j["id"], "job_id": j["id"]}) for j in jobs]


def load_text_file(name: str, data: bytes) -> list[Document]:
    """Load a user-supplied file (pdf / md / txt) so their own notes can be searched too."""
    low = name.lower()
    if low.endswith(".pdf"):
        return [Document(load_pdf_text(data), {"source": name, "doc_type": "note", "skill_id": "user"})]
    return [Document(data.decode("utf-8", errors="ignore"), {"source": name, "doc_type": "note", "skill_id": "user"})]


def load_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)
