#!/usr/bin/env bash
set -e

# Run the python installer using system python3
python3 "$(dirname "$0")/install.py" "$@"
