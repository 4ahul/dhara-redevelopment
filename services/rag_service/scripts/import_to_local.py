import json
import os
from openai import OpenAI
from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType

LOCAL_HOST = "localhost"
LOCAL_PORT = "19530"

def reembed_and_import(input_file, collection_name="documents"):
    # Load text data
    with open(input_file, 'r', encoding='utf-8') as f:
        texts = json.load(f)
    
    print(f"Loaded {len(texts)} texts")
    
    # Get OpenAI client
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Re-embed texts (text-embedding-3-small = 1536 dim)
    print("Re-embedding texts...")
    embeddings = []
    
    for i, item in enumerate(texts):
        text = item.get('text', '')
        if text:
            emb = client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Max tokens
            )
            embeddings.append(emb.data[0].embedding)
        
        if (i + 1) % 100 == 0:
            print(f"Embedded {i + 1}/{len(texts)}")
    
    print(f"Embedded {len(embeddings)} vectors")
    
    # Connect to local Milvus
    print(f"Connecting to local Milvus at {LOCAL_HOST}:{LOCAL_PORT}...")
    connections.connect("default", host=LOCAL_HOST, port=LOCAL_PORT)
    
    # Drop existing collection if exists
    if utility.has_collection(collection_name):
        print(f"Dropping existing {collection_name}...")
        utility.drop_collection(collection_name)
    
    # Create schema (matching cloud: id, text, embedding with dim 1536)
    dim = 1536
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields, description="Document embeddings")
    collection = Collection(collection_name, schema)
    
    # Create index
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 256}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    
    # Insert data
    print(f"Inserting {len(texts)} entities...")
    text_data = [item.get('text', '') for item in texts]
    
    batch_size = 500
    for i in range(0, len(text_data), batch_size):
        end = min(i + batch_size, len(text_data))
        collection.insert([text_data[i:end], embeddings[i:end]])
        print(f"Inserted {end}/{len(text_data)}")
    
    collection.flush()
    collection.load()
    
    print(f"Import complete! {collection_name} has {collection.num_entities} entities")
    connections.disconnect("default")

if __name__ == "__main__":
    reembed_and_import("documents_text.json")
