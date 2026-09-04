#!/usr/bin/env bash
# ==============================================================================
# Helper to configure the macOS crontab for daily LinkedIn scraping sync.
# ==============================================================================

set -euo pipefail

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/daily_sync.sh"
chmod +x "${SCRIPT_PATH}"

CRON_SCHEDULE="0 9 * * *" # Every day at 9:00 AM
CRON_COMMAND="${SCRIPT_PATH}"
CRON_LINE="${CRON_SCHEDULE} ${CRON_COMMAND}"

echo "=========================================================="
echo " Daily LinkedIn Job Sync Cron Setup"
echo "=========================================================="
echo "Target sync script: ${SCRIPT_PATH}"
echo "Scheduled frequency: Daily at 9:00 AM (${CRON_SCHEDULE})"
echo ""

# Check existing crontab
EXISTING_CRON=$(crontab -l 2>/dev/null || true)

if echo "${EXISTING_CRON}" | grep -Fq "${SCRIPT_PATH}"; then
    echo "✓ Daily sync job is ALREADY configured in your crontab:"
    echo "${EXISTING_CRON}" | grep -F "${SCRIPT_PATH}"
    exit 0
fi

echo "To install this schedule in your crontab, run:"
echo "  (crontab -l 2>/dev/null; echo \"${CRON_LINE}\") | crontab -"
echo ""

if [[ "${1:-}" == "--install" ]]; then
    (echo "${EXISTING_CRON}"; echo "${CRON_LINE}") | crontab -
    echo "✓ Successfully installed daily cron job in crontab!"
    crontab -l | grep -F "${SCRIPT_PATH}"
else
    echo "Run with --install to automatically register this schedule:"
    echo "  ./scripts/setup_cron.sh --install"
fi
echo "=========================================================="
