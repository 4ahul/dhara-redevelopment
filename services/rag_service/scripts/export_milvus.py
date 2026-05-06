import json
import os

from pymilvus import Collection, connections, utility

# Zilliz Cloud credentials from environment
ZILLIZ_CLUSTER = os.environ.get("ZILLIZ_CLUSTER", "")
ZILLIZ_TOKEN = os.environ.get("ZILLIZ_TOKEN", "")
COLLECTION_NAME = "documents"


def export_collection(collection_name, output_file):
    if not ZILLIZ_CLUSTER or not ZILLIZ_TOKEN:
        return

    connections.connect("default", host=ZILLIZ_CLUSTER, port="443", token=ZILLIZ_TOKEN, secure=True)

    if not utility.has_collection(collection_name):
        return

    collection = Collection(collection_name)
    collection.load()

    total = collection.num_entities

    all_results = []
    batch_size = 500
    offset = 0

    while offset < total:
        results = collection.query(
            expr="", output_fields=["id", "text"], limit=batch_size, offset=offset
        )

        if not results:
            break

        all_results.extend(results)
        offset += batch_size

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False)

    connections.disconnect("default")


if __name__ == "__main__":
    export_collection(COLLECTION_NAME, "documents_text.json")
