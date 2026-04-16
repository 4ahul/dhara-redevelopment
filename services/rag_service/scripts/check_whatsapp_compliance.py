#!/usr/bin/env python3
"""
Check WhatsApp Compliance Updates
Run: Every hour
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"whatsapp_compliance_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def check_whatsapp_compliance():
    """Check for new compliance updates from WhatsApp"""
    logger.info("Checking WhatsApp compliance updates...")

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from integrations.whatsapp_integration import WhatsAppIntegration

        whatsapp = WhatsAppIntegration()

        # Check for pending updates
        pending = whatsapp.get_pending_compliances(days=1)

        # Filter urgent ones
        urgent = [u for u in pending if u.urgency == "high" or u.action_required]

        if urgent:
            logger.info(f"Found {len(urgent)} urgent compliance updates:")
            for u in urgent:
                logger.info(f"  - [{u.category.upper()}] {u.title[:60]}")

            # Send alert
            send_alert(urgent)
        else:
            logger.info("No urgent updates found")

        return len(urgent)

    except Exception as e:
        logger.error(f"WhatsApp check failed: {e}")
        return 0


def send_alert(updates):
    """Send alert for urgent updates"""
    message = f"🚨 Urgent Compliance Updates ({len(updates)}):\n\n"
    for u in updates[:5]:  # Limit to 5
        message += f"• {u.title[:60]}\n"
        message += f"  Date: {u.date} | Category: {u.category}\n"
        if u.action_required:
            message += "  ⚠️ ACTION REQUIRED\n"
        message += "\n"

    logger.info(f"Alert prepared: {len(updates)} urgent updates")

    # TODO: Implement actual notification
    # Options: Email, Slack, WhatsApp message, SMS
    print(f"\n[ALERT]\n{message}")


if __name__ == "__main__":
    count = check_whatsapp_compliance()
    sys.exit(0 if count == 0 else 1)
