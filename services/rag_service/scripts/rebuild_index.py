#!/usr/bin/env python3
"""
Rebuild vector store with semantic paragraph chunking + nomic-embed-text.
Run this whenever you add new documents to data/docs.

Usage:
    python scripts/rebuild_index.py
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from pypdf import PdfReader

BATCH_SIZE = 20  # chunks per Ollama embedding call
CHUNK_SIZE = 800  # characters per chunk
CHUNK_OVERLAP = 100
DIM = 768  # nomic-embed-text dimension


def load_env():
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_text(filepath: Path) -> str:
    """Extract text from PDF, TXT, or DOCX."""
    try:
        if filepath.suffix.lower() == ".pdf":
            reader = PdfReader(filepath)
            pages = [p.extract_text() or "" for p in reader.pages]
            return "\n".join(pages)
        if filepath.suffix.lower() == ".txt":
            return filepath.read_text(encoding="utf-8", errors="ignore")
        if filepath.suffix.lower() == ".docx":
            import docx

            doc = docx.Document(str(filepath))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        pass
    return ""


def chunk_text(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n\n", "\n\n", "\n", "Regulation ", ". ", " ", ""],
        keep_separator=True,
    )
    chunks = splitter.create_documents([text])
    # Merge tiny trailing chunks with previous
    merged = []
    for c in chunks:
        if merged and len(c.page_content) < 100:
            merged[-1].page_content += " " + c.page_content
        else:
            merged.append(c)
    return merged


def main():

    load_env()

    # Connect
    host = os.environ.get("MILVUS_HOST", "localhost")
    port = os.environ.get("MILVUS_PORT", "19530")
    token = os.environ.get("MILVUS_TOKEN", "")

    if token:
        connections.connect(alias="default", host=host, port=port, token=token, secure=True)
    else:
        connections.connect(alias="default", host=host, port=port)

    # Drop + recreate collection
    if utility.has_collection("documents"):
        utility.drop_collection("documents")

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    collection = Collection("documents", CollectionSchema(fields, "DCPR document embeddings"))
    collection.create_index(
        "embedding",
        {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
    )

    # Find documents - primary regulation files only
    docs_dir = Path("data/docs")
    PRIMARY = [
        "DCPR 2034 updated upto 30.9.24 for circulation (1).pdf",
        "DCPR Book All Pages 13-09-2024.pdf",
        "Updated-UDCPR-2022.pdf",
        "UDCPR updated to 30.1.2024.pdf",
        "UDCPR Updated 30.01.25 with earlier provisions & corrections.pdf",
        "MRTP act 1966 Modified upto 26 th nov 2015.pdf",
        "india-national-building-code-nbc-2016-vol-1.pdf",
        "Various Premiums under DCR 2034.pdf",
        "Various Type of Premiums under DCPR - 2034 05.12.23.pdf",
    ]
    files = []
    for name in PRIMARY:
        matches = list(docs_dir.glob(f"**/{name}"))
        if matches:
            files.append(matches[0])

    if not files:
        # fallback: any DCPR PDF in root
        files = [f for f in docs_dir.glob("*.pdf") if "DCPR" in f.name.upper()]

    for f in files:
        f.stat().st_size / 1024 / 1024

    # Init embeddings
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vec = embeddings.embed_query("test")
    assert len(vec) == DIM, f"Expected dim {DIM}, got {len(vec)}"

    total_indexed = 0
    overall_start = time.time()

    for _i, filepath in enumerate(files):
        t0 = time.time()

        text = load_text(filepath)
        if not text.strip():
            continue

        chunks = chunk_text(text)

        indexed = 0
        for j in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[j : j + BATCH_SIZE]
            texts = [c.page_content for c in batch]
            try:
                vectors = embeddings.embed_documents(texts)
                collection.insert([texts, vectors])
                collection.flush()
                indexed += len(texts)
                total_indexed += len(texts)
                indexed / (time.time() - t0)
            except Exception:
                pass

    collection.load()
    time.time() - overall_start


if __name__ == "__main__":
    main()
