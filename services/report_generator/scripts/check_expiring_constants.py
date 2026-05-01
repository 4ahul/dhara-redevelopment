"""
Script to check for expiring hardcoded constants (RED fields) in Excel templates.
It reads from mappings YAML files and sends an email alert when constants are close to expiry,
so the admin can update the templates and reset the expiry date.
"""

import logging
import os
import smtplib
from datetime import UTC, datetime
from email.mime.text import MIMEText
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
MAPPINGS_DIR = HERE.parent / "mappings"


def send_alert_email(admin_email: str, alerts: list):
    """Send an email alert to the admin."""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USERNAME", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM_EMAIL", "noreply@dharaai.com")

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not configured. Skipping email alert.")
        for alert in alerts:
            logger.warning(f"ALERT: {alert}")
        return

    subject = "[Dhara AI] Action Required: Expiring Excel Template Constants"
    body = "The following hardcoded constants (RED fields) in your Excel templates are close to expiry or have expired:\n\n"
    for alert in alerts:
        body += f"- {alert}\n"

    body += "\nPlease update the respective Excel templates and reset the expiry dates in the mappings YAML files."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = admin_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Sent expiry alert email to {admin_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def main():
    admin_email = os.environ.get("SMTP_FROM_EMAIL", "admin@dharaai.com")
    today = datetime.now(UTC).date()
    alerts = []

    for yaml_file in MAPPINGS_DIR.glob("*.yaml"):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                mapping = yaml.safe_load(f)

            filename = mapping.get("template", yaml_file.name)
            cells = mapping.get("cells", [])

            for const in cells:
                if const.get("kind") == "red" and "expires_on" in const:
                    try:
                        exp_date_str = const["expires_on"]
                        # Handle potential datetime objects parsed by yaml
                        if isinstance(exp_date_str, datetime):
                            exp_date = exp_date_str.date()
                        elif hasattr(exp_date_str, "date"):  # handles datetime.date
                            exp_date = exp_date_str
                        else:
                            exp_date = datetime.strptime(str(exp_date_str), "%Y-%m-%d").date()

                        alert_days = const.get("alert_days_before", 60)
                        diff = (exp_date - today).days

                        if diff <= alert_days:
                            status = "EXPIRED" if diff < 0 else f"Expires in {diff} days"
                            desc = const.get("description", "Unknown constant")
                            alerts.append(
                                f"{filename} -> {const['cell']} ({desc}): {status} on {exp_date_str}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Invalid expiry date format for {filename} {const.get('cell')}: {e}"
                        )
        except Exception as e:
            logger.error(f"Failed to process {yaml_file}: {e}")

    if alerts:
        send_alert_email(admin_email, alerts)
    else:
        logger.info("All fixed constants are up to date.")


if __name__ == "__main__":
    main()
