"""Parser for plain text (.txt) and Markdown (.md) files."""

from __future__ import annotations


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
    """Parse text/markdown file into list of {text, metadata} dicts."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("cp1251", errors="replace")

    doc_type = _detect_doc_type(filename)
    is_markdown = filename.lower().endswith(".md")

    if is_markdown:
        return _parse_markdown(filename, text, doc_type)

    # Plain .txt — whole file as one document
    if text.strip():
        return [
            {
                "text": text.strip(),
                "metadata": {
                    "source": filename,
                    "section": filename,
                    "doc_type": doc_type,
                },
            }
        ]
    return []


def _humanize_filename(filename: str) -> str:
    """'кафедра-анализа-данных-и-ИИ.md' -> 'кафедра анализа данных и ИИ'."""
    stem = filename.rsplit("/", 1)[-1]
    for ext in (".md", ".txt"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    return stem.replace("-", " ").replace("_", " ").strip()


def _parse_markdown(filename: str, text: str, doc_type: str) -> list[dict]:
    """Split markdown by headings, keeping the heading hierarchy as context.

    Each section's text is prefixed with a breadcrumb of its enclosing headings
    (e.g. "кафедра ... / Преподаватели / Осипян Валерий Осипович"). This puts the
    heading words — which would otherwise be dropped from the body — into the
    embedded and stored text, so a search for a name or a section title can match.
    """
    file_title = _humanize_filename(filename)
    lines = text.split("\n")
    documents = []
    heading_stack: list[tuple[int, str]] = []  # (level, title), outermost first
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        titles = [t for _, t in heading_stack]
        breadcrumb = " / ".join([file_title, *titles])
        section = titles[-1] if titles else file_title
        documents.append(
            {
                "text": f"{breadcrumb}\n\n{body}",
                "metadata": {
                    "source": filename,
                    "section": section,
                    "heading_path": breadcrumb,
                    "doc_type": doc_type,
                },
            }
        )

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            current_lines = []
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("#").strip()
            # Drop any sibling/deeper headings, then descend one level.
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
        else:
            current_lines.append(line)

    flush()
    return documents
