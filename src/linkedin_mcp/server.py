#!/usr/bin/env python3
"""
LinkedIn Model Context Protocol (MCP) Server.
Provides tools to interact with LinkedIn via Playwright automation and MCP over Stdio.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# MCPServer (mcp >= 2.0)
from mcp.server.mcpserver import MCPServer

from linkedin_mcp.browser import (
    launch_stealth_context,
    has_saved_session,
    is_authenticated,
    human_delay,
    SESSION_FILE,
)
from linkedin_mcp.actions.posts import search_feed_posts, add_comment_to_post
from linkedin_mcp.actions.people import search_people, send_connection_request
from linkedin_mcp.safety import get_safety_summary, get_safety_stats, check_action_allowed
from linkedin_mcp.auth import run_interactive_login

# Configure logging exclusively to stderr to avoid corrupting stdio JSON-RPC stream
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("linkedin-mcp")

# Search and load environment variables
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


def _check_browser_auth() -> str:
    if has_saved_session():
        return f"Browser session ACTIVE (Saved at {SESSION_FILE})"
    return "Browser session NOT CONFIGURED (Run `python login.py` to authenticate)"


@app.tool()
def linkedin_status() -> str:
    """Check the operational status of LinkedIn MCP server, credentials, browser session, and daily safety stats."""
    token = _get_access_token()
    token_status = (
        f"Configured (Token: {token[:6]}...{token[-4:]})"
        if (token and len(token) > 10)
        else ("Configured" if token else "Not set")
    )
    browser_status = _check_browser_auth()
    safety_info = get_safety_summary()

    return (
        "=== LinkedIn MCP Status ===\n"
        f"• Status: ACTIVE\n"
        f"• REST API Token: {token_status}\n"
        f"• Playwright Session: {browser_status}\n\n"
        f"{safety_info}\n"
        "==========================="
    )


@app.tool()
def linkedin_get_safety_stats() -> str:
    """Check the daily limits and remaining actions for comments and connection requests."""
    return get_safety_summary()


@app.tool()
async def linkedin_browser_login(timeout_seconds: int = 180) -> str:
    """Launch a visible Chromium browser window on your desktop to log into LinkedIn.
    Once you log in and reach your feed, session cookies are automatically saved for all future automation.

    Args:
        timeout_seconds: Maximum time in seconds to wait for login completion (default: 180).
    """
    logger.info("Starting browser login helper (timeout=%ds)...", timeout_seconds)
    success = await run_interactive_login(timeout_seconds=timeout_seconds)
    if success:
        return (
            "Successfully logged into LinkedIn!\n"
            f"Session saved to: {SESSION_FILE}\n"
            "You can now search posts, post comments, and send connection requests."
        )
    return "Login process timed out or was closed before reaching the LinkedIn feed."


async def _fetch_profile_via_browser(identifier: str) -> str:
    handle = identifier.strip().strip("/").split("/")[-1]
    url = f"https://www.linkedin.com/in/{handle}/"
    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()
        try:
            logger.info("Navigating to member profile: %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector("main section", timeout=12000)
            except Exception:
                await human_delay(2.0, 3.5)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            main = soup.select_one("main")

            name = handle
            headline = ""
            location = ""
            about = ""

            if main:
                strings = [s.strip() for s in main.stripped_strings if s.strip()]
                if strings:
                    name = strings[0]

                filtered = []
                for s in strings[1:]:
                    if s.lower() in ["he/him", "she/her", "they/them", "·", "contact info", "connect", "message", "more"]:
                        continue
                    if s.startswith("·") or s.startswith("•"):
                        continue
                    filtered.append(s)

                if len(filtered) > 0:
                    headline = filtered[0]
                if len(filtered) > 1 and any(kw in filtered[1] for kw in ["India", "Area", "District", "Division", "City", "State", "United States", ","]):
                    location = filtered[1]

                about_h2 = main.find(lambda t: t.name in ["h2", "span"] and t.get_text(strip=True) == "About")
                if about_h2:
                    parent_sec = about_h2.find_parent("section")
                    if parent_sec and not parent_sec.find_parent("footer"):
                        txt = parent_sec.get_text(separator=" ", strip=True)
                        clean = re.sub(r"^About\s*", "", txt)
                        clean = re.sub(r"\s*…\s*(see\s*more|more).*$", "", clean, flags=re.IGNORECASE)
                        # Check that it's not footer text
                        if "accessibility" not in clean.lower():
                            about = clean[:800]

            output = [
                f"LinkedIn Profile: {name}",
                f"• Profile URL: {url}",
                f"• Headline: {headline or 'Not specified'}",
                f"• Location: {location or 'Not specified'}",
            ]
            if about:
                output.append(f"• About:\n{about[:800]}")
            return "\n".join(output)
        except Exception as e:
            logger.error("Error scraping profile via browser: %s", e)
            return f"Error loading profile for '{identifier}': {str(e)}"
        finally:
            await browser.close()


@app.tool()
async def linkedin_get_profile(identifier: str = "me") -> str:
    """Fetch LinkedIn profile details.

    Args:
        identifier: The LinkedIn member ID, vanity name, or 'me' for the authenticated user.
    """
    logger.info("Fetching profile for: %s", identifier)
    token = _get_access_token()

    # Case 1: Authenticated user's profile
    if identifier.strip().lower() in ("me", "self"):
        if not token:
            return (
                "[MOCK/DEMO MODE] Authenticated Profile details:\n"
                "- Name: Sample User\n"
                "- Headline: Software Engineer & AI Builder\n"
                "- Location: Global\n"
                "Note: Set LINKEDIN_ACCESS_TOKEN in .env to fetch live profile data via LinkedIn API."
            )
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15.0
                )
                if res.status_code == 200:
                    info = res.json()
                    name = info.get("name") or f"{info.get('given_name', '')} {info.get('family_name', '')}".strip()
                    sub = info.get("sub", "Unknown")
                    email = info.get("email", "Not provided")
                    locale = info.get("locale", {})
                    locale_str = f"{locale.get('language', 'en')}_{locale.get('country', 'US')}" if isinstance(locale, dict) else str(locale)
                    return (
                        f"Authenticated LinkedIn Profile (Self):\n"
                        f"• Name: {name}\n"
                        f"• Member ID (sub): {sub}\n"
                        f"• Profile URN: urn:li:person:{sub}\n"
                        f"• Email: {email}\n"
                        f"• Locale: {locale_str}\n"
                        f"• Token Status: Active"
                    )
                return f"LinkedIn API error (HTTP {res.status_code}): {res.text}"
        except Exception as e:
            logger.error("Error fetching self profile: %s", e)
            return f"Error while querying LinkedIn userinfo API: {str(e)}"

    # Case 2: Third-party profile
    if has_saved_session():
        return await _fetch_profile_via_browser(identifier)

    return (
        f"To fetch live profile details for '{identifier}', a browser session is required.\n"
        "Please run `python login.py` to authenticate and save your session."
    )


@app.tool()
async def linkedin_create_post(content: str, visibility: str = "PUBLIC") -> str:
    """Publish a new post or update to LinkedIn.

    Args:
        content: The text content of the post to be published.
        visibility: The post visibility. Accepted values: 'PUBLIC' or 'CONNECTIONS'. Default is 'PUBLIC'.
    """
    token = _get_access_token()
    clean_content = content.strip()
    if not clean_content:
        return "Error: Post content cannot be empty."

    norm_visibility = "PUBLIC" if visibility.upper() == "PUBLIC" else "CONNECTIONS"

    if not token:
        return (
            f"[MOCK/DEMO MODE] Post drafted successfully:\n"
            f"- Visibility: {norm_visibility}\n"
            f"- Character Count: {len(clean_content)}\n"
            f"- Content:\n{clean_content}\n\n"
            "Note: Configure LINKEDIN_ACCESS_TOKEN in .env to publish directly to your live LinkedIn feed."
        )

    logger.info("Publishing post via LinkedIn REST API (visibility=%s, length=%d)", norm_visibility, len(clean_content))
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch user URN via userinfo
            userinfo_res = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15.0
            )
            if userinfo_res.status_code != 200:
                return f"Failed to retrieve user URN from LinkedIn API (HTTP {userinfo_res.status_code}): {userinfo_res.text}"

            sub = userinfo_res.json().get("sub")
            if not sub:
                return "Failed to determine author URN: 'sub' missing from userinfo response."

            author_urn = f"urn:li:person:{sub}"

            # 2. Publish post via ugcPosts endpoint
            payload = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": clean_content},
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": norm_visibility
                }
            }

            post_res = await client.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=20.0
            )

            if post_res.status_code in (200, 201):
                res_data = post_res.json()
                post_id = res_data.get("id", "")
                post_url = f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "https://www.linkedin.com/feed/"
                return (
                    f"Successfully published post to LinkedIn ({norm_visibility})!\n"
                    f"• Post URN: {post_id}\n"
                    f"• Feed URL: {post_url}\n"
                    f"• Preview: \"{clean_content[:120]}...\""
                )
            else:
                return f"LinkedIn API failed to publish post (HTTP {post_res.status_code}): {post_res.text}"

    except Exception as e:
        logger.error("Error publishing post: %s", e)
        return f"Error while publishing post to LinkedIn: {str(e)}"


@app.tool()
async def linkedin_search_feed_posts(
    keywords: str,
    limit: int = 5,
    sort_by: str = "date_posted",
    date_posted: str = "past-week",
) -> str:
    """Search LinkedIn posts and discussions by keywords, returning engagement metrics (likes, comments) and post links.

    Args:
        keywords: Search query terms (e.g. 'Hiring senior data engineer', 'AI agents').
        limit: Maximum number of posts to return (default: 5).
        sort_by: Sorting order: 'date_posted' (most recent) or 'relevance'.
        date_posted: Filter by date: 'past-24h', 'past-week', 'past-month'.
    """
    if not has_saved_session():
        return (
            "LinkedIn browser session is not configured.\n"
            "To authenticate, please run the login script in your terminal:\n"
            "   python login.py\n"
            "This will open a browser window to log in and save your session."
        )

    logger.info("Searching feed posts for '%s' (limit=%d, sort=%s, date=%s)", keywords, limit, sort_by, date_posted)
    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()
        try:
            posts = await search_feed_posts(
                page=page,
                keywords=keywords,
                limit=limit,
                sort_by=sort_by,
                date_posted=date_posted,
            )
            if not posts:
                # Check if session expired
                if not await is_authenticated(page):
                    return "LinkedIn session expired or requires re-authentication. Please run `python login.py`."
                return f"No posts found for query: '{keywords}' with date filter '{date_posted}'."

            output = [f"Found {len(posts)} posts for '{keywords}':\n"]
            for i, p_data in enumerate(posts, 1):
                output.append(f"--- Post {i} ---")
                output.append(f"Author: {p_data['author_name']} ({p_data['author_headline']})")
                if p_data["author_profile_url"]:
                    output.append(f"Author Profile: {p_data['author_profile_url']}")
                output.append(f"Reactions: {p_data['reactions_count']} | Comments: {p_data['comments_count']} | Engagement Score: {p_data['engagement_score']}")
                output.append(f"Post URL: {p_data['post_url']}")
                output.append(f"Text Preview:\n{p_data['post_text']}\n")

            return "\n".join(output)
        except Exception as e:
            logger.error("Error searching feed posts: %s", e)
            return f"Error while searching LinkedIn posts: {str(e)}"
        finally:
            await browser.close()


@app.tool()
async def linkedin_search_posts(keywords: str, limit: int = 5) -> str:
    """Search LinkedIn posts and discussions by keywords (alias for linkedin_search_feed_posts).

    Args:
        keywords: Search query terms (e.g. 'artificial intelligence agents').
        limit: Maximum number of posts to return (default: 5).
    """
    if has_saved_session():
        return await linkedin_search_feed_posts(keywords=keywords, limit=limit)

    token = _get_access_token()
    if not token:
        return (
            f"[MOCK/DEMO MODE] Search results for '{keywords}' (Top {limit}):\n"
            f"1. Exploring autonomous coding agents and Model Context Protocol.\n"
            f"2. Building scalable tool integrations with MCP and Python.\n"
            f"3. Google Antigravity developer workflow updates.\n"
            "Note: Run `python login.py` to enable live post search."
        )

    return f"Search completed for '{keywords}'. Run `python login.py` to fetch full live post details and engagement scores."


@app.tool()
async def linkedin_comment_on_post(post_url: str, comment_text: str) -> str:
    """Publish a thoughtful comment on a specific LinkedIn post.

    Args:
        post_url: The full LinkedIn post URL (e.g. https://www.linkedin.com/feed/update/urn:li:activity:...).
        comment_text: The comment text to publish.
    """
    if not has_saved_session():
        return (
            "LinkedIn browser session is not configured.\n"
            "To authenticate, please run the login script in your terminal:\n"
            "   python login.py"
        )

    allowed, reason = check_action_allowed("comment")
    if not allowed:
        return f"Comment aborted: {reason}"

    logger.info("Submitting comment on post: %s", post_url)
    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()
        try:
            result = await add_comment_to_post(
                page=page,
                post_url=post_url,
                comment_text=comment_text,
            )
            if not result.get("success"):
                return f"Failed to comment on post: {result.get('error', 'Unknown error')}"

            return (
                f"Successfully posted comment!\n"
                f"Post: {result.get('post_url')}\n"
                f"Comment: \"{result.get('comment_preview')}...\"\n"
                f"Comments used today: {result.get('daily_comments_used')}"
            )
        except Exception as e:
            logger.error("Error commenting on post: %s", e)
            return f"Error while posting comment: {str(e)}"
        finally:
            await browser.close()


@app.tool()
async def linkedin_search_people(keywords: str, limit: int = 5, title: Optional[str] = None) -> str:
    """Search for relevant LinkedIn people, such as recruiters, hiring managers, or engineering leaders.

    Args:
        keywords: Search query terms (e.g. 'Senior Data Engineer', 'Tech recruiter').
        limit: Maximum number of profiles to return (default: 5).
        title: Optional specific job title filter (e.g. 'Engineering Manager', 'Recruiter').
    """
    if not has_saved_session():
        return (
            "LinkedIn browser session is not configured.\n"
            "To authenticate, please run the login script in your terminal:\n"
            "   python login.py"
        )

    logger.info("Searching people for '%s' (title=%s, limit=%d)", keywords, title, limit)
    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()
        try:
            people = await search_people(
                page=page,
                keywords=keywords,
                limit=limit,
                title=title,
            )
            if not people:
                if not await is_authenticated(page):
                    return "LinkedIn session expired or requires re-authentication. Please run `python login.py`."
                return f"No people found matching: '{keywords}'."

            output = [f"Found {len(people)} profiles for '{keywords}':\n"]
            for i, person in enumerate(people, 1):
                output.append(f"{i}. {person['name']}")
                output.append(f"   Headline: {person['headline']}")
                if person.get("location"):
                    output.append(f"   Location: {person['location']}")
                output.append(f"   Profile URL: {person['profile_url']}\n")

            return "\n".join(output)
        except Exception as e:
            logger.error("Error searching people: %s", e)
            return f"Error while searching LinkedIn profiles: {str(e)}"
        finally:
            await browser.close()


@app.tool()
async def linkedin_send_connect_request(profile_url: str, note: Optional[str] = None) -> str:
    """Send a connection invitation to a LinkedIn member with an optional personalized note (max 300 chars).

    Args:
        profile_url: The full LinkedIn profile URL (e.g. https://www.linkedin.com/in/username).
        note: Optional personal note up to 300 characters.
    """
    if not has_saved_session():
        return (
            "LinkedIn browser session is not configured.\n"
            "To authenticate, please run the login script in your terminal:\n"
            "   python login.py"
        )

    allowed, reason = check_action_allowed("invite")
    if not allowed:
        return f"Connection request aborted: {reason}"

    logger.info("Sending connection request to: %s", profile_url)
    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()
        try:
            result = await send_connection_request(
                page=page,
                profile_url=profile_url,
                note=note,
            )
            if not result.get("success"):
                return f"Could not send connection request: {result.get('message') or result.get('error', 'Unknown issue')}"

            note_msg = f'with note: "{note}"' if result.get("has_note") else "without a custom note"
            return (
                f"Successfully sent connection request {note_msg}!\n"
                f"Profile: {result.get('profile_url')}\n"
                f"Connection requests used today: {result.get('daily_invites_used')}"
            )
        except Exception as e:
            logger.error("Error sending connection request: %s", e)
            return f"Error while sending connection request: {str(e)}"
        finally:
            await browser.close()


def main():
    """Main entrypoint to run the MCP server over stdio."""
    logger.info("Starting LinkedIn MCP server over stdio...")
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
