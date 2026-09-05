"""
Settings management for LinkedIn MCP UI and AI Copilot.
Stores user preferences, resume profile, and API configuration in ~/.config/linkedin-mcp/settings.json.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

SETTINGS_DIR = Path.home() / ".config" / "linkedin-mcp"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT_PROFILE = (
    "Lead / Senior Data Engineer with 10+ years of experience in distributed systems, "
    "real-time event streaming, and cloud data platforms.\n"
    "Core Skills: Apache Spark (PySpark), Apache Kafka, Python, SQL, AWS (S3, EMR, Athena, Glue), "
    "Databricks, Snowflake, Airflow, Data Modeling, Lakehouse architecture (Delta Lake / Iceberg).\n"
    "Location Preferences: Pune (Hybrid / Onsite), Bangalore, Remote."
)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "llm_provider": "gemini",
    "gemini_api_key": "",
    "gemini_model": "gemini-3.6-flash",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.1",
    "user_profile": DEFAULT_PROFILE,
}



def load_settings() -> Dict[str, Any]:
    """Load settings from JSON file or fall back to defaults and env vars."""
    settings = dict(DEFAULT_SETTINGS)

    # Check env vars first
    env_gemini_key = os.getenv("GEMINI_API_KEY", "")
    if env_gemini_key:
        settings["gemini_api_key"] = env_gemini_key

    env_provider = os.getenv("LLM_PROVIDER", "")
    if env_provider:
        settings["llm_provider"] = env_provider

    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass

    # If env var provided, it can override empty saved key
    if not settings.get("gemini_api_key") and env_gemini_key:
        settings["gemini_api_key"] = env_gemini_key

    return settings


def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Persist settings to ~/.config/linkedin-mcp/settings.json."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    current = load_settings()
    current.update(new_settings)

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    return current
