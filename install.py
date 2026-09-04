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
import shutil
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
DATA_DIR = Path.home() / ".config" / "linkedin-mcp"
LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.linkedin.mcp.sync.plist"


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
    run_command([str(PYTHON_EXE), "-m", "pip", "install", "-e", ".[test]"])
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


def unregister(purge_all: bool = False):
    """Completely uninstall and remove global registrations, schedules, and local environments."""
    print("==================================================")
    print("  Uninstalling LinkedIn MCP Server                ")
    print("==================================================")

    # 1. Antigravity MCP config
    if ANTIGRAVITY_CONFIG_FILE.exists():
        try:
            with open(ANTIGRAVITY_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" in config and "linkedin" in config["mcpServers"]:
                del config["mcpServers"]["linkedin"]
                with open(ANTIGRAVITY_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print("✓ Removed 'linkedin' from Antigravity config.")
        except Exception as e:
            print(f"Error removing from Antigravity config: {e}")

    # 2. Claude Code config
    if CLAUDE_CONFIG_FILE.exists():
        try:
            with open(CLAUDE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "mcpServers" in config and "linkedin" in config["mcpServers"]:
                del config["mcpServers"]["linkedin"]
                with open(CLAUDE_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print("✓ Removed 'linkedin' from Claude config.")
        except Exception as e:
            print(f"Error removing from Claude config: {e}")

    # 3. Global CLI shortcut
    if not IS_WINDOWS and (GLOBAL_JOBS_CLI.is_symlink() or GLOBAL_JOBS_CLI.exists()):
        try:
            GLOBAL_JOBS_CLI.unlink()
            print(f"✓ Removed global CLI shortcut: {GLOBAL_JOBS_CLI}")
        except Exception as e:
            pass

    # 4. Background crontab schedule
    if not IS_WINDOWS:
        try:
            res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if res.returncode == 0 and "daily_sync.sh" in res.stdout:
                lines = [line for line in res.stdout.splitlines() if "daily_sync.sh" not in line]
                new_cron = "\n".join(lines).strip()
                if new_cron:
                    subprocess.run(["crontab", "-"], input=new_cron + "\n", text=True, check=True)
                else:
                    subprocess.run(["crontab", "-r"], capture_output=True)
                print("✓ Removed daily_sync.sh from crontab.")
        except Exception as e:
            pass

    # 5. macOS LaunchAgent
    if not IS_WINDOWS and LAUNCHD_PLIST.exists():
        try:
            subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)], capture_output=True)
            LAUNCHD_PLIST.unlink(missing_ok=True)
            print("✓ Unloaded and removed macOS LaunchAgent.")
        except Exception as e:
            pass

    # 6. Isolated virtual environment (.venv)
    if VENV_DIR.exists():
        try:
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            print(f"✓ Removed virtual environment: {VENV_DIR}")
        except Exception as e:
            print(f"Warning removing .venv: {e}")

    # 7. SQLite database and log files
    if DATA_DIR.exists():
        if purge_all:
            try:
                shutil.rmtree(DATA_DIR, ignore_errors=True)
                print(f"✓ Purged entire data directory (including session): {DATA_DIR}")
            except Exception as e:
                print(f"Warning purging {DATA_DIR}: {e}")
        else:
            for f in ["jobs.db", "jobs.db-wal", "jobs.db-shm", "sync.log", "latest_sync_report.md", "candidate_feed_posts.json"]:
                target = DATA_DIR / f
                if target.exists():
                    target.unlink(missing_ok=True)
            print(f"✓ Removed SQLite database, staged posts, reports & sync logs from {DATA_DIR} (session.json preserved).")

    print("\nUninstallation Complete!")
    print("--------------------------------------------------")


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


def init_database():
    """Initialize the SQLite database with all tables and indexes."""
    print("Initializing SQLite database with schema tables...")
    run_command([
        str(PYTHON_EXE),
        "-c",
        "from linkedin_mcp.db.database import init_db, DEFAULT_DB_PATH; init_db(); print(f'Database successfully initialized at: {DEFAULT_DB_PATH}')"
    ])


def main():
    parser = argparse.ArgumentParser(description="Install and configure LinkedIn MCP server globally.")
    parser.add_argument("--uninstall", action="store_true", help="Completely uninstall, remove registrations, venv, and database")
    parser.add_argument("--purge-all", action="store_true", help="Also delete browser session.json when uninstalling")
    parser.add_argument("--claude", action="store_true", help="Also register in Claude Code ~/.claude.json")
    args = parser.parse_args()

    if args.uninstall:
        unregister(purge_all=args.purge_all)
        return

    print("==================================================")
    print("  Installing LinkedIn MCP Server (System-Wide)    ")
    print("==================================================")
    ensure_venv()
    install_package()
    init_database()
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
