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
CANDIDATE_POSTS_FILE="${DATA_DIR}/candidate_feed_posts.json"

run_sync() {
    echo "==> [Stage 1/2] Fetching LinkedIn Job Board & Staging Recruiter Feed Posts (Pune & Bangalore, past 7 days)..."
    "${PYTHON_BIN}" -m linkedin_mcp.pipeline.cli \
        --keywords "Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead" \
        --location "Pune, Bangalore" \
        --date-posted "past-week" \
        --limit 25 \
        --export markdown \
        --output "${REPORT_FILE}"

    if [[ -n "${AGY_BIN}" && -x "${AGY_BIN}" ]]; then
        echo -e "\n==> [Stage 2/2] Running Antigravity AI Semantic Post Classifier & Executive Briefing..."
        AGY_PROMPT="You are the AI Hiring & Recruiter Classifier for the daily LinkedIn sync.
1. Inspect the candidate recruiter feed posts stored in ${CANDIDATE_POSTS_FILE}.
2. For each post, perform semantic classification:
   - Determine whether the post author is actively HIRING for a Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead, or data team role in Pune or Bangalore.
   - Filter out non-hiring noise: job seekers (#opentowork, seeking opportunities), celebrating new roles, course advertisements, agency marketing, and general tech commentary.
   - For every verified hiring opening, extract: title (e.g. 'Senior Data Engineer (Recruiter Post)'), company, location, workplace_type ('remote', 'hybrid', 'onsite'), tech_stack (list of skills), posted_relative (preserve from candidate post e.g. '2 days ago'), hiring_contact_name, hiring_contact_profile, hiring_contact_email, and description_summary.
   - Call the MCP tool 'linkedin_save_parsed_jobs' with the verified jobs list to store them into SQLite.
3. Review the combined openings (Job Board from ${REPORT_FILE} and newly verified Recruiter posts).
4. Produce a high-value Executive Briefing:
   - Top High-Signal Opportunities (categorized into Leadership/Lead, Tier-1 Product/FinTech, and Scaleups with Easy Apply).
   - In-demand Technical Stack Patterns across the openings.
   - Direct Recruiter Contacts (names, profile links, and direct emails)."
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
