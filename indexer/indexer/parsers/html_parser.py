"""Parser for HTML files."""

from __future__ import annotations

from bs4 import BeautifulSoup


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
    """Parse HTML file into list of {text, metadata} dicts."""
    encoding = "utf-8"
    try:
        text = content.decode(encoding)
    except UnicodeDecodeError:
        text = content.decode("cp1251", errors="replace")

    soup = BeautifulSoup(text, "html.parser")

    # Remove non-content tags
    for tag in soup.find_all(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()

    doc_type = _detect_doc_type(filename)
    documents = []

    # Walk through headings to split into sections
    headings = soup.find_all(["h1", "h2", "h3"])
    if not headings:
        # No headings — treat whole body as one document
        body_text = soup.get_text(separator="\n", strip=True)
        if body_text.strip():
            documents.append(
                {
                    "text": body_text,
                    "metadata": {
                        "source": filename,
                        "section": filename,
                        "doc_type": doc_type,
                    },
                }
            )
        return documents

    # Collect text before first heading
    pre_heading_parts = []
    for el in headings[0].previous_siblings:
        t = el.get_text(strip=True) if hasattr(el, "get_text") else str(el).strip()
        if t:
            pre_heading_parts.append(t)
    if pre_heading_parts:
        pre_heading_parts.reverse()
        documents.append(
            {
                "text": "\n".join(pre_heading_parts),
                "metadata": {
                    "source": filename,
                    "section": filename,
                    "doc_type": doc_type,
                },
            }
        )

    # Collect text under each heading
    for _i, heading in enumerate(headings):
        section_title = heading.get_text(strip=True)
        parts = []

        sibling = heading.next_sibling
        stop_tags = {"h1", "h2", "h3"}
        while sibling:
            if hasattr(sibling, "name") and sibling.name in stop_tags:
                break
            t = sibling.get_text(strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
            if t:
                parts.append(t)
            sibling = sibling.next_sibling

        section_text = "\n".join(parts)
        if section_text.strip():
            documents.append(
                {
                    "text": section_text,
                    "metadata": {
                        "source": filename,
                        "section": section_title,
                        "doc_type": doc_type,
                    },
                }
            )

    return documents
