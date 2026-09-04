"""
Actions package for LinkedIn MCP.
"""

from linkedin_mcp.actions.posts import search_feed_posts, add_comment_to_post
from linkedin_mcp.actions.people import search_people, send_connection_request
from linkedin_mcp.actions.jobs import search_job_board, get_job_details

__all__ = [
    "search_feed_posts",
    "add_comment_to_post",
    "search_people",
    "send_connection_request",
    "search_job_board",
    "get_job_details",
]
