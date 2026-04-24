"""
Copy the local `dcpr_knowledge` Milvus collection to Zilliz Cloud, preserving
the full metadata schema (text, source, page, language, doc_type, chunk_type,
chunk_index, file_hash, embedding). Uses HNSW + COSINE to match local.

The existing `documents` collection on cloud is NEVER touched.

Usage:
    python -m scripts.migrate_local_to_cloud
    python -m scripts.migrate_local_to_cloud --collection dcpr_knowledge
"""

import os
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from pymilvus import (
    connections,
    utility,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
)


EMBEDDING_DIM = 1536
BATCH = 200  # cloud insert batch


def build_cloud_collection(name: str) -> Collection:
    """Drop + recreate on cloud with the full local schema and HNSW index."""
    if utility.has_collection(name, using="cloud"):
        print(f"[CLOUD] Dropping existing collection: {name}")
        utility.drop_collection(name, using="cloud")
        # Wait for drop to propagate (Zilliz is eventually-consistent).
        for _ in range(20):
            time.sleep(1)
            if not utility.has_collection(name, using="cloud"):
                break
        else:
            print("[CLOUD] WARNING: drop did not propagate within 20s")

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="page", dtype=DataType.INT32),
        FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="chunk_index", dtype=DataType.INT32),
        FieldSchema(name="file_hash", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
    ]
    schema = CollectionSchema(
        fields, description="Dhara RAG - DCPR knowledge (migrated from local)"
    )
    collection = Collection(name, schema, using="cloud")

    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 256},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    print(f"[CLOUD] Created {name} (HNSW, {EMBEDDING_DIM}-dim COSINE)")
    return collection


def dump_local(name: str):
    """Stream all rows from the local collection, including embeddings."""
    col = Collection(name, using="local")
    col.load()
    total = col.num_entities
    print(f"[LOCAL] {name}: {total} entities")

    out_fields = [
        "text",
        "source",
        "page",
        "language",
        "doc_type",
        "chunk_type",
        "chunk_index",
        "file_hash",
        "embedding",
    ]
    offset = 0
    limit = 500
    while offset < total:
        rows = col.query(
            expr="id >= 0",
            output_fields=out_fields,
            limit=limit,
            offset=offset,
        )
        if not rows:
            break
        yield rows
        offset += len(rows)
        print(f"  Dumped {offset}/{total}")


def migrate(name: str):
    local_host = os.environ.get("MILVUS_HOST", "localhost")
    local_port = os.environ.get("MILVUS_PORT", "19530")
    cluster = os.environ["ZILLIZ_CLUSTER"]
    token = os.environ["ZILLIZ_TOKEN"]

    print("=" * 70)
    print("MIGRATE LOCAL -> ZILLIZ CLOUD")
    print("=" * 70)
    print(f"  Collection: {name}")
    print(f"  Local:      {local_host}:{local_port}")
    print(f"  Cloud:      {cluster}")
    print("=" * 70)

    t0 = time.time()

    connections.connect(alias="local", host=local_host, port=local_port, timeout=15)
    connections.connect(
        alias="cloud", host=cluster, port="443", token=token, secure=True, timeout=60
    )

    # Fast-fail if local collection is missing
    if not utility.has_collection(name, using="local"):
        print(f"[FATAL] Local collection '{name}' not found.")
        sys.exit(1)

    cloud_col = build_cloud_collection(name)

    print("\n--- Streaming rows & inserting ---")
    inserted = 0
    buf_text, buf_source, buf_page, buf_lang = [], [], [], []
    buf_dtype, buf_ctype, buf_cidx, buf_hash, buf_vec = [], [], [], [], []

    def flush():
        nonlocal inserted, buf_text, buf_source, buf_page, buf_lang
        nonlocal buf_dtype, buf_ctype, buf_cidx, buf_hash, buf_vec
        if not buf_text:
            return
        cloud_col.insert(
            [
                buf_text,
                buf_source,
                buf_page,
                buf_lang,
                buf_dtype,
                buf_ctype,
                buf_cidx,
                buf_hash,
                buf_vec,
            ]
        )
        inserted += len(buf_text)
        print(f"  Inserted {inserted} into cloud")
        buf_text, buf_source, buf_page, buf_lang = [], [], [], []
        buf_dtype, buf_ctype, buf_cidx, buf_hash, buf_vec = [], [], [], [], []

    for chunk in dump_local(name):
        for r in chunk:
            buf_text.append(r.get("text", ""))
            buf_source.append(r.get("source", ""))
            buf_page.append(int(r.get("page", 0) or 0))
            buf_lang.append(r.get("language", "en"))
            buf_dtype.append(r.get("doc_type", "other"))
            buf_ctype.append(r.get("chunk_type", "paragraph"))
            buf_cidx.append(int(r.get("chunk_index", 0) or 0))
            buf_hash.append(r.get("file_hash", ""))
            buf_vec.append(r.get("embedding"))
            if len(buf_text) >= BATCH:
                flush()
    flush()

    cloud_col.flush()
    cloud_col.load()

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"  Cloud entities: {cloud_col.num_entities}")
    print(f"  Elapsed:        {time.time() - t0:.1f}s")

    connections.disconnect("local")
    connections.disconnect("cloud")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local Milvus -> Zilliz Cloud")
    parser.add_argument(
        "--collection",
        default=os.environ.get("MILVUS_COLLECTION", "dcpr_knowledge"),
        help="Collection name (default: MILVUS_COLLECTION env or dcpr_knowledge)",
    )
    args = parser.parse_args()
    migrate(args.collection)

