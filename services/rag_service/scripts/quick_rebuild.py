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

from pymilvus import (
    connections,
    utility,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
)


def main():
    print("=" * 60)
    print("Full DCPR Rebuild - nomic-embed-text (768 dim)")
    print("=" * 60)

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

    print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
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
    print("[OK] Connected")

    # Drop and recreate collection
    if utility.has_collection("documents"):
        print("Dropping old 'documents' collection...")
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
    print("[OK] Collection created (768-dim, COSINE)")

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

    print(f"\nIndexing {len(files)} primary regulation documents:")
    for f in files:
        try:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  - {f.name} ({size_mb:.1f} MB)")
        except UnicodeEncodeError:
            print(f"  - [filename] ({f.stat().st_size / 1024 / 1024:.1f} MB)")

    # Init embeddings
    from langchain_ollama import OllamaEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from pypdf import PdfReader

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Test connection
    test_vec = embeddings.embed_query("test")
    assert len(test_vec) == 768, f"Expected 768, got {len(test_vec)}"
    print(f"[OK] Ollama embeddings verified ({len(test_vec)} dim)\n")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n\n", "\n\n", "\n", "Regulation ", ". ", " ", ""],
        keep_separator=True,
    )

    BATCH_SIZE = 20  # chunks per embedding call
    total_indexed = 0
    overall_start = time.time()

    for file_idx, filepath in enumerate(files):
        print(f"\n[{file_idx + 1}/{len(files)}] Processing: {filepath.name}")
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
                print("  [SKIP] No text extracted")
                continue

            print(f"  Loaded {len(text):,} chars")
        except Exception as e:
            print(f"  [ERROR] Loading failed: {e}")
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
        print(f"  Chunked into {len(chunks)} pieces")

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
                eta = (len(chunks) - file_indexed) / rate if rate > 0 else 0
                print(
                    f"  {file_indexed}/{len(chunks)} chunks  ({rate:.1f}/s  ETA {eta:.0f}s)"
                )
            except Exception as e:
                print(f"  [ERROR] Embedding batch {i}: {e}")
                continue

        print(f"  Done: {file_indexed} chunks in {time.time() - file_start:.1f}s")

    # Load for queries
    collection.load()
    total_time = time.time() - overall_start

    print("\n" + "=" * 60)
    print(f"COMPLETE: {total_indexed} chunks indexed in {total_time:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()

