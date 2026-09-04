"""
Safety manager for LinkedIn MCP.
Tracks daily actions (comments, connection requests) to avoid triggering LinkedIn bot detection.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Dict, Any

CONFIG_DIR = Path.home() / ".config" / "linkedin-mcp"
STATS_FILE = CONFIG_DIR / "daily_stats.json"


def _get_max_comments() -> int:
    return int(os.getenv("LINKEDIN_MAX_DAILY_COMMENTS", "15"))


def _get_max_invites() -> int:
    return int(os.getenv("LINKEDIN_MAX_DAILY_INVITES", "10"))


def _get_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_stats() -> Dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not STATS_FILE.exists():
        return {"date": _get_today_str(), "comments": 0, "invites": 0}
    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        if data.get("date") != _get_today_str():
            # New day: reset counts
            return {"date": _get_today_str(), "comments": 0, "invites": 0}
        return data
    except Exception:
        return {"date": _get_today_str(), "comments": 0, "invites": 0}


def _save_stats(stats: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = STATS_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    tmp_file.replace(STATS_FILE)


def check_action_allowed(action_type: str) -> Tuple[bool, str]:
    """
    Check if an action (comment or invite) is permitted under daily safety limits.
    Returns (allowed: bool, reason: str).
    """
    stats = _load_stats()
    today = _get_today_str()

    if action_type == "comment":
        current = stats.get("comments", 0)
        limit = _get_max_comments()
        if current >= limit:
            return False, f"Daily limit reached for comments ({current}/{limit} on {today}). Safeguard triggered."
        return True, f"OK ({current + 1}/{limit} comments today)"

    elif action_type == "invite":
        current = stats.get("invites", 0)
        limit = _get_max_invites()
        if current >= limit:
            return False, f"Daily limit reached for connection requests ({current}/{limit} on {today}). Safeguard triggered."
        return True, f"OK ({current + 1}/{limit} connection requests today)"

    return True, "OK"


def record_action(action_type: str) -> Dict[str, Any]:
    """Record an action execution for today."""
    stats = _load_stats()
    if action_type == "comment":
        stats["comments"] = stats.get("comments", 0) + 1
    elif action_type == "invite":
        stats["invites"] = stats.get("invites", 0) + 1
    _save_stats(stats)
    return stats


def get_safety_stats() -> Dict[str, Any]:
    """Return dictionary of current safety stats and dynamic limits."""
    stats = _load_stats()
    return {
        "date": stats.get("date", _get_today_str()),
        "comments": stats.get("comments", 0),
        "max_comments": _get_max_comments(),
        "invites": stats.get("invites", 0),
        "max_invites": _get_max_invites(),
    }


def get_safety_summary() -> str:
    """Return a formatted status summary of daily actions."""
    data = get_safety_stats()
    return (
        f"Daily LinkedIn Safety Stats ({data['date']}):\n"
        f"  - Comments posted: {data['comments']} / {data['max_comments']}\n"
        f"  - Connection requests sent: {data['invites']} / {data['max_invites']}"
    )
