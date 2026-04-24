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

import os
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from scripts.index_pipeline import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
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
        print(f"[FATAL] PDF not found: {pdf_path}")
        sys.exit(1)

    print("=" * 70)
    print("DCPR SINGLE-DOC INDEX")
    print("=" * 70)
    print(f"  PDF:        {pdf_path}")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Embedding:  OpenAI text-embedding-3-small ({EMBEDDING_DIM} dim)")
    print(f"  Drop first: {drop_existing}")
    print("=" * 70)

    t0 = time.time()

    # Phase 1: extract
    print("\n--- Phase 1: Extract ---")
    doc = extract_document(pdf_path, docs_root)
    if doc.total_chars == 0:
        print(f"[FATAL] Extraction produced no text. Errors: {doc.errors}")
        sys.exit(1)
    print(f"  Pages: {len(doc.pages)}, chars: {doc.total_chars:,}")

    # Phase 2: chunk
    print("\n--- Phase 2: Chunk ---")
    chunks = chunk_document(doc)
    if not chunks:
        print("[FATAL] No chunks produced.")
        sys.exit(1)
    print(f"  Chunks: {len(chunks)}")

    # Phase 3: Milvus setup (targeted collection only)
    print("\n--- Phase 3: Milvus setup ---")
    collection = setup_milvus_collection(drop_existing=drop_existing)

    # Phase 4: embed + insert
    print("\n--- Phase 4: Embed & Insert ---")
    client = get_embeddings_client()
    inserted = insert_chunks_to_milvus(collection, chunks, client)

    collection.load()
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"  Inserted:     {inserted}")
    print(f"  Entities:     {collection.num_entities}")
    print(f"  Elapsed:      {time.time() - t0:.1f}s")


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

