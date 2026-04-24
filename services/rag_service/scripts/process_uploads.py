#!/usr/bin/env python3
"""
Process Uploaded Documents
Run: Every 15 minutes
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"doc_processing_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def process_pending_uploads():
    """Process pending document uploads"""
    logger.info("Starting document processing...")

    try:
        uploads_dir = Path("data/uploads")
        processed_dir = Path("data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)

        processed_count = 0

        # Process property cards
        property_cards = uploads_dir / "property_cards"
        if property_cards.exists():
            for file in property_cards.glob("*"):
                if file.is_file():
                    logger.info(f"Processing: {file.name}")
                    # Move to processed
                    dest = processed_dir / "property_cards" / file.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    file.rename(dest)
                    processed_count += 1

        # Process 7-12 documents
        docs_7_12 = uploads_dir / "7_12"
        if docs_7_12.exists():
            for file in docs_7_12.glob("*"):
                if file.is_file():
                    logger.info(f"Processing 7-12: {file.name}")
                    dest = processed_dir / "7_12" / file.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    file.rename(dest)
                    processed_count += 1

        logger.info(f"Processed {processed_count} documents")

    except Exception as e:
        logger.error(f"Processing failed: {e}")


if __name__ == "__main__":
    process_pending_uploads()
