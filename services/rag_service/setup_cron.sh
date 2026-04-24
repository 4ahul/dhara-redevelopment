#!/bin/bash
# Dhara RAG - Cron Job Setup Script
# Run this to set up automated tasks

echo "Setting up Dhara RAG Cron Jobs..."
echo "=================================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
VENV_ACTIVATE="source venv/bin/activate"

# Cron jobs to add
CRON_JOBS="# Dhara RAG - Daily RERA Updates (9:00 AM)
0 9 * * * cd $SCRIPT_DIR && $VENV_ACTIVATE && python3 scripts/check_rera_updates.py >> logs/rera_updates.log 2>&1

# Dhara RAG - Check WhatsApp Compliance (Every hour)
0 * * * * cd $SCRIPT_DIR && $VENV_ACTIVATE && python3 scripts/check_whatsapp_compliance.py >> logs/whatsapp_compliance.log 2>&1

# Dhara RAG - Process Uploaded Documents (Every 15 minutes)
*/15 * * * * cd $SCRIPT_DIR && $VENV_ACTIVATE && python3 scripts/process_uploads.py >> logs/doc_processing.log 2>&1

# Dhara RAG - Weekly Compliance Summary (Sunday 10 AM)
0 10 * * 0 cd $SCRIPT_DIR && $VENV_ACTIVATE && python3 integrations/whatsapp_integration.py updates --days 7 >> logs/weekly_compliance.log 2>&1"

# Create cron.d file
CRON_FILE="/etc/cron.d/dhara_rag"

echo ""
echo "Cron jobs to be installed:"
echo "$CRON_JOBS"
echo ""

read -p "Do you want to install these cron jobs? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Option 1: Install system-wide cron.d
    if [ -d "/etc/cron.d" ] && [ -w "/etc/cron.d" ]; then
        echo "$CRON_JOBS" | sudo tee "$CRON_FILE" > /dev/null
        echo "✓ Installed to $CRON_FILE"
    else
        # Option 2: Install to user crontab
        echo "Installing to user crontab..."
        
        # Remove old Dhara RAG jobs first
        (crontab -l 2>/dev/null | grep -v "Dhara RAG"; echo "$CRON_JOBS") | crontab -
        
        echo "✓ Installed to user crontab"
    fi
    
    echo ""
    echo "✓ Cron jobs installed successfully!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep -A1 "Dhara RAG" || echo "(none)"
else
    echo "Installation cancelled."
fi

echo ""
echo "To manually run a cron job:"
echo "  python3 scripts/check_rera_updates.py"
echo "  python3 scripts/check_whatsapp_compliance.py"
echo "  python3 scripts/process_uploads.py"
