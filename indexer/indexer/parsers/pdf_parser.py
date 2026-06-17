"""Parser for PDF files using PyMuPDF."""

from __future__ import annotations

import fitz


def _detect_doc_type(filename: str) -> str:
    name = filename.lower()
    if "faq" in name:
        return "faq"
    if "прием" in name or "поступл" in name:
        return "regulation"
    if "расписан" in name:
        return "schedule"
    if "програм" in name or "план" in name:
        return "program"
    return "general"


def parse(filename: str, content: bytes) -> list[dict]:
    """Parse PDF file into list of {text, metadata} dicts, one per page."""
    doc_type = _detect_doc_type(filename)
    documents = []

    with fitz.open(stream=content, filetype="pdf") as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if len(text.strip()) < 50:
                continue
            documents.append(
                {
                    "text": text.strip(),
                    "metadata": {
                        "source": filename,
                        "section": f"Страница {page_num + 1}",
                        "doc_type": doc_type,
                    },
                }
            )

    return documents
