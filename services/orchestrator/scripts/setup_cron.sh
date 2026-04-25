#!/bin/bash

# Dhara AI — Orchestrator Cron Setup
# This script registers the database cleanup task to run daily.

# 1. Define the job (Runs at 3:00 AM every Sunday)
# Format: minute hour day_of_month month day_of_week command
CLEANUP_JOB="0 3 * * 0 cd /app && /usr/local/bin/python services/orchestrator/scripts/cleanup_logs.py --days 30 >> /var/log/cleanup.log 2>&1"

# 2. Add to crontab if not already present
(crontab -l 2>/dev/null | grep -F "cleanup_logs.py") || (crontab -l 2>/dev/null; echo "$CLEANUP_JOB") | crontab -

echo "✅ Database cleanup cron job registered (Daily at 03:00 AM)"
