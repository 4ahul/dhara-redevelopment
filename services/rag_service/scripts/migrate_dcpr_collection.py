import logging
import os

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Configuration ---
SOURCE_COLLECTION_NAME = os.environ.get("SOURCE_MILVUS_COLLECTION", "dcpr_knowledge")
TARGET_COLLECTION_NAME = os.environ.get("TARGET_MILVUS_COLLECTION", "dcpr_knowledge")

CLOUD_MILVUS_URI = os.environ.get("ZILLIZ_CLUSTER")
CLOUD_MILVUS_TOKEN = os.environ.get("ZILLIZ_TOKEN")

LOCAL_MILVUS_HOST = os.environ.get("LOCAL_MILVUS_HOST", "milvus")
LOCAL_MILVUS_PORT = os.environ.get("LOCAL_MILVUS_PORT", "19530")

BATCH_SIZE = 50  # Number of entities to fetch/insert at a time


def connect_milvus(
    alias: str, host: str = None, port: str = None, token: str = None, uri: str = None
):
    """Establishes connection to Milvus."""
    try:
        if uri and token:  # Zilliz Cloud connection
            connections.connect(alias=alias, uri=uri, token=token)
            logger.info(f"Connected to Zilliz Cloud (alias: {alias}, uri: {uri})")
        elif host and port:  # Local/on-prem Milvus connection
            connections.connect(alias=alias, host=host, port=port)
            logger.info(f"Connected to local Milvus (alias: {alias}, host: {host}:{port})")
        else:
            raise ValueError("Insufficient connection parameters provided.")
    except Exception as e:
        logger.error(f"Failed to connect to Milvus (alias: {alias}): {e}")
        raise


def get_milvus_collection(alias: str, collection_name: str) -> Collection:
    """Returns a Milvus collection object, ensuring it's loaded."""
    if not utility.has_collection(collection_name, using=alias):
        raise ValueError(f"Collection '{collection_name}' not found in Milvus (alias: {alias}).")
    collection = Collection(collection_name, using=alias)
    collection.load()
    logger.info(f"Loaded collection '{collection_name}' (alias: {alias}).")
    return collection


def create_target_collection_if_not_exists(
    alias: str, collection_name: str, source_collection: Collection
):
    """Creates the target collection with the same schema as the source if it doesn't exist."""
    if utility.has_collection(collection_name, using=alias):
        logger.info(
            f"Target collection '{collection_name}' already exists. Dropping to recreate with compatible schema."
        )
        utility.drop_collection(collection_name, using=alias)

    # Get source collection schema
    source_schema = source_collection.schema

    # Convert source schema to target collection schema (keep PK with auto_id=False to preserve original IDs)
    fields = []
    for field in source_schema.fields:
        if field.is_primary:
            fields.append(
                FieldSchema(name=field.name, dtype=field.dtype, is_primary=True, auto_id=False)
            )
        else:
            fields.append(
                FieldSchema(
                    name=field.name, dtype=field.dtype, max_length=field.max_length, dim=field.dim
                )
            )

    target_schema = CollectionSchema(fields, description=f"Migrated from {source_collection.name}")
    target_collection = Collection(collection_name, target_schema, using=alias)

    # Create index (assuming same index params as source, or a default HNSW)
    # This part is simplified; ideally, you'd inspect source_collection.indexes[0].params
    vector_field_name = None
    for field in source_schema.fields:
        if field.dtype == DataType.FLOAT_VECTOR:
            vector_field_name = field.name
            break

    if vector_field_name:
        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",  # Assuming COSINE, adjust if source uses L2, IP, etc.
            "params": {"M": 16, "efConstruction": 256},
        }
        target_collection.create_index(field_name=vector_field_name, index_params=index_params)
        logger.info(
            f"Created HNSW index on '{vector_field_name}' for target collection '{collection_name}'."
        )

    target_collection.load()
    logger.info(f"Created and loaded target collection '{collection_name}' (alias: {alias}).")
    return target_collection


def migrate_collection():
    if not CLOUD_MILVUS_URI or not CLOUD_MILVUS_TOKEN:
        logger.error(
            "CLOUD_MILVUS_URI and CLOUD_MILVUS_TOKEN environment variables must be set for source connection."
        )
        return

    logger.info(
        f"Starting migration of collection '{SOURCE_COLLECTION_NAME}' from Cloud to Local Milvus."
    )

    # 1. Connect to Source Milvus (Cloud)
    connect_milvus("cloud_milvus", uri=CLOUD_MILVUS_URI, token=CLOUD_MILVUS_TOKEN)
    source_collection = get_milvus_collection("cloud_milvus", SOURCE_COLLECTION_NAME)

    # 2. Connect to Target Milvus (Local)
    connect_milvus("local_milvus", host=LOCAL_MILVUS_HOST, port=LOCAL_MILVUS_PORT)
    target_collection = create_target_collection_if_not_exists(
        "local_milvus", TARGET_COLLECTION_NAME, source_collection
    )

    # 3. Retrieve and Insert Data in Batches using offset-based iteration
    total_entities = source_collection.num_entities
    logger.info(f"Found {total_entities} entities in source collection '{SOURCE_COLLECTION_NAME}'.")

    if total_entities == 0:
        logger.info("No entities to migrate. Exiting.")
        return

    # Get target schema field names (excluding auto-generated PK)
    target_schema = target_collection.schema
    [
        f.name for f in target_schema.fields if not f.is_primary and not f.auto_id
    ]

    # Use target field names for querying and inserting (includes PK now)
    output_fields = [f.name for f in target_collection.schema.fields]

    migrated_count = 0
    for i in range(0, total_entities, BATCH_SIZE):
        # Use offset-based query instead of ID-based
        source_entities_batch = source_collection.query(
            expr="id >= 0",
            output_fields=output_fields,
            consistency_level="Strong",
            offset=i,
            limit=BATCH_SIZE,
        )

        if not source_entities_batch:
            logger.warning(f"No entities fetched for batch starting at offset {i}. Skipping.")
            continue

        # Prepare data for insertion into target
        # Milvus insert expects a list of lists, where each inner list corresponds to a field
        # e.g., [[field1_val1, field1_val2], [field2_val1, field2_val2]]

        # Prepare data in target schema field order
        target_fields = [f.name for f in target_collection.schema.fields]
        insert_lists = []
        for field in target_fields:
            values = [entity.get(field) for entity in source_entities_batch]
            insert_lists.append(values)

        try:
            target_collection.insert(insert_lists)
            target_collection.flush()
            migrated_count += len(insert_lists[0]) if insert_lists else 0
            logger.info(
                f"Migrated {len(insert_lists[0]) if insert_lists else 0} entities. Total migrated: {migrated_count}/{total_entities}."
            )
        except Exception as e:
            logger.error(f"Failed to insert batch of entities: {e}", exc_info=True)
            # Depending on desired behavior, could log and continue or re-raise

    logger.info(
        f"Migration completed. Total {migrated_count} entities migrated to local collection '{TARGET_COLLECTION_NAME}'."
    )


if __name__ == "__main__":
    migrate_collection()
