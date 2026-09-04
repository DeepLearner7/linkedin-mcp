#!/usr/bin/env python3
"""Convenience script to log into LinkedIn and save session."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
IS_WINDOWS = sys.platform.startswith("win")
VENV_PYTHON = REPO_ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")

# If running outside .venv and .venv exists, automatically re-exec with .venv python
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# Ensure src/ is in path
sys.path.insert(0, str(REPO_ROOT / "src"))

from linkedin_mcp.auth import main

if __name__ == "__main__":
    main()
