#!/usr/bin/env python3
"""
Full DCPR rebuild with nomic-embed-text (Ollama) - processes in streaming batches
to avoid memory issues and provide progress updates.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import contextlib

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

    # Connect to Milvus
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

    # Drop and recreate collection
    if utility.has_collection("documents"):
        utility.drop_collection("documents")

    dim = 768  # nomic-embed-text
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="DCPR document embeddings")
    collection = Collection("documents", schema)
    collection.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        },
    )

    # Find only the primary regulation documents in docs root (not subdirs)
    # This avoids indexing 3000+ circular/minor files
    docs_dir = Path("data/docs")
    PRIMARY_DOCS = [
        "DCPR 2034 updated upto 30.9.24 for circulation (1).pdf",
        "DCPR Book All Pages 13-09-2024.pdf",
        "Updated-UDCPR-2022.pdf",
        "UDCPR updated to 30.1.2024.pdf",
        "UDCPR Updated 30.01.25 with earlier provisions & corrections.pdf",
        "MRTP act 1966 Modified upto 26 th nov 2015.pdf",
        "india-national-building-code-nbc-2016-vol-1.pdf",
    ]

    files = []
    for name in PRIMARY_DOCS:
        # search recursively
        matches = list(docs_dir.glob(f"**/{name}"))
        if matches:
            files.append(matches[0])

    # Fallback: if none found, grab any DCPR PDF in root
    if not files:
        files = [f for f in docs_dir.glob("*.pdf") if "DCPR" in f.name.upper()]

    for f in files:
        with contextlib.suppress(UnicodeEncodeError):
            f.stat().st_size / 1024 / 1024

    # Init embeddings
    from langchain_ollama import OllamaEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from pypdf import PdfReader

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Test connection
    test_vec = embeddings.embed_query("test")
    assert len(test_vec) == 768, f"Expected 768, got {len(test_vec)}"

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n\n", "\n\n", "\n", "Regulation ", ". ", " ", ""],
        keep_separator=True,
    )

    BATCH_SIZE = 20  # chunks per embedding call
    total_indexed = 0
    overall_start = time.time()

    for _file_idx, filepath in enumerate(files):
        file_start = time.time()

        # Load text
        try:
            text = ""
            if filepath.suffix.lower() == ".pdf":
                reader = PdfReader(filepath)
                pages = []
                for p in reader.pages:
                    t = p.extract_text()
                    if t:
                        pages.append(t)
                text = "\n".join(pages)
            elif filepath.suffix.lower() == ".txt":
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            elif filepath.suffix.lower() == ".docx":
                import docx

                doc = docx.Document(filepath)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

            if not text.strip():
                continue

        except Exception:
            continue

        # Chunk
        chunks = splitter.create_documents([text])
        # Merge very small chunks with previous
        merged = []
        for c in chunks:
            if merged and len(c.page_content) < 100:
                merged[-1].page_content += " " + c.page_content
            else:
                merged.append(c)
        chunks = merged

        # Embed + insert in streaming batches
        file_indexed = 0
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c.page_content for c in batch]

            try:
                vectors = embeddings.embed_documents(texts)
                collection.insert([texts, vectors])
                collection.flush()
                file_indexed += len(texts)
                total_indexed += len(texts)

                elapsed = time.time() - file_start
                rate = file_indexed / elapsed if elapsed > 0 else 0
                (len(chunks) - file_indexed) / rate if rate > 0 else 0
            except Exception:
                continue

    # Load for queries
    collection.load()
    time.time() - overall_start


if __name__ == "__main__":
    main()
