#!/usr/bin/env python3
"""
Installer and MCP Registration script for LinkedIn MCP.

This script:
1. Sets up the Python virtual environment (.venv).
2. Installs the package in editable mode (pip install -e .).
3. Registers the server globally in ~/.gemini/config/mcp_config.json
   so it can be used by Antigravity (agy) from anywhere on the system.
4. Optionally registers in Claude Code (~/.claude.json).
"""

import sys
import os
import json
import subprocess
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
IS_WINDOWS = sys.platform.startswith("win")
VENV_BIN = VENV_DIR / ("Scripts" if IS_WINDOWS else "bin")
PYTHON_EXE = VENV_BIN / ("python.exe" if IS_WINDOWS else "python")
LINKEDIN_EXE = VENV_BIN / ("linkedin-mcp.exe" if IS_WINDOWS else "linkedin-mcp")
JOBS_CLI_EXE = VENV_BIN / ("linkedin-jobs.exe" if IS_WINDOWS else "linkedin-jobs")

ANTIGRAVITY_CONFIG_DIR = Path.home() / ".gemini" / "config"
ANTIGRAVITY_CONFIG_FILE = ANTIGRAVITY_CONFIG_DIR / "mcp_config.json"
CLAUDE_CONFIG_FILE = Path.home() / ".claude.json"
LOCAL_BIN_DIR = Path.home() / ".local" / "bin"
GLOBAL_JOBS_CLI = LOCAL_BIN_DIR / ("linkedin-jobs.exe" if IS_WINDOWS else "linkedin-jobs")


def run_command(cmd, cwd=REPO_ROOT):
    """Run a shell command and check for errors."""
    print(f"--> Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(cwd))


def ensure_venv():
    """Create virtual environment if it does not exist."""
    if not PYTHON_EXE.exists():
        print(f"Creating virtual environment in {VENV_DIR}...")
        run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print(f"Virtual environment already present at {VENV_DIR}")


def install_package():
    """Install dependencies and package in editable mode."""
    print("Installing linkedin-mcp in editable mode...")
    run_command([str(PYTHON_EXE), "-m", "pip", "install", "--upgrade", "pip", "setuptools"])
    run_command([str(PYTHON_EXE), "-m", "pip", "install", "-e", "."])
    print("Ensuring Playwright Chromium browser is installed...")
    run_command([str(PYTHON_EXE), "-m", "playwright", "install", "chromium"])
    
    # Expose global `linkedin-jobs` CLI command in ~/.local/bin
    if not IS_WINDOWS and JOBS_CLI_EXE.exists():
        try:
            LOCAL_BIN_DIR.mkdir(parents=True, exist_ok=True)
            if GLOBAL_JOBS_CLI.is_symlink() or GLOBAL_JOBS_CLI.exists():
                GLOBAL_JOBS_CLI.unlink()
            GLOBAL_JOBS_CLI.symlink_to(JOBS_CLI_EXE)
            print(f"Created global CLI shortcut: {GLOBAL_JOBS_CLI} -> {JOBS_CLI_EXE}")
        except Exception as e:
            print(f"Note: Could not symlink {GLOBAL_JOBS_CLI}: {e}")


def setup_env_file():
    """Create .env from .env.example if missing."""
    env_file = REPO_ROOT / ".env"
    example_file = REPO_ROOT / ".env.example"
    if not env_file.exists() and example_file.exists():
        print("Creating default .env file from .env.example...")
        env_file.write_text(example_file.read_text())
        print("Tip: Add your LINKEDIN_ACCESS_TOKEN to .env when ready.")


def register_antigravity():
    """Register server in Antigravity global mcp_config.json."""
    ANTIGRAVITY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    config = {}
    if ANTIGRAVITY_CONFIG_FILE.exists() and ANTIGRAVITY_CONFIG_FILE.stat().st_size > 0:
        try:
            with open(ANTIGRAVITY_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Warning: Could not parse existing {ANTIGRAVITY_CONFIG_FILE} ({e}). Starting fresh.")
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Prefer the console script executable, fallback to python -m
    command_path = str(LINKEDIN_EXE if LINKEDIN_EXE.exists() else PYTHON_EXE)
    args = [] if LINKEDIN_EXE.exists() else ["-m", "linkedin_mcp.server"]

    config["mcpServers"]["linkedin"] = {
        "command": command_path,
        "args": args,
        "env": {
            "PYTHONUNBUFFERED": "1"
        }
    }

    with open(ANTIGRAVITY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Successfully registered 'linkedin' in Antigravity config: {ANTIGRAVITY_CONFIG_FILE}")


def unregister():
    """Remove registration from configs."""
    if ANTIGRAVITY_CONFIG_FILE.exists():
        try:
            with open(ANTIGRAVITY_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" in config and "linkedin" in config["mcpServers"]:
                del config["mcpServers"]["linkedin"]
                with open(ANTIGRAVITY_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print("Removed 'linkedin' from Antigravity config.")
        except Exception as e:
            print(f"Error removing from Antigravity config: {e}")

    if CLAUDE_CONFIG_FILE.exists():
        try:
            with open(CLAUDE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" in config and "linkedin" in config["mcpServers"]:
                del config["mcpServers"]["linkedin"]
                with open(CLAUDE_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print("Removed 'linkedin' from Claude config.")
        except Exception as e:
            print(f"Error removing from Claude config: {e}")

    # Remove global CLI symlink
    if not IS_WINDOWS and (GLOBAL_JOBS_CLI.is_symlink() or GLOBAL_JOBS_CLI.exists()):
        try:
            GLOBAL_JOBS_CLI.unlink()
            print(f"Removed global CLI shortcut: {GLOBAL_JOBS_CLI}")
        except Exception as e:
            pass


def register_claude():
    """Register server in Claude Code (~/.claude.json) if requested."""
    config = {}
    if CLAUDE_CONFIG_FILE.exists() and CLAUDE_CONFIG_FILE.stat().st_size > 0:
        try:
            with open(CLAUDE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    command_path = str(LINKEDIN_EXE if LINKEDIN_EXE.exists() else PYTHON_EXE)
    args = [] if LINKEDIN_EXE.exists() else ["-m", "linkedin_mcp.server"]

    config["mcpServers"]["linkedin"] = {
        "command": command_path,
        "args": args,
        "env": {
            "PYTHONUNBUFFERED": "1"
        }
    }

    with open(CLAUDE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Successfully registered 'linkedin' in Claude config: {CLAUDE_CONFIG_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Install and configure LinkedIn MCP server globally.")
    parser.add_argument("--uninstall", action="store_true", help="Unregister the server globally")
    parser.add_argument("--claude", action="store_true", help="Also register in Claude Code ~/.claude.json")
    args = parser.parse_args()

    if args.uninstall:
        unregister()
        return

    print("==================================================")
    print("  Installing LinkedIn MCP Server (System-Wide)    ")
    print("==================================================")
    ensure_venv()
    install_package()
    setup_env_file()
    register_antigravity()

    if args.claude:
        register_claude()

    print("\nInstallation Complete!")
    print("--------------------------------------------------")
    print("The 'linkedin' MCP server is now registered globally.")
    print("You can run 'agy' from ANY directory and it will load this server.")
    print("Inside agy, type '/mcp' to verify connection and tools.")
    print("--------------------------------------------------")


if __name__ == "__main__":
    main()
