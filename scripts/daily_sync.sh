#!/usr/bin/env bash
# ==============================================================================
# Daily LinkedIn Job & Post Scraper Sync
# Triggered via macOS crontab, launchd, or manual execution.
# Runs headless Antigravity (agy) to fetch, categorize, and store openings.
# ==============================================================================

set -euo pipefail

# Ensure standard user PATH is present for cron environments
export PATH="${HOME}/.gemini/antigravity-cli/bin:${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

# Dynamically resolve repository root and log path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${HOME}/.config/linkedin-mcp"
LOG_FILE="${DATA_DIR}/sync.log"

# Locate Antigravity CLI binary (PATH or standard user home location)
AGY_BIN="$(command -v agy || true)"
if [[ -z "${AGY_BIN}" && -x "${HOME}/.gemini/antigravity-cli/bin/agy" ]]; then
    AGY_BIN="${HOME}/.gemini/antigravity-cli/bin/agy"
fi

if [[ -z "${AGY_BIN}" || ! -x "${AGY_BIN}" ]]; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ERROR: Antigravity CLI (agy) binary not found." | tee -a "${LOG_FILE}"
    exit 1
fi

mkdir -p "${DATA_DIR}"
cd "${REPO_DIR}"

HEADER="========================================================\n[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting Daily LinkedIn Job Sync\nRunning in: ${REPO_DIR}\nLog file:   ${LOG_FILE}\n========================================================"

SYNC_PROMPT="Run daily sync: Search LinkedIn for all recent job openings and recruiter posts strictly within the last 7 days (date_posted: 'past-week', sort_by: 'date_posted') matching target roles ('Senior Data Engineer', 'Senior Data Platform Engineer', 'Data Engineering Lead') across locations 'Pune' and 'Bangalore'. Exhaustively retrieve all matching results across both the Job Board (paginating through all available listings for the past week) and Recruiter Feed Posts without truncating early. Filter out non-hiring noise and candidate self-promotions (#opentowork), parse and normalize each verified hiring opening into the deterministic schema, extract full tech stack skills, and save them into SQLite using linkedin_save_parsed_jobs. Provide a comprehensive summary of all newly added and updated jobs grouped by role and location."

if [[ -t 1 ]]; then
    # Interactive terminal: stream live output to terminal AND save to log file
    echo -e "${HEADER}" | tee -a "${LOG_FILE}"
    echo "Running headless Antigravity sync (this takes 1-2 minutes to search and parse LinkedIn)..."
    "${AGY_BIN}" -p "${SYNC_PROMPT}" --dangerously-skip-permissions 2>&1 | tee -a "${LOG_FILE}"
    echo -e "\n[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Finished Daily LinkedIn Job Sync successfully.\n========================================================" | tee -a "${LOG_FILE}"
else
    # Non-interactive / cron daemon mode: silently append everything to log file
    echo -e "${HEADER}" >> "${LOG_FILE}"
    "${AGY_BIN}" -p "${SYNC_PROMPT}" --dangerously-skip-permissions >> "${LOG_FILE}" 2>&1
    echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Finished Daily LinkedIn Job Sync successfully.\n========================================================" >> "${LOG_FILE}"
fi
