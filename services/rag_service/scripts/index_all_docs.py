#!/usr/bin/env python3
"""
Efficiently index all documents in data/docs to Milvus.
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from services.rag_service.services.rag import DocumentLoader, RAGAgent


def load_and_chunk(filepath):
    """Load a file and return chunks"""
    try:
        text = ""
        if filepath.suffix.lower() == ".pdf":
            text = DocumentLoader.load_pdf(filepath)
        elif filepath.suffix.lower() == ".txt":
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif filepath.suffix.lower() == ".docx":
            import docx

            doc = docx.Document(filepath)
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            return []

        if not text:
            return []

        return DocumentLoader.chunk_text(text)
    except Exception:
        return []


def main():
    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().strip().split("\n"):
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key] = val

    docs_dir = Path("data/docs")
    if not docs_dir.exists():
        return

    # Find all supported files
    extensions = [".pdf", ".txt", ".docx"]
    files = []
    for ext in extensions:
        files.extend(list(docs_dir.glob(f"**/*{ext}")))

    if not files:
        return

    agent = RAGAgent(use_milvus=True)

    # We want to be fast. Batching is already done in agent.vectorstore.add_documents
    # But we can parallelize the LOAD and CHUNK phase which is CPU intensive.

    all_chunks = []

    time.time()

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(load_and_chunk, files))

    for chunks in results:
        all_chunks.extend(chunks)

    if not all_chunks:
        return

    # Index in batches (RAGAgent does this internally, but we'll do it in larger chunks for Milvus efficiency if needed)
    # The current RAGAgent.add_documents uses a batch_size of 10 for embeddings.
    # We'll just pass all chunks to it.

    batch_size = 500  # Larger batches for the high-level call
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        agent.vectorstore.add_documents(batch)

    time.time()


if __name__ == "__main__":
    main()
