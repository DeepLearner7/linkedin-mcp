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

echo "========================================================" >> "${LOG_FILE}"
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting Daily LinkedIn Job Sync" >> "${LOG_FILE}"
echo "Running in: ${REPO_DIR}" >> "${LOG_FILE}"
echo "========================================================" >> "${LOG_FILE}"

SYNC_PROMPT="Run daily sync: Search LinkedIn for recent openings (past-24h to past-week) matching 'Senior Data Engineer' in 'Pune' on both the Job Board and Feed Posts. Filter out non-hiring noise, parse and normalize each relevant hiring opening into the deterministic schema, and save them using linkedin_save_parsed_jobs. Provide a concise summary of newly added and updated jobs."

# Execute headless Antigravity CLI with auto-permission approval
"${AGY_BIN}" -p "${SYNC_PROMPT}" --dangerously-skip-permissions >> "${LOG_FILE}" 2>&1

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Finished Daily LinkedIn Job Sync successfully." >> "${LOG_FILE}"
echo "========================================================" >> "${LOG_FILE}"
