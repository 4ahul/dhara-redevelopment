"""
Document Indexer using Semantic Chunking
Rebuilds the vector store with semantic chunks for better retrieval.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import OpenAIEmbeddings
from milvus_utils import get_collection, setup_local_milvus
from semantic_chunker import SemanticChunker

DOCS_DIR = Path(__file__).parent.parent / "docs"
COLLECTION_NAME = "dcpr_knowledge"
BATCH_SIZE = 100


def extract_text_from_file(filepath: Path) -> str:
    """Extract text from various file formats"""
    text = ""

    try:
        if filepath.suffix.lower() == ".pdf":
            try:
                import pypdf

                reader = pypdf.PdfReader(str(filepath))
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            except Exception:
                try:
                    import fitz

                    doc = fitz.open(str(filepath))
                    for page in doc:
                        text += page.get_text() + "\n"
                except Exception:
                    pass
        elif filepath.suffix.lower() == ".txt":
            with open(filepath, encoding="utf-8") as f:
                text = f.read()
        elif filepath.suffix.lower() == ".docx":
            try:
                from docx import Document

                doc = Document(str(filepath))
                text = "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                pass
    except Exception:
        pass

    if not text or len(text) < 50:
        return None

    return text


def semantic_chunk_text(text: str, source: str) -> list[tuple[str, str]]:
    """Chunk text using semantic approach"""
    chunker = SemanticChunker(
        min_chunk_size=100,
        max_chunk_size=1200,
        overlap=150,
    )
    return chunker.chunk_text(text, source)


def find_all_files() -> list[Path]:
    """Find all document files to process"""
    extensions = [".pdf", ".txt", ".docx"]
    files = []
    skip_files = {
        "README.md",
        "INTEGRATION_IMPLEMENTATION.md",
        "GOVERNMENT_INTEGRATION.md",
    }

    doc_dir = Path() if not DOCS_DIR.exists() else DOCS_DIR

    for root, _dirs, filenames in os.walk(doc_dir):
        for f in filenames:
            if any(f.lower().endswith(ext) for ext in extensions) and f not in skip_files:
                files.append(Path(root) / f)

    return files


def process_file(filepath: Path) -> list[tuple[str, str]]:
    """Process a single file and return chunks"""
    text = extract_text_from_file(filepath)
    if not text:
        return []

    # Use semantic chunking
    source = str(filepath.relative_to(filepath.parent))
    return semantic_chunk_text(text, source)


def index_chunks(chunks: list[tuple[str, str]], collection, embeddings):
    """Index chunks into Milvus"""
    total = len(chunks)
    indexed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        chunk_texts = [c[0] for c in batch]
        metadatas = [c[1] for c in batch]

        try:
            vectors = embeddings.embed_documents(chunk_texts)

            # Prepare data for insertion
            ids = list(range(i, i + len(batch)))
            data = [ids, chunk_texts, metadatas, vectors]

            collection.insert(data)
            indexed += len(batch)

        except Exception:
            pass

    return indexed


def main():

    # Setup Milvus
    setup_local_milvus()
    collection = get_collection(COLLECTION_NAME)

    if collection.num_entities > 0:
        response = input("  Clear and rebuild? (y/n): ")
        if response.lower() == "y":
            collection.drop()
            collection = get_collection(COLLECTION_NAME)
        else:
            pass

    # Setup embeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Find and process files
    files = find_all_files()

    if not files:
        return

    all_chunks = []

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in as_completed(futures):
            try:
                chunks = future.result()
                all_chunks.extend(chunks)
            except Exception:
                pass

    if not all_chunks:
        return

    # Index chunks
    index_chunks(all_chunks, collection, embeddings)


if __name__ == "__main__":
    main()
