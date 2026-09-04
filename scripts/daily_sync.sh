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

# Locate Python / linkedin-jobs binary in virtual environment
PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(command -v python3 || true)"
fi

mkdir -p "${DATA_DIR}"
cd "${REPO_DIR}"

HEADER="========================================================\n[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting Daily LinkedIn Job Sync\nRunning in: ${REPO_DIR}\nLog file:   ${LOG_FILE}\n========================================================"

REPORT_FILE="${DATA_DIR}/latest_sync_report.md"

run_sync() {
    echo "==> [Stage 1/2] Fetching LinkedIn jobs via Boolean OR pipeline (Pune & Bangalore, past 7 days)..."
    "${PYTHON_BIN}" -m linkedin_mcp.pipeline.cli \
        --keywords "Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead" \
        --location "Pune, Bangalore" \
        --date-posted "past-week" \
        --limit 25 \
        --export markdown \
        --output "${REPORT_FILE}"

    if [[ -n "${AGY_BIN}" && -x "${AGY_BIN}" ]]; then
        echo -e "\n==> [Stage 2/2] Generating Antigravity AI Executive Briefing from stored jobs..."
        AGY_PROMPT="Analyze the latest LinkedIn job sync results stored in ${REPORT_FILE}. Produce a concise Executive Briefing for a Senior Data Engineering / Platform / Lead candidate in Pune & Bangalore:
1. Top high-signal job openings (company, role, location, easy-apply or recruiter link).
2. Key in-demand technical stack patterns (e.g., Spark, Kafka, Databricks, Snowflake, Cloud).
3. Direct recruiter contact leads (names, profiles, emails if available)."
        "${AGY_BIN}" -p "${AGY_PROMPT}" --dangerously-skip-permissions
    fi
}

if [[ -t 1 ]]; then
    # Interactive terminal: stream live output to terminal AND save to log file
    echo -e "${HEADER}" | tee -a "${LOG_FILE}"
    run_sync 2>&1 | tee -a "${LOG_FILE}"
    echo -e "\n[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Finished Daily LinkedIn Job Sync successfully.\n========================================================" | tee -a "${LOG_FILE}"
else
    # Non-interactive / cron daemon mode: silently append everything to log file
    echo -e "${HEADER}" >> "${LOG_FILE}"
    run_sync >> "${LOG_FILE}" 2>&1
    echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Finished Daily LinkedIn Job Sync successfully.\n========================================================" >> "${LOG_FILE}"
fi
