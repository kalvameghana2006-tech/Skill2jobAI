"""Resume text extraction (PDF, DOCX, TXT/MD)."""
from __future__ import annotations

import io
import re
import zipfile

from .rag.loaders import load_pdf_text


def extract_text(name: str, data: bytes) -> str:
    low = name.lower()
    if low.endswith(".pdf"):
        return load_pdf_text(data)
    if low.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    return data.decode("utf-8", errors="ignore")
