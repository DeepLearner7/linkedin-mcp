"""
Unit tests for LinkedIn MCP Safety Manager.
"""

import json
from unittest.mock import patch
from linkedin_mcp.safety import (
    check_action_allowed,
    record_action,
    get_safety_stats,
    get_safety_summary,
    _load_stats,
    _save_stats,
)


def test_safety_initial_state(tmp_path):
    fake_stats_file = tmp_path / "daily_stats.json"
    with patch("linkedin_mcp.safety.STATS_FILE", fake_stats_file), \
         patch("linkedin_mcp.safety.CONFIG_DIR", tmp_path):
        stats = get_safety_stats()
        assert stats["comments"] == 0
        assert stats["invites"] == 0
        assert stats["max_comments"] == 15
        assert stats["max_invites"] == 10


def test_check_action_allowed(tmp_path):
    fake_stats_file = tmp_path / "daily_stats.json"
    with patch("linkedin_mcp.safety.STATS_FILE", fake_stats_file), \
         patch("linkedin_mcp.safety.CONFIG_DIR", tmp_path), \
         patch("linkedin_mcp.safety._get_max_comments", return_value=2), \
         patch("linkedin_mcp.safety._get_max_invites", return_value=1):

        # Initial: allowed
        ok, reason = check_action_allowed("comment")
        assert ok is True
        assert "OK" in reason

        # Record 1 comment
        record_action("comment")
        ok, reason = check_action_allowed("comment")
        assert ok is True

        # Record 2nd comment -> limit reached
        record_action("comment")
        ok, reason = check_action_allowed("comment")
        assert ok is False
        assert "Daily limit reached for comments" in reason

        # Invite: allowed once
        ok, reason = check_action_allowed("invite")
        assert ok is True
        record_action("invite")

        # 2nd invite: blocked
        ok, reason = check_action_allowed("invite")
        assert ok is False
        assert "Daily limit reached for connection requests" in reason


def test_safety_date_reset(tmp_path):
    fake_stats_file = tmp_path / "daily_stats.json"
    fake_stats_file.write_text(json.dumps({
        "date": "2020-01-01",
        "comments": 15,
        "invites": 10
    }))

    with patch("linkedin_mcp.safety.STATS_FILE", fake_stats_file), \
         patch("linkedin_mcp.safety.CONFIG_DIR", tmp_path):
        stats = get_safety_stats()
        # Should reset because the date is old
        assert stats["comments"] == 0
        assert stats["invites"] == 0


def test_safety_summary_formatting(tmp_path):
    fake_stats_file = tmp_path / "daily_stats.json"
    with patch("linkedin_mcp.safety.STATS_FILE", fake_stats_file), \
         patch("linkedin_mcp.safety.CONFIG_DIR", tmp_path):
        summary = get_safety_summary()
        assert "Daily LinkedIn Safety Stats" in summary
        assert "Comments posted: 0 / 15" in summary
        assert "Connection requests sent: 0 / 10" in summary
