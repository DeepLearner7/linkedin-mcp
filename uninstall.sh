#!/usr/bin/env bash
# ==============================================================================
# One-command uninstaller for LinkedIn MCP server.
# Completely removes global registrations, crontab, virtualenv, and database.
# Usage:
#   ./uninstall.sh             # Preserves session.json
#   ./uninstall.sh --purge-all # Also removes session.json
# ==============================================================================
set -e

python3 "$(dirname "$0")/install.py" --uninstall "$@"
