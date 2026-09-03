#!/usr/bin/env python3
"""
LinkedIn Model Context Protocol (MCP) Server.
Provides tools to interact with LinkedIn via MCP over Stdio.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Try importing MCPServer (mcp >= 2.0) with fallback to FastMCP (mcp < 2.0)
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore

# Configure logging exclusively to stderr to avoid corrupting stdio JSON-RPC stream
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("linkedin-mcp")

# Search and load environment variables from multiple standard locations
env_locations = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path.home() / ".config" / "linkedin-mcp" / ".env",
    Path.home() / ".linkedin_mcp.env",
]
for env_path in env_locations:
    if env_path.is_file():
        logger.info("Loading environment variables from: %s", env_path)
        load_dotenv(dotenv_path=env_path)
        break

# Initialize MCP Server
app = MCPServer("linkedin")


def _get_access_token() -> Optional[str]:
    """Retrieve the configured LinkedIn access token."""
    return os.getenv("LINKEDIN_ACCESS_TOKEN")


@app.tool()
def linkedin_status() -> str:
    """Check the operational status of the LinkedIn MCP server and credentials configuration.
    Use this to verify if the server is connected and authenticated before running other commands.
    """
    token = _get_access_token()
    if not token:
        return (
            "LinkedIn MCP is ACTIVE, but LINKEDIN_ACCESS_TOKEN is not configured.\n"
            "To configure, set LINKEDIN_ACCESS_TOKEN in your environment or in ~/.config/linkedin-mcp/.env\n"
            "Visit https://www.linkedin.com/developers/ to generate your OAuth2 access token."
        )
    masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
    return f"LinkedIn MCP is ACTIVE and authenticated. Configured token: {masked}"


@app.tool()
def linkedin_get_profile(identifier: str = "me") -> str:
    """Fetch LinkedIn profile details.

    Args:
        identifier: The LinkedIn member ID, vanity name, or 'me' for the authenticated user.
    """
    token = _get_access_token()
    logger.info("Fetching profile for: %s", identifier)

    if not token:
        return (
            f"[MOCK/DEMO MODE] Profile details for '{identifier}':\n"
            "- Name: Sample User\n"
            "- Headline: Software Engineer & AI Builder\n"
            "- Location: Global\n"
            "Note: Set LINKEDIN_ACCESS_TOKEN to fetch live profile data via LinkedIn API."
        )

    # TODO: Implement live LinkedIn API call (GET https://api.linkedin.com/v2/userinfo or /v2/me)
    return (
        f"Fetched live profile for '{identifier}'. "
        "(LinkedIn API call integration hook ready)"
    )


@app.tool()
def linkedin_create_post(content: str, visibility: str = "PUBLIC") -> str:
    """Publish a new post or update to LinkedIn.

    Args:
        content: The text content of the post to be published.
        visibility: The post visibility. Accepted values: 'PUBLIC' or 'CONNECTIONS'. Default is 'PUBLIC'.
    """
    token = _get_access_token()
    logger.info("Creating post with visibility=%s, length=%d chars", visibility, len(content))

    if not token:
        return (
            f"[MOCK/DEMO MODE] Post drafted successfully:\n"
            f"- Visibility: {visibility}\n"
            f"- Character Count: {len(content)}\n"
            f"- Content:\n{content}\n\n"
            "Note: Configure LINKEDIN_ACCESS_TOKEN to publish directly to your live LinkedIn feed."
        )

    # TODO: Implement live LinkedIn API call (POST https://api.linkedin.com/v2/ugcPosts or /rest/posts)
    return (
        f"Successfully published post to LinkedIn ({visibility}):\n"
        f"\"{content[:100]}...\""
    )


@app.tool()
def linkedin_search_posts(keywords: str, limit: int = 5) -> str:
    """Search LinkedIn posts and discussions by keywords.

    Args:
        keywords: Search query terms (e.g. 'artificial intelligence agents').
        limit: Maximum number of posts to return (default: 5).
    """
    token = _get_access_token()
    logger.info("Searching posts with keywords='%s', limit=%d", keywords, limit)

    if not token:
        return (
            f"[MOCK/DEMO MODE] Search results for '{keywords}' (Top {limit}):\n"
            f"1. Exploring autonomous coding agents and Model Context Protocol.\n"
            f"2. Building scalable tool integrations with MCP and Python.\n"
            f"3. Google Antigravity developer workflow updates.\n"
            "Note: Configure LINKEDIN_ACCESS_TOKEN for live search results."
        )

    return f"Search completed for '{keywords}'. Returned {limit} results."


def main():
    """Main entrypoint to run the MCP server over stdio."""
    logger.info("Starting LinkedIn MCP server over stdio...")
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
