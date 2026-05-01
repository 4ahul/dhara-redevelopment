#!/usr/bin/env python3
"""
WhatsApp Business API Integration
For receiving compliance updates from government groups
"""

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
WHATSAPP_DIR = DATA_DIR / "whatsapp"
WHATSAPP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = WHATSAPP_DIR / "messages.db"


@dataclass
class WhatsAppMessage:
    """WhatsApp message structure"""

    message_id: str
    sender: str
    sender_name: str
    message: str
    timestamp: datetime
    group_name: str = ""
    is_compliance: bool = False
    compliance_category: str = ""
    processed: bool = False


@dataclass
class ComplianceUpdate:
    """Extracted compliance update"""

    title: str
    description: str
    source: str
    date: str
    category: str  # rera, dcpr, fire, environment, mc gm
    urgency: str = "normal"  # urgent, normal, low
    action_required: bool = False
    url: str = ""
    raw_text: str = ""


class WhatsAppIntegration:
    """
    WhatsApp Business API Integration

    Setup Instructions:
    1. Get WhatsApp Business API credentials from Meta
    2. Set environment variables:
       - WHATSAPP_PHONE_NUMBER_ID
       - WHATSAPP_ACCESS_TOKEN
       - WHATSAPP_WEBHOOK_VERIFY_TOKEN
    """

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self):
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "dhara_verify_token")

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        self.db_init()
        self.compliance_patterns = self._init_compliance_patterns()

    def db_init(self):
        """Initialize SQLite database for messages"""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                sender TEXT,
                sender_name TEXT,
                message TEXT,
                timestamp DATETIME,
                group_name TEXT,
                is_compliance BOOLEAN,
                compliance_category TEXT,
                processed BOOLEAN
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS compliance_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                source TEXT,
                date TEXT,
                category TEXT,
                urgency TEXT,
                action_required BOOLEAN,
                url TEXT,
                raw_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _init_compliance_patterns(self) -> list[tuple]:
        """Initialize regex patterns for compliance detection"""
        return [
            # MahaRERA patterns
            (
                r"(?i)(maharera|maha\s*rera).*?(circular|order|notification)\s*[:\-]?\s*(.+)",
                "rera",
                "high",
            ),
            (r"(?i)(rera).*?(deemed\s*conveyance)\s*[:\-]?\s*(.+)", "rera", "high"),
            # DCPR/Regulations
            (
                r"(?i)(DCPR|mumbai).*?(regulation|amendment|rule)\s*[:\-]?\s*(.+)",
                "dcpr",
                "normal",
            ),
            (
                r"(?i)(FSI|FAR|building\s*permission).*?(changed|amended|new)\s*[:\-]?\s*(.+)",
                "dcpr",
                "high",
            ),
            # MCGM
            (
                r"(?i)(mcgm|municipal).*?(notice|order|amendment)\s*[:\-]?\s*(.+)",
                "mcgm",
                "normal",
            ),
            (
                r"(?i)(building\s*plan|oc\s*certificate|noc).*?(new|amended|required)\s*[:\-]?\s*(.+)",
                "mcgm",
                "high",
            ),
            # Government
            (
                r"(?i)(govt|government|maharashtra).*?(notification|order)\s*[:\-]?\s*(.+)",
                "government",
                "normal",
            ),
            # Fire Safety
            (
                r"(?i)fire.*?(safety|noc|rule).*?(new|amended)\s*[:\-]?\s*(.+)",
                "fire",
                "high",
            ),
            # Environment
            (
                r"(?i)(environment|eco).*?(clearance|noc|rule).*?(new|amended)\s*[:\-]?\s*(.+)",
                "environment",
                "normal",
            ),
            # Effective date mentions
            (
                r"(?i)(effective|from)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*[:\-]?\s*(.+)",
                "effective_date",
                "high",
            ),
            # Deadline mentions
            (
                r"(?i)(deadline|last\s*date|submission).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*[:\-]?\s*(.+)",
                "deadline",
                "high",
            ),
        ]

    def process_message(
        self, message: str, sender: str = "", sender_name: str = "", timestamp: str = ""
    ) -> ComplianceUpdate | None:
        """Process a message and extract compliance if found"""

        for pattern, category, urgency in self.compliance_patterns:
            match = re.search(pattern, message, re.I)

            if match:
                groups = match.groups()

                # Extract title
                title = ""
                for g in reversed(groups):
                    if g and len(g.strip()) > 10:
                        title = g.strip()[:100]
                        break

                # Extract date
                date_match = re.search(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}", message)
                date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")

                # Extract URL if present
                url_match = re.search(r"https?://[^\s]+", message)
                url = url_match.group(0) if url_match else ""

                # Determine if action required
                action_keywords = [
                    "submit",
                    "apply",
                    "deadline",
                    "last date",
                    "immediate",
                    "urgent",
                ]
                action_required = any(kw in message.lower() for kw in action_keywords)

                return ComplianceUpdate(
                    title=title or f"{category.upper()} Update",
                    description=message.strip(),
                    source=f"WhatsApp - {sender_name or sender}",
                    date=date,
                    category=category,
                    urgency=urgency,
                    action_required=action_required,
                    url=url,
                    raw_text=message,
                )

        return None

    def save_message(self, message: WhatsAppMessage):
        """Save message to database"""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()

        c.execute(
            """
            INSERT OR REPLACE INTO messages
            (message_id, sender, sender_name, message, timestamp, group_name,
             is_compliance, compliance_category, processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                message.message_id,
                message.sender,
                message.sender_name,
                message.message,
                message.timestamp.isoformat(),
                message.group_name,
                message.is_compliance,
                message.compliance_category,
                message.processed,
            ),
        )

        conn.commit()
        conn.close()

    def save_compliance(self, compliance: ComplianceUpdate):
        """Save compliance update to database"""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO compliance_updates
            (title, description, source, date, category, urgency,
             action_required, url, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                compliance.title,
                compliance.description,
                compliance.source,
                compliance.date,
                compliance.category,
                compliance.urgency,
                compliance.action_required,
                compliance.url,
                compliance.raw_text,
            ),
        )

        conn.commit()
        conn.close()

        return c.lastrowid

    def import_from_file(self, file_path: str) -> int:
        """
        Import messages from WhatsApp chat export

        WhatsApp export format:
        "1/15/2024, 9:30 AM - Sender Name: Message"
        """
        count = 0

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Pattern for WhatsApp export format
        pattern = r"(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2})\s*(AM|PM)?\s*-\s*([^+]+?):\s*(.+?)(?=\n\d{1,2}/\d{1,2}/\d{2,4},|$)"

        matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            date_str, time_str, ampm, sender, message = match

            # Parse timestamp
            timestamp_str = f"{date_str} {time_str} {ampm or ''}"
            try:
                timestamp = datetime.strptime(timestamp_str.strip(), "%m/%d/%Y %I:%M %p")
            except Exception:
                timestamp = datetime.now()

            # Create message
            msg = WhatsAppMessage(
                message_id=f"import_{count}_{int(timestamp.timestamp())}",
                sender="",
                sender_name=sender.strip(),
                message=message.strip(),
                timestamp=timestamp,
                group_name="Imported",
                is_compliance=False,
            )

            # Check for compliance
            compliance = self.process_message(
                msg.message, sender=msg.sender, sender_name=msg.sender_name
            )

            if compliance:
                msg.is_compliance = True
                msg.compliance_category = compliance.category
                self.save_compliance(compliance)

            self.save_message(msg)
            count += 1

        return count

    def get_pending_compliances(self, days: int = 7) -> list[ComplianceUpdate]:
        """Get recent compliance updates"""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).isoformat()

        c.execute(
            """
            SELECT title, description, source, date, category, urgency,
                   action_required, url, raw_text
            FROM compliance_updates
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """,
            (since,),
        )

        results = []
        for row in c.fetchall():
            results.append(
                ComplianceUpdate(
                    title=row[0],
                    description=row[1],
                    source=row[2],
                    date=row[3],
                    category=row[4],
                    urgency=row[5],
                    action_required=bool(row[6]),
                    url=row[7],
                    raw_text=row[8],
                )
            )

        conn.close()
        return results

    def get_action_required(self) -> list[ComplianceUpdate]:
        """Get compliances requiring action"""
        return [c for c in self.get_pending_compliances() if c.action_required]

    # WhatsApp Cloud API Methods
    def send_message(self, to: str, message: str) -> dict:
        """Send WhatsApp message"""
        if not self.phone_number_id or not self.access_token:
            return {"error": "WhatsApp API not configured"}

        try:
            url = f"{self.BASE_URL}/{self.phone_number_id}/messages"

            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": message},
            }

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            return {"error": str(e)}

    def send_template(self, to: str, template_name: str, components: dict = None) -> dict:
        """Send WhatsApp template message"""
        if not self.phone_number_id or not self.access_token:
            return {"error": "WhatsApp API not configured"}

        try:
            url = f"{self.BASE_URL}/{self.phone_number_id}/messages"

            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {"name": template_name, "language": {"code": "en"}},
            }

            if components:
                payload["template"]["components"] = components

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            return {"error": str(e)}

    def verify_webhook(self, mode: str, token: str, challenge: str) -> bool:
        """Verify webhook for WhatsApp API"""
        return mode == "subscribe" and token == self.verify_token


def main():
    """CLI for WhatsApp integration"""
    import argparse

    parser = argparse.ArgumentParser(description="WhatsApp Compliance Integration")
    subparsers = parser.add_subparsers(dest="cmd")

    # Import from file
    import_parser = subparsers.add_parser("import", help="Import WhatsApp chat export")
    import_parser.add_argument("file", help="Path to chat export file")

    # Get updates
    updates_parser = subparsers.add_parser("updates", help="Get compliance updates")
    updates_parser.add_argument("--days", type=int, default=7, help="Days to look back")
    updates_parser.add_argument(
        "--action-required",
        action="store_true",
        help="Only show items requiring action",
    )

    # Send test message
    send_parser = subparsers.add_parser("send", help="Send WhatsApp message")
    send_parser.add_argument("to", help="Recipient phone number")
    send_parser.add_argument("message", help="Message to send")

    args = parser.parse_args()

    whatsapp = WhatsAppIntegration()

    if args.cmd == "import":
        logger.info(f"Importing from {args.file}...")
        count = whatsapp.import_from_file(args.file)
        logger.info(f"Imported {count} messages")

    elif args.cmd == "updates":
        if args.action_required:
            updates = whatsapp.get_action_required()
            logger.info(f"\n{len(updates)} updates requiring action:\n")
        else:
            updates = whatsapp.get_pending_compliances(args.days)
            logger.info(f"\n{len(updates)} compliance updates (last {args.days} days):\n")

        for i, u in enumerate(updates, 1):
            logger.info(f"{i}. [{u.category.upper()}] {u.title[:60]}")
            logger.info(f"   Date: {u.date} | Urgency: {u.urgency}")
            if u.action_required:
                logger.warning("   ⚠️ ACTION REQUIRED")
            logger.info("")

    elif args.cmd == "send":
        result = whatsapp.send_message(args.to, args.message)
        logger.info(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
