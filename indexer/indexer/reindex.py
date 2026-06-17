"""One-shot reindex of a knowledge folder through the current indexer pipeline.

Walks a directory, parses every supported file, chunks it, computes dense
(USER-bge-m3) + sparse (BM25) vectors, and upserts into Qdrant — exactly the
same code path as the web upload, just driven from local files instead of the UI.

Usage (inside the indexer image, where Qdrant is reachable as ``qdrant``):
    docker compose run --rm -v /path/to/knowledge:/knowledge:ro \
        indexer python -m indexer.reindex /knowledge --clear

Locally (with .env pointing QDRANT_HOST at localhost):
    cd indexer && uv run python -m indexer.reindex /path/to/knowledge --clear

Use --clear to drop and recreate the knowledge_base collection first (needed
when migrating schema, e.g. switching to the dense+sparse hybrid layout).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from indexer.chunker import chunk_documents
from indexer.config import settings
from indexer.embedder import embed_documents, embed_documents_sparse
from indexer.parsers import get_parser
from indexer.qdrant_client import (
    KNOWLEDGE_BASE,
    clear_collection,
    make_point_id,
    upsert_batch,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reindex")

ALLOWED_EXTENSIONS = {".html", ".htm", ".pdf", ".md", ".txt"}


def collect_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Reindex a knowledge folder into Qdrant.")
    parser.add_argument("root", type=Path, help="Folder with knowledge files")
    parser.add_argument(
        "--clear", action="store_true", help="Drop and recreate the collection first"
    )
    args = parser.parse_args()

    root: Path = args.root
    if not root.is_dir():
        logger.error("Not a directory: %s", root)
        return 1

    files = collect_files(root)
    if not files:
        logger.error("No supported files found under %s", root)
        return 1
    logger.info("Found %d files under %s", len(files), root)

    if args.clear:
        logger.info("Clearing collection %s ...", KNOWLEDGE_BASE)
        clear_collection(KNOWLEDGE_BASE)

    # Parse + chunk every file.
    all_chunks: list[dict] = []
    for path in files:
        # Use the path relative to root as the "filename" so doc_type detection
        # and breadcrumbs see the real name, but keep it stable across machines.
        filename = path.name
        parse = get_parser(filename)
        if parse is None:
            logger.warning("No parser for %s, skipped", path)
            continue
        content = path.read_bytes()
        try:
            docs = parse(filename, content)
        except Exception:
            logger.exception("Failed to parse %s", path)
            continue
        chunks = chunk_documents(
            docs, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        all_chunks.extend(chunks)
        logger.info("%s -> %d chunks", path.name, len(chunks))

    if not all_chunks:
        logger.error("Nothing to index after parsing.")
        return 1

    # Embed + upsert in batches.
    total = len(all_chunks)
    batch_size = settings.batch_size
    upserted = 0
    for start in range(0, total, batch_size):
        batch = all_chunks[start : start + batch_size]
        texts = [c["text"] for c in batch]
        vectors = embed_documents(texts)
        sparse_vectors = embed_documents_sparse(texts)
        ids = [
            make_point_id(KNOWLEDGE_BASE, c["metadata"]["source"], c["metadata"]["chunk_index"])
            for c in batch
        ]
        payloads = [
            {"text": c["text"], **{k: v for k, v in c["metadata"].items() if k != "chunk_index"}}
            for c in batch
        ]
        upsert_batch(KNOWLEDGE_BASE, ids, vectors, payloads, sparse_vectors=sparse_vectors)
        upserted += len(batch)
        logger.info("Upserted %d/%d", upserted, total)

    logger.info("Done. %d chunks indexed into %s.", upserted, KNOWLEDGE_BASE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
