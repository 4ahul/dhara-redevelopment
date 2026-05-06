"""
Index only the DCPR 2034 PDF into a dedicated Milvus collection.

Re-uses helpers from scripts.index_pipeline (chunking, embedding, Milvus setup)
but restricts input to a single PDF. Collection name comes from the
MILVUS_COLLECTION env var (default: dcpr_knowledge). The existing
`documents` collection (if any) is left untouched.

Usage:
    python -m scripts.index_dcpr_only
    python -m scripts.index_dcpr_only --drop
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from scripts.index_pipeline import (
    chunk_document,
    get_embeddings_client,
    insert_chunks_to_milvus,
    setup_milvus_collection,
)
from scripts.unified_extractor import extract_document

DEFAULT_PDF = Path("data/docs/DCPR 2034 updated upto 30.9.24 for circulation (1).pdf")


def run(pdf_path: Path, drop_existing: bool):
    docs_root = pdf_path.parent

    if not pdf_path.exists():
        sys.exit(1)

    time.time()

    # Phase 1: extract
    doc = extract_document(pdf_path, docs_root)
    if doc.total_chars == 0:
        sys.exit(1)

    # Phase 2: chunk
    chunks = chunk_document(doc)
    if not chunks:
        sys.exit(1)

    # Phase 3: Milvus setup (targeted collection only)
    collection = setup_milvus_collection(drop_existing=drop_existing)

    # Phase 4: embed + insert
    client = get_embeddings_client()
    insert_chunks_to_milvus(collection, chunks, client)

    collection.load()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index the DCPR PDF only")
    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF),
        help="Path to the DCPR PDF (default: the circulation copy in data/docs)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the existing collection (don't drop and recreate)",
    )
    args = parser.parse_args()

    run(Path(args.pdf), drop_existing=not args.keep)
