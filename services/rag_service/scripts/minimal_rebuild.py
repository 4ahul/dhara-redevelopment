#!/usr/bin/env python3
"""
Minimal rebuild - index just 200 chunks for quick test
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)


def main():

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

    # Load DCPR - just first few pages
    dcpr_file = Path("data/docs/DCPR 2034 updated upto 30.9.24 for circulation (1).pdf")
    if not dcpr_file.exists():
        return

    from pypdf import PdfReader

    reader = PdfReader(dcpr_file)
    # Just first 20 pages for quick test
    text = "\n".join([p.extract_text() or "" for p in reader.pages[:20]])

    # Chunk
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=50,
        separators=["\n\n", "\n", "Regulation ", ". "],
    )
    chunks = splitter.create_documents([text])
    # Limit to 200
    chunks = chunks[:200]

    # Embed and index
    import time

    from langchain_ollama import OllamaEmbeddings

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
        time.time() - start

        # Insert
        collection.insert([texts, vectors])
        collection.flush()

    collection.load()


if __name__ == "__main__":
    main()
