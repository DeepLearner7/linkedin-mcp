"""
Unit tests for MCP server tool registration and validation.
"""

import pytest
from linkedin_mcp.server import app, linkedin_create_post


def test_registered_tools():
    # Verify all expected tools are registered on the FastMCP/MCPServer instance
    registered_tool_names = list(app._tool_manager._tools.keys()) if hasattr(app, "_tool_manager") else []
    
    expected_tools = [
        "linkedin_status",
        "linkedin_get_safety_stats",
        "linkedin_browser_login",
        "linkedin_get_profile",
        "linkedin_create_post",
        "linkedin_search_feed_posts",
        "linkedin_search_posts",
        "linkedin_comment_on_post",
        "linkedin_search_people",
        "linkedin_send_connect_request",
        "linkedin_search_jobs",
        "linkedin_get_job_details",
    ]
    
    for tool_name in expected_tools:
        assert tool_name in registered_tool_names, f"Expected tool {tool_name} to be registered"


@pytest.mark.asyncio
async def test_create_post_empty_validation():
    res = await linkedin_create_post("")
    assert "Error: Post content cannot be empty" in res

    res_spaces = await linkedin_create_post("   ")
    assert "Error: Post content cannot be empty" in res_spaces
