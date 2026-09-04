#!/usr/bin/env python3
"""Convenience script to log into LinkedIn and save session."""
import sys
from pathlib import Path

# Ensure src/ is in path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from linkedin_mcp.auth import main

if __name__ == "__main__":
    main()
