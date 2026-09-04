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
        "linkedin_save_parsed_jobs",
        "linkedin_query_stored_jobs",
        "linkedin_get_db_stats",
    ]
    
    for tool_name in expected_tools:
        assert tool_name in registered_tool_names, f"Expected tool {tool_name} to be registered"


@pytest.mark.asyncio
async def test_create_post_empty_validation():
    res = await linkedin_create_post("")
    assert "Error: Post content cannot be empty" in res

    res_spaces = await linkedin_create_post("   ")
    assert "Error: Post content cannot be empty" in res_spaces


def test_db_tools_execution():
    from linkedin_mcp.server import (
        linkedin_save_parsed_jobs,
        linkedin_query_stored_jobs,
        linkedin_get_db_stats,
    )

    sample_jobs = [
        {
            "title": "Senior Data Engineer",
            "company": "ContractTest Co",
            "location": "Pune, India",
            "source_type": "job_board",
            "source_url": "https://www.linkedin.com/jobs/view/999999/",
            "tech_stack": ["Spark", "Python"],
            "description_summary": "Testing MCP server save tool.",
        }
    ]

    save_result = linkedin_save_parsed_jobs(sample_jobs, source_name="contract_test")
    assert "LinkedIn Job Storage Sync" in save_result
    assert "Total Processed: 1" in save_result

    query_result = linkedin_query_stored_jobs(keywords="ContractTest")
    assert "ContractTest Co" in query_result
    assert "Senior Data Engineer" in query_result

    stats_result = linkedin_get_db_stats()
    assert "LinkedIn Job Storage Statistics" in stats_result
    assert "Total Stored Jobs:" in stats_result

