#!/usr/bin/env python3
"""
Efficiently index all documents in data/docs to Milvus.
"""

import os
import sys
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rag_service.services.rag import RAGAgent, DocumentLoader
from pymilvus import connections, utility, Collection

def load_and_chunk(filepath):
    """Load a file and return chunks"""
    try:
        print(f"  Processing: {filepath.name}")
        text = ""
        if filepath.suffix.lower() == ".pdf":
            text = DocumentLoader.load_pdf(filepath)
        elif filepath.suffix.lower() == ".txt":
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif filepath.suffix.lower() == ".docx":
            import docx
            doc = docx.Document(filepath)
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            return []
            
        if not text:
            return []
            
        chunks = DocumentLoader.chunk_text(text)
        return chunks
    except Exception as e:
        print(f"  Error processing {filepath.name}: {e}")
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
        print(f"Directory not found: {docs_dir}")
        return

    # Find all supported files
    extensions = [".pdf", ".txt", ".docx"]
    files = []
    for ext in extensions:
        files.extend(list(docs_dir.glob(f"**/*{ext}")))
    
    if not files:
        print("No documents found to index.")
        return

    print(f"Found {len(files)} documents. Initializing RAG Agent...")
    agent = RAGAgent(use_milvus=True)
    
    # We want to be fast. Batching is already done in agent.vectorstore.add_documents
    # But we can parallelize the LOAD and CHUNK phase which is CPU intensive.
    
    all_chunks = []
    print(f"Extracting text from {len(files)} files using ThreadPool...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(load_and_chunk, files))
        
    for chunks in results:
        all_chunks.extend(chunks)
        
    print(f"Total chunks created: {len(all_chunks)}")
    
    if not all_chunks:
        print("No text extracted. Exiting.")
        return

    # Index in batches (RAGAgent does this internally, but we'll do it in larger chunks for Milvus efficiency if needed)
    # The current RAGAgent.add_documents uses a batch_size of 10 for embeddings.
    # We'll just pass all chunks to it.
    
    print(f"Indexing {len(all_chunks)} chunks to Milvus...")
    batch_size = 500 # Larger batches for the high-level call
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        agent.vectorstore.add_documents(batch)
        print(f"  Progress: {min(i+batch_size, len(all_chunks))}/{len(all_chunks)}")

    end_time = time.time()
    print(f"\nIndexing complete in {end_time - start_time:.2f} seconds!")

if __name__ == "__main__":
    main()

