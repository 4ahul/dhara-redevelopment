"""
Quick Indexer - Simple document indexing to Milvus with full metadata schema
Uses OpenAI embeddings, processes all PDFs in data/docs
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

from pymilvus import connections, Collection, DataType

# Config
COLLECTION_NAME = "documents"
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
BATCH_SIZE = 50


def get_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pypdf"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"  PDF error: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Simple chunking by characters"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def detect_doc_type(text: str, filename: str) -> str:
    """Detect document type from text and filename"""
    fname_lower = filename.lower()
    text_lower = text.lower()[:1000]

    if "dcpr" in fname_lower or "dcpr" in text_lower:
        return "dcpr"
    elif "udcpr" in fname_lower or "udcpr" in text_lower:
        return "dcpr"
    elif "mumbai" in fname_lower or "mumbai" in text_lower:
        return "act"
    elif "municipal" in fname_lower or "municipal" in text_lower:
        return "act"
    elif "circular" in fname_lower or "notification" in fname_lower:
        return "circular"
    elif "policy" in fname_lower:
        return "policy"
    else:
        return "other"


def detect_chunk_type(text: str) -> str:
    """Detect chunk type from content"""
    text_lower = text.lower()
    if "table" in text_lower and ("-" in text_lower or "|" in text_lower):
        return "table"
    elif text_lower.startswith("#") or len(text) < 100:
        return "heading"
    elif any(f"regulation {i}" in text_lower for i in range(1, 100)):
        return "clause"
    elif text_lower.startswith("-") or text_lower.startswith("*"):
        return "list"
    else:
        return "paragraph"


def main():
    print("=" * 60)
    print("DHARA RAG - QUICK INDEXER")
    print("=" * 60)

    # Connect to Milvus
    print(f"\n[1] Connecting to Milvus...")
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(COLLECTION_NAME)
    collection.load()
    print(f"    Collection: {COLLECTION_NAME}")

    # Find all PDFs
    print(f"\n[2] Finding PDFs...")
    docs_dir = Path("data/docs")
    pdf_files = list(docs_dir.rglob("*.pdf"))
    print(f"    Found {len(pdf_files)} PDFs")

    if not pdf_files:
        print("No PDFs found!")
        return

    # Get embeddings client
    print(f"\n[3] Setting up embeddings...")
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    test_vec = embeddings.embed_query("test")
    print(f"    Embedding dim: {len(test_vec)}")

    # Process each PDF
    print(f"\n[4] Indexing documents...")
    total_chunks = 0

    for pdf_file in pdf_files:
        rel_path = str(pdf_file.relative_to(docs_dir))
        print(f"  Processing: {rel_path[:50]}...")

        # Extract text
        text = get_text_from_pdf(pdf_file)
        if len(text) < 100:
            print(f"    Skipping: not enough text ({len(text)} chars)")
            continue

        # Detect doc type
        doc_type = detect_doc_type(text, pdf_file.name)

        # Chunk
        chunks = chunk_text(text, chunk_size=800, overlap=100)

        if not chunks:
            continue

        # Prepare batch
        batch_texts = chunks[:200]  # Limit per file
        batch_sources = [rel_path] * len(batch_texts)
        batch_pages = list(range(1, len(batch_texts) + 1))
        batch_languages = ["en"] * len(batch_texts)  # Simplify
        batch_doc_types = [doc_type] * len(batch_texts)
        batch_chunk_types = [detect_chunk_type(c) for c in batch_texts]
        batch_chunk_indices = list(range(len(batch_texts)))
        batch_file_hashes = [hashlib.sha256(rel_path.encode()).hexdigest()[:16]] * len(
            batch_texts
        )

        # Embed
        try:
            vectors = embeddings.embed_documents(batch_texts)
        except Exception as e:
            print(f"    Embed error: {e}")
            continue

        # Insert to Milvus
        entities = [
            batch_texts,
            batch_sources,
            batch_pages,
            batch_languages,
            batch_doc_types,
            batch_chunk_types,
            batch_chunk_indices,
            batch_file_hashes,
            vectors,
        ]

        try:
            collection.insert(entities)
            total_chunks += len(batch_texts)
            print(f"    Indexed {len(batch_texts)} chunks")
        except Exception as e:
            print(f"    Insert error: {e}")

    # Flush
    collection.flush()

    print(f"\n[5] Indexing complete!")
    print(f"    Total chunks: {total_chunks}")
    print(f"    Collection entities: {collection.num_entities}")

    # Verify schema
    print(f"\n[6] Schema verification:")
    for f in collection.schema.fields:
        print(f"    - {f.name}: {f.dtype}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
