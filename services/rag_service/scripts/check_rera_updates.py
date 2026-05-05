#!/usr/bin/env python3
"""
Daily Cron Job - Fetch RERA Updates
Run: Every day at 9:00 AM
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"rera_updates_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def check_rera_updates():
    """Check for new RERA registrations and updates"""
    logger.info("Starting RERA update check...")

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from services.rag_service.integrations.rera_integration import RERAIntegration

        rera = RERAIntegration()

        # Check sample registrations
        sample_registrations = [
            "P51800045641",  # Sample - replace with actual
        ]

        new_registrations = []

        for reg_no in sample_registrations:
            try:
                result = rera.verify_registration(reg_no)
                if result.get("valid"):
                    new_registrations.append(result)
                    logger.info(f"Found valid registration: {reg_no}")
            except Exception as e:
                logger.exception(f"Error checking {reg_no}: {e}")

        # Save results
        output_file = Path("data/compliance/rera_updates.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if output_file.exists():
            existing = json.loads(output_file.read_text())

        existing.append(
            {
                "checked_at": datetime.now().isoformat(),
                "registrations": new_registrations,
            }
        )

        output_file.write_text(json.dumps(existing, indent=2))

        logger.info(f"RERA check complete. Found {len(new_registrations)} valid registrations.")

    except Exception as e:
        logger.exception(f"RERA update check failed: {e}")
        raise


def send_alert(message: str):
    """Send alert (placeholder - implement email/Slack notification)"""
    logger.info(f"ALERT: {message}")


if __name__ == "__main__":
    try:
        check_rera_updates()
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Script failed: {e}")
        sys.exit(1)
