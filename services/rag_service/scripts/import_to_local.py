import json
import os

from openai import OpenAI
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

LOCAL_HOST = "localhost"
LOCAL_PORT = "19530"


def reembed_and_import(input_file, collection_name="documents"):
    # Load text data
    with open(input_file, encoding="utf-8") as f:
        texts = json.load(f)

    # Get OpenAI client
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Re-embed texts (text-embedding-3-small = 1536 dim)
    embeddings = []

    for i, item in enumerate(texts):
        text = item.get("text", "")
        if text:
            emb = client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Max tokens
            )
            embeddings.append(emb.data[0].embedding)

        if (i + 1) % 100 == 0:
            pass

    # Connect to local Milvus
    connections.connect("default", host=LOCAL_HOST, port=LOCAL_PORT)

    # Drop existing collection if exists
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)

    # Create schema (matching cloud: id, text, embedding with dim 1536)
    dim = 1536
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="Document embeddings")
    collection = Collection(collection_name, schema)

    # Create index
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 256},
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    # Insert data
    text_data = [item.get("text", "") for item in texts]

    batch_size = 500
    for i in range(0, len(text_data), batch_size):
        end = min(i + batch_size, len(text_data))
        collection.insert([text_data[i:end], embeddings[i:end]])

    collection.flush()
    collection.load()

    connections.disconnect("default")


if __name__ == "__main__":
    reembed_and_import("documents_text.json")
