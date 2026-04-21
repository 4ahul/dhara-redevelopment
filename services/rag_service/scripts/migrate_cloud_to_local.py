import os
import logging
from pymilvus import connections, Collection, utility
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cloud Milvus (Source)
CLOUD_HOST = os.getenv("CLOUD_MILVUS_HOST", "in03-7ab10f7686b6973.serverless.aws-eu-central-1.cloud.zilliz.com")
CLOUD_TOKEN = os.getenv("CLOUD_MILVUS_TOKEN", "95ad1dc5854224a3e1108e2fd806dd948f46f7d1db180e1d5aad64791f8868473751b8520f7da41c6545f455662bb16a9719cc8f")
SOURCE_COLLECTION = "dcpr_knowledge"
DEST_COLLECTION = "dcpr_knowledge"

# Local Milvus Lite (Destination)
# When running in Docker, data is at /app/data/
DATA_DIR = os.getenv("DATA_DIR", "data")
LOCAL_DB_PATH = os.path.join(DATA_DIR, "milvus_local.db")

def migrate():
    # 1. Connect to Cloud
    logger.info(f"Connecting to Cloud Milvus: {CLOUD_HOST}...")
    connections.connect(alias="cloud", host=CLOUD_HOST, port="443", token=CLOUD_TOKEN, secure=True)

    if not utility.has_collection(SOURCE_COLLECTION, using="cloud"):
        logger.error(f"Collection '{SOURCE_COLLECTION}' not found on cloud instance.")
        return

    cloud_col = Collection(SOURCE_COLLECTION, using="cloud")
    cloud_col.load()
    num_entities = cloud_col.num_entities
    logger.info(f"Found {num_entities} entities in cloud collection '{SOURCE_COLLECTION}'.")

    # 2. Connect to Local Milvus Lite
    logger.info(f"Connecting to Local Milvus Lite: {LOCAL_DB_PATH}...")
    from milvus_lite import MilvusClient
    
    # Simple check for directory
    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    
    local_client = MilvusClient(LOCAL_DB_PATH)

    # 3. Handle Local Collection
    if DEST_COLLECTION in local_client.list_collections():
        logger.info(f"Local collection '{DEST_COLLECTION}' already exists. Re-creating...")
        local_client.drop_collection(DEST_COLLECTION)

    # Create local collection
    logger.info(f"Creating local collection '{DEST_COLLECTION}'...")
    local_client.create_collection(
        collection_name=DEST_COLLECTION,
        dimension=1536,
        metric_type="COSINE"
    )

    # 4. Batch Transfer Data
    logger.info("Starting data transfer (batches of 1000)...")
    offset = 0
    batch_size = 1000
    
    while True:
        res = cloud_col.query(
            expr="id >= 0", 
            output_fields=["*"],
            offset=offset,
            limit=batch_size,
            using="cloud"
        )
        
        if not res:
            break
            
        local_client.insert(
            collection_name=DEST_COLLECTION,
            data=res
        )
        offset += len(res)
        logger.info(f"  Migrated {offset}/{num_entities} entities...")
        
        if len(res) < batch_size:
            break

    logger.info(f"SUCCESS: Migrated {offset} entities to local Milvus Lite.")

if __name__ == "__main__":
    migrate()
