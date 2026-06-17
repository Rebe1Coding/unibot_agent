"""Document chunking by word count with sentence-boundary splitting."""

from __future__ import annotations

import re


def chunk_documents(
    documents: list[dict],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[dict]:
    """Split documents into chunks of approximately chunk_size words.

    Tries to split on sentence boundaries (". " or ".\\n").
    Each chunk inherits metadata from its parent document with an
    added "chunk_index" field.
    """
    result = []
    # Running counter across ALL chunks of ALL sections of this file.
    # Critically, chunk_index must be unique per source file: the point id is
    # derived from (source, chunk_index), so resetting it to 0 for every short
    # section makes sibling sections collide and overwrite each other in Qdrant.
    global_index = 0
    for doc in documents:
        text = doc["text"]
        metadata = doc["metadata"]
        words = text.split()

        if len(words) <= chunk_size:
            result.append(
                {
                    "text": text,
                    "metadata": {**metadata, "chunk_index": global_index},
                }
            )
            global_index += 1
            continue

        chunks = _split_text(text, words, chunk_size, chunk_overlap)
        for chunk_text in chunks:
            result.append(
                {
                    "text": chunk_text,
                    "metadata": {**metadata, "chunk_index": global_index},
                }
            )
            global_index += 1

    return result


def _split_text(
    text: str,
    words: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split text into overlapping chunks, preferring sentence boundaries."""
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        # If not the last chunk, try to find a sentence boundary to cut at
        if end < len(words):
            # Look for ". " or ".\n" in the chunk to find a clean break point
            # Search backwards from the end of the chunk
            best_break = _find_sentence_break(chunk_text)
            if best_break is not None:
                chunk_text = chunk_text[: best_break + 1].strip()
                # Recalculate how many words we actually consumed
                end = start + len(chunk_text.split())

        if chunk_text.strip():
            chunks.append(chunk_text.strip())

        # Advance with overlap
        step = max(end - start - chunk_overlap, 1)
        start += step

    return chunks


def _find_sentence_break(text: str) -> int | None:
    """Find the last sentence-ending position in the text.

    Returns the index of the period character, or None if no good break found.
    Only considers breaks in the last 40% of the text to avoid tiny chunks.
    """
    min_pos = int(len(text) * 0.6)
    # Find all sentence-ending positions (". " or ".\n")
    matches = list(re.finditer(r"\.\s", text[min_pos:]))
    if matches:
        return min_pos + matches[-1].start()
    return None
