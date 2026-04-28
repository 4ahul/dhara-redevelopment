#!/bin/bash
set -e

# Dhara AI — Orchestrator Cron Setup
# This script registers the database cleanup task to run weekly on Sundays at 3 AM.

CLEANUP_JOB="0 3 * * 0 cd /app && /usr/local/bin/python services/orchestrator/scripts/cleanup_logs.py --days 30 >> /var/log/cleanup.log 2>&1"

# Add to crontab if not already present
(crontab -l 2>/dev/null | grep -F "cleanup_logs.py") || (crontab -l 2>/dev/null; echo "$CLEANUP_JOB") | crontab -

echo "Database cleanup cron job registered (Weekly at Sunday 03:00 AM)"
