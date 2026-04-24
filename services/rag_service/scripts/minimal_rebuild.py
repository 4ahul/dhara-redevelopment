#!/usr/bin/env python3
"""
Minimal rebuild - index just 200 chunks for quick test
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymilvus import (
    connections,
    utility,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
)


def main():
    print("Minimal rebuild - 200 chunks for testing")

    # Load env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().strip().split("\n"):
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key] = val.strip()

    # Connect
    MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
    MILVUS_PORT = os.environ.get("MILVUS_PORT", "19530")
    MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN", "")

    print("Connecting to Milvus...")
    if MILVUS_TOKEN:
        connections.connect(
            alias="default",
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            token=MILVUS_TOKEN,
            secure=True,
        )
    else:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)

    # Drop old
    if utility.has_collection("documents"):
        print("Dropping collection...")
        utility.drop_collection("documents")

    # Create collection
    dim = 768
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="Document embeddings")
    collection = Collection("documents", schema)

    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    print("[OK] Collection created")

    # Load DCPR - just first few pages
    dcpr_file = Path("data/docs/DCPR 2034 updated upto 30.9.24 for circulation (1).pdf")
    if not dcpr_file.exists():
        print("DCPR file not found")
        return

    print("Loading DCPR PDF (first 20 pages)...")
    from pypdf import PdfReader

    reader = PdfReader(dcpr_file)
    # Just first 20 pages for quick test
    text = "\n".join([p.extract_text() or "" for p in reader.pages[:20]])
    print(f"Loaded {len(text)} chars")

    # Chunk
    print("Chunking...")
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=50,
        separators=["\n\n", "\n", "Regulation ", ". "],
    )
    chunks = splitter.create_documents([text])
    # Limit to 200
    chunks = chunks[:200]
    print(f"Created {len(chunks)} chunks")

    # Embed and index
    print("Embedding with Ollama...")
    from langchain_ollama import OllamaEmbeddings
    import time

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Process in small batches
    batch_size = 10
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.page_content for c in batch]

        # Embed
        start = time.time()
        vectors = embeddings.embed_documents(texts)
        embed_time = time.time() - start

        # Insert
        collection.insert([texts, vectors])
        collection.flush()

        print(f"  {min(i + batch_size, total)}/{total} ({embed_time:.1f}s)")

    collection.load()
    print(f"\nDone! Indexed {len(chunks)} chunks")


if __name__ == "__main__":
    main()

