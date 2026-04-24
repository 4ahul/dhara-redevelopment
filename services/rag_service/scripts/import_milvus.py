import os
import json
from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType

def import_collection(input_file, collection_name="documents"):
    host = os.environ.get("MILVUS_HOST", "localhost")
    port = os.environ.get("MILVUS_PORT", "19530")
    token = os.environ.get("MILVUS_TOKEN", "")
    
    # Clean host
    if host.startswith("https://"):
        host = host.replace("https://", "")

    print(f"Connecting to Milvus at {host}:{port}...")
    if token:
        connections.connect("default", host=host, port=port, token=token, secure=True)
    else:
        connections.connect("default", host=host, port=port)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check if data is list of dicts with 'text' and 'embedding' or other format
    if isinstance(data, dict) and 'documents' in data:
        # Format from SimpleVectorStore export
        print(f"Detected SimpleVectorStore export format...")
        texts = [doc['text'] for doc in data['documents']]
        embeddings = data['vectors']
    else:
        # List of objects format
        texts = [item['text'] for item in data]
        embeddings = [item['embedding'] for item in data]
        
    print(f"Loaded {len(texts)} entities from {input_file}")

    if utility.has_collection(collection_name):
        print(f"Collection {collection_name} already exists. Dropping it for clean import...")
        utility.drop_collection(collection_name)

    # Recreate schema (matching rag.py)
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
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    
    print(f"Inserting {len(texts)} entities into {collection_name}...")
    
    # Batch insert to be safe
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        end = min(i + batch_size, len(texts))
        batch_texts = texts[i:end]
        batch_embeddings = embeddings[i:end]
        collection.insert([batch_texts, batch_embeddings])
    
    collection.flush()
    print(f"Collection {collection_name} loaded.")
    collection.load() # Ensure collection is loaded for querying
    print(f"Import complete! {collection_name} now has {collection.num_entities} entities.")
    connections.disconnect("default")

if __name__ == "__main__":
    import_collection("collection.json")

