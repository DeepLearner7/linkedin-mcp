"""
Browser manager for LinkedIn MCP using Playwright.
Handles session state, stealth configuration, and human-like interaction.
"""

import asyncio
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger("linkedin-mcp.browser")

CONFIG_DIR = Path.home() / ".config" / "linkedin-mcp"
SESSION_FILE = CONFIG_DIR / "session.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def get_session_file() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_FILE


def has_saved_session() -> bool:
    """Return True if session.json exists and is non-empty, or li_at cookie is set in env."""
    if SESSION_FILE.is_file() and SESSION_FILE.stat().st_size > 20:
        return True
    return bool(os.getenv("LINKEDIN_LI_AT_COOKIE") or os.getenv("LINKEDIN_LI_AT"))


def _bootstrap_session_from_env_if_needed() -> None:
    """If session.json is missing but LINKEDIN_LI_AT_COOKIE is set, create session.json."""
    if SESSION_FILE.is_file() and SESSION_FILE.stat().st_size > 20:
        return
    li_at = os.getenv("LINKEDIN_LI_AT_COOKIE") or os.getenv("LINKEDIN_LI_AT")
    if not li_at:
        return

    session_data = {
        "cookies": [
            {
                "name": "li_at",
                "value": li_at.strip(),
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            },
            {
                "name": "li_at",
                "value": li_at.strip(),
                "domain": ".www.linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            },
        ],
        "origins": [],
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
    logger.info("Created %s from LINKEDIN_LI_AT environment variable.", SESSION_FILE)


async def launch_stealth_context(
    p: Playwright,
    headless: bool = True,
    storage_state: Optional[Path] = None,
) -> Tuple[Browser, BrowserContext]:
    """Launch Chromium browser and context with anti-bot evasion settings."""
    _bootstrap_session_from_env_if_needed()

    browser = await p.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1280,900",
        ],
    )

    state_path = storage_state or (SESSION_FILE if SESSION_FILE.exists() else None)
    context_kwargs = {
        "user_agent": USER_AGENT,
        "viewport": {"width": 1280, "height": 900},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }
    if state_path and state_path.is_file() and state_path.stat().st_size > 10:
        context_kwargs["storage_state"] = str(state_path)

    context = await browser.new_context(**context_kwargs)

    # Evade navigator.webdriver detection
    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        window.chrome = {
            runtime: {},
        };
        """
    )
    return browser, context


async def human_delay(min_s: float = 1.5, max_s: float = 3.5) -> None:
    """Randomized human delay to prevent bot rate-limiting."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def human_type(page: Page, selector: str, text: str, delay_range: Tuple[int, int] = (30, 80)) -> None:
    """Type text character-by-character with realistic typing variance."""
    await page.click(selector)
    for char in text:
        await page.keyboard.press(char)
        await asyncio.sleep(random.uniform(delay_range[0] / 1000.0, delay_range[1] / 1000.0))


async def is_authenticated(page: Page) -> bool:
    """Verify if the current page has an authenticated LinkedIn session."""
    url = page.url
    if "linkedin.com/login" in url or "linkedin.com/checkpoint" in url or "linkedin.com/uas/login" in url:
        return False

    # Check for feed or navigation presence
    try:
        # Check for profile icon, feed container, or search input
        has_nav = await page.locator(".global-nav__me, .feed-identity-module, input.search-global-typeahead__input").count() > 0
        if has_nav:
            return True
        # If url is linkedin.com/feed or /in/ or /search
        if any(path in url for path in ["/feed", "/in/", "/search/"]):
            return True
    except Exception:
        pass
    return False
