#!/usr/bin/env python3
"""
Index all documents in data/docs to LOCAL Milvus with OCR fallback.
Uses OpenAI embeddings (text-embedding-3-small)
"""

import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
COLLECTION_NAME = "documents"
EMBEDDING_DIM = 1536

DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"
VECTOR_CACHE_DIR = Path("data/vectors")
VECTOR_CACHE_DIR.mkdir(exist_ok=True)

SKIP_FILES = {"Thumbs.db"}
SKIP_EXTENSIONS = {".tmp", ".bak", ".db"}

EASYOCR_AVAILABLE = False
try:
    import easyocr

    reader = easyocr.Reader(["en", "mr"], gpu=False, verbose=False)
    EASYOCR_AVAILABLE = True
except ImportError:
    pass

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small", openai_api_key=os.environ.get("OPENAI_API_KEY")
)


def get_embedding_dimension():
    return EMBEDDING_DIM


def setup_local_milvus():
    try:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=10)
    except Exception:
        raise

    dim = get_embedding_dimension()

    if utility.has_collection(COLLECTION_NAME):
        utility.drop_collection(COLLECTION_NAME)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="Document embeddings with source")
    collection = Collection(COLLECTION_NAME, schema)

    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    return collection


def extract_text_from_pdf(filepath):
    text = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(filepath)
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        return None


def extract_text_with_ocr(filepath):
    if not EASYOCR_AVAILABLE:
        return None
    try:
        result = reader.readtext(str(filepath), detail=0)
        return "\n".join(result).strip()
    except Exception:
        return None


def process_file(filepath):
    filename = filepath.name

    if filename in SKIP_FILES or filepath.suffix.lower() in SKIP_EXTENSIONS:
        return []

    if filepath.suffix.lower() in {".db", ".tif", ".tiff"} and filepath.suffix.lower() != ".tif":
        return []

    text = ""
    method = ""

    if filepath.suffix.lower() == ".pdf":
        text = extract_text_from_pdf(filepath)
        method = "pypdf"
        if not text or len(text) < 100:
            text = extract_text_with_ocr(filepath)
            method = "ocr" if text else method
    elif filepath.suffix.lower() == ".txt":
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            method = "txt"
        except Exception:
            return []
    elif filepath.suffix.lower() == ".docx":
        try:
            import docx

            doc = docx.Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs]).strip()
            method = "docx"
        except Exception:
            return []
    elif filepath.suffix.lower() in {".tif", ".tiff"}:
        text = extract_text_with_ocr(filepath)
        method = "ocr"
    else:
        return []

    if not text or len(text) < 50:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_text(text)

    source = str(filepath.relative_to(DOCS_DIR))
    return [(chunk, source) for chunk in chunks]


def find_all_files():
    import os

    extensions = [".pdf", ".txt", ".docx", ".tif", ".tiff"]
    files = []
    for root, _dirs, filenames in os.walk(DOCS_DIR):
        for f in filenames:
            if any(f.lower().endswith(ext) for ext in extensions) and f not in SKIP_FILES:
                files.append(Path(root) / f)
    return files


def main():

    setup_local_milvus()
    collection = Collection(COLLECTION_NAME)

    files = find_all_files()

    if not files:
        return

    all_chunks = []

    time.time()

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

    batch_size = 50
    total_inserted = 0

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [c[0] for c in batch]
        sources = [c[1] for c in batch]

        try:
            vectors = embeddings.embed_documents(texts)

            entities = [texts, sources, vectors]

            collection.insert(entities)
            total_inserted += len(texts)

        except Exception:
            continue

    collection.flush()


def index_document(filepath: str, description: str = "") -> str:
    """
    Index a single document to Milvus.
    Returns document ID.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from pypdf import PdfReader

    file_path = Path(filepath)
    filename = file_path.name

    text = ""
    if file_path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() or ""
        except Exception:
            return None
    elif file_path.suffix.lower() == ".txt":
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            return None
    else:
        return None

    if not text:
        return None

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)

    if not chunks:
        return None

    setup_local_milvus()
    collection = Collection(COLLECTION_NAME)

    try:
        vectors = embeddings.embed_documents(chunks)
        sources = [f"{filename}: {description}" for _ in chunks]

        entities = [chunks, sources, vectors]
        collection.insert(entities)
        collection.flush()

        return str(uuid.uuid4())[:8]
    except Exception:
        return None


if __name__ == "__main__":
    main()
