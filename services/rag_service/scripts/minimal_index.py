"""
Minimal Indexer - Process ONE PDF at a time
"""

import os
import hashlib
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

from pymilvus import connections, Collection
from langchain_openai import OpenAIEmbeddings
from pypdf import PdfReader

COLLECTION_NAME = "documents"
BATCH_SIZE = 50


def process_pdf(pdf_path: Path, collection, embeddings):
    rel_path = str(pdf_path.relative_to("data/docs"))
    print(f"Processing: {rel_path}")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"  Cannot read PDF: {e}")
        return 0

    all_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"

    if len(all_text) < 100:
        print(f"  No text extracted")
        return 0

    # Simple chunking
    chunk_size = 800
    chunks = []
    for i in range(0, len(all_text), chunk_size - 100):
        chunk = all_text[i : i + chunk_size].strip()
        if len(chunk) > 50:
            chunks.append(chunk)

    print(f"  Found {len(chunks)} chunks")

    # Process in batches
    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]

        # Metadata
        sources = [rel_path] * len(batch)
        pages = list(range(i + 1, i + len(batch) + 1))
        languages = ["en"] * len(batch)
        doc_types = ["dcpr"] * len(batch)
        chunk_types = ["paragraph"] * len(batch)
        chunk_indices = list(range(i, i + len(batch)))
        file_hashes = [hashlib.sha256(rel_path.encode()).hexdigest()[:16]] * len(batch)

        # Embed
        vectors = embeddings.embed_documents(batch)

        # Insert
        entities = [
            batch,
            sources,
            pages,
            languages,
            doc_types,
            chunk_types,
            chunk_indices,
            file_hashes,
            vectors,
        ]
        collection.insert(entities)
        total += len(batch)
        print(f"    Indexed {len(batch)} (total: {total})")

    collection.flush()
    return total


def main():
    connections.connect(host="localhost", port="19530")
    collection = Collection(COLLECTION_NAME)
    collection.load()

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    docs_dir = Path("data/docs")
    pdf_files = list(docs_dir.rglob("*.pdf"))[:5]  # First 5 only

    total = 0
    for pdf in pdf_files:
        count = process_pdf(pdf, collection, embeddings)
        total += count

    print(f"\nTotal indexed: {total}")
    print(f"Collection count: {collection.num_entities}")


if __name__ == "__main__":
    main()

