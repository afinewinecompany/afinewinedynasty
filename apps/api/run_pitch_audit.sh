#!/bin/bash
# Unix shell script to run pitch data audit
# Can be scheduled via cron job

echo "========================================"
echo "Running Pitch Data Audit"
echo "========================================"
echo

# Navigate to the API directory
cd /path/to/afinewinedynasty/apps/api

# Activate virtual environment if needed
# source venv/bin/activate

# Run the audit
python3 scheduled_pitch_audit.py --output ./audit_reports

# Check exit code
if [ $? -ne 0 ]; then
    echo
    echo "[WARNING] Audit reported issues. Check the reports."

    # Optionally trigger collection
    # python3 collect_missing_pitches_final.py
else
    echo
    echo "[OK] Audit completed successfully."
fi

echo
echo "Audit complete at $(date)"
echo "========================================"

# Example cron job entry (runs daily at 2 AM):
# 0 2 * * * /path/to/run_pitch_audit.sh >> /var/log/pitch_audit.log 2>&1