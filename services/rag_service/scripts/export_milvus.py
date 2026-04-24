import json
import os
from pymilvus import connections, Collection, utility

# Zilliz Cloud credentials from environment
ZILLIZ_CLUSTER = os.environ.get("ZILLIZ_CLUSTER", "")
ZILLIZ_TOKEN = os.environ.get("ZILLIZ_TOKEN", "")
COLLECTION_NAME = "documents"

def export_collection(collection_name, output_file):
    if not ZILLIZ_CLUSTER or not ZILLIZ_TOKEN:
        print("Error: Set ZILLIZ_CLUSTER and ZILLIZ_TOKEN environment variables")
        return
        
    print(f"Connecting to Zilliz Cloud...")
    connections.connect(
        "default", 
        host=ZILLIZ_CLUSTER, 
        port="443", 
        token=ZILLIZ_TOKEN,
        secure=True
    )
    
    if not utility.has_collection(collection_name):
        print(f"Collection {collection_name} not found!")
        print("Available:", utility.list_collections())
        return

    collection = Collection(collection_name)
    collection.load()
    
    total = collection.num_entities
    print(f"Total: {total}")
    
    all_results = []
    batch_size = 500
    offset = 0
    
    while offset < total:
        results = collection.query(
            expr="", 
            output_fields=["id", "text"],
            limit=batch_size,
            offset=offset
        )
        
        if not results:
            break
            
        all_results.extend(results)
        print(f"Exported {len(all_results)}/{total}")
        offset += batch_size
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False)
    
    print(f"Done! Exported {len(all_results)} texts to {output_file}")
    connections.disconnect("default")
    print("Cloud DB untouched.")

if __name__ == "__main__":
    export_collection(COLLECTION_NAME, "documents_text.json")
