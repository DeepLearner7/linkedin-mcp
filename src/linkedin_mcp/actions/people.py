"""
LinkedIn people search and connection request actions using Playwright.
"""

import asyncio
import logging
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import Page

from linkedin_mcp.browser import human_delay, human_type
from linkedin_mcp.safety import check_action_allowed, record_action

logger = logging.getLogger("linkedin-mcp.people")


async def search_people(
    page: Page,
    keywords: str,
    limit: int = 5,
    title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search LinkedIn people/profiles by keywords or job title.

    Args:
        page: Active authenticated Playwright Page.
        keywords: General search query (e.g. 'Senior Data Engineer recruiter').
        limit: Max profiles to return.
        title: Optional specific job title filter.
    """
    encoded_query = urllib.parse.quote_plus(keywords)
    url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}"
    if title:
        url += f"&titleFreeText={urllib.parse.quote_plus(title)}"

    logger.info("Navigating to LinkedIn people search: %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await human_delay(2.0, 3.5)

    # Adaptive scroll to load requested number of results
    scroll_count = 2 if limit <= 5 else 4
    for _ in range(scroll_count):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await human_delay(1.2, 2.0)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    results: List[Dict[str, Any]] = []

    # Profile cards in search results (supports modern and legacy LinkedIn DOM)
    cards = soup.select(
        "div[role='listitem'], div[data-view-name='search-entity-result-universal-template'], "
        "li.reusable-search__result-container, div.entity-result"
    )

    seen_urls = set()
    ignore_tokens = {"is open to work", "status is offline", "status is online", "• 1st", "• 2nd", "• 3rd+"}

    for card in cards:
        if len(results) >= limit:
            break

        # Profile link
        in_links = card.select("a[href*='/in/']")
        if not in_links:
            continue

        raw_href = in_links[0].get("href", "").split("?")[0]
        if not raw_href or "/in/" not in raw_href or raw_href.endswith("/in/"):
            continue
        clean_url = f"https://www.linkedin.com{raw_href}" if raw_href.startswith("/") else raw_href
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        # Try legacy elements first
        name_elem = card.select_one(
            "span.entity-result__title-text a, a.app-aware-link[href*='/in/'], .entity-result__title a"
        )
        headline_elem = card.select_one(
            ".entity-result__primary-subtitle, div.entity-result__summary"
        )
        loc_elem = card.select_one(".entity-result__secondary-subtitle")

        if name_elem and headline_elem:
            name = name_elem.get_text(separator=" ", strip=True).split("\n")[0].strip()
            headline = headline_elem.get_text(separator=" ", strip=True)
            location = loc_elem.get_text(separator=" ", strip=True) if loc_elem else ""
        else:
            # Modern DOM extraction
            raw_strings = [s.strip() for s in card.stripped_strings if s.strip()]
            deduped = []
            for s in raw_strings:
                if s.lower() in ignore_tokens:
                    continue
                if not deduped or deduped[-1] != s:
                    deduped.append(s)

            if not deduped:
                continue

            name = deduped[0]
            headline = deduped[1] if len(deduped) > 1 else ""
            location = ""
            for item in deduped[2:5]:
                if any(kw in item for kw in ["India", "Area", "District", "Division", "City", "State", ","]):
                    location = item
                    break

        results.append({
            "name": name,
            "headline": headline,
            "location": location,
            "profile_url": clean_url,
        })

    return results


async def send_connection_request(
    page: Page,
    profile_url: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a connection request to a LinkedIn profile, optionally with a personalized note.

    Args:
        page: Active authenticated Playwright Page.
        profile_url: Direct URL to the LinkedIn profile (e.g. https://www.linkedin.com/in/username).
        note: Optional custom message (max 300 chars allowed by LinkedIn).
    """
    # 1. Safety Check
    allowed, reason = check_action_allowed("invite")
    if not allowed:
        return {"success": False, "error": reason}

    logger.info("Visiting profile for connection request: %s", profile_url)
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=35000)
    await human_delay(2.5, 4.0)

    # Check if already a 1st degree connection
    first_degree = page.locator("span.dist-value:has-text('1st'), span:has-text('• 1st')")
    message_btn = page.locator("div.ph5 button:has-text('Message'), section.artdeco-card button:has-text('Message')")
    if await first_degree.count() > 0 and await message_btn.count() > 0:
        return {
            "success": False,
            "status": "ALREADY_CONNECTED",
            "message": "Already connected (1st degree connection) with this member."
        }

    # Check if invitation is already pending
    pending_btn = page.locator("button:has-text('Pending'), button[aria-label*='Pending' i]")
    if await pending_btn.count() > 0 and await pending_btn.first.is_visible():
        return {
            "success": False,
            "status": "ALREADY_PENDING",
            "message": "Connection request already sent and pending."
        }

    # Find the Connect button
    connect_btn = None

    # Priority 1: Direct "Connect" button in top-card actions
    direct_connect = page.locator(
        "div.ph5 button:has-text('Connect'), button[aria-label*='Invite'][aria-label*='to connect'], section.artdeco-card button:has-text('Connect')"
    )
    if await direct_connect.count() > 0 and await direct_connect.first.is_visible():
        connect_btn = direct_connect.first
    else:
        # Priority 2: "More actions" dropdown
        more_btn = page.locator(
            "button[aria-label='More actions'], div.ph5 button:has-text('More'), button[aria-label*='more options']"
        ).first
        if await more_btn.count() > 0:
            await more_btn.click()
            await human_delay(1.0, 1.5)
            # Find connect option in dropdown
            dropdown_connect = page.locator(
                "div[aria-label*='Invite'][role='button'], div[role='button']:has-text('Connect'), span:has-text('Connect')"
            ).first
            if await dropdown_connect.count() > 0:
                connect_btn = dropdown_connect

    if not connect_btn or await connect_btn.count() == 0:
        return {
            "success": False,
            "status": "CONNECT_NOT_AVAILABLE",
            "message": "Could not find an available 'Connect' button. The profile may only allow Following or InMail."
        }

    await connect_btn.click()
    await human_delay(1.5, 2.5)

    # Check if modal opens asking for email (locked behind knowing their email)
    if await page.locator("input[name='email'], input#email").count() > 0:
        close_btn = page.locator("button[aria-label='Dismiss']").first
        if await close_btn.count() > 0:
            await close_btn.click()
        return {
            "success": False,
            "status": "EMAIL_REQUIRED",
            "message": "User settings require entering their personal email address to connect."
        }

    # Check if weekly invitation limit dialog is shown
    weekly_limit_dialog = page.locator(
        "text='You’ve reached the weekly invitation limit', "
        "text='You’ve reached the weekly limit', "
        "span:has-text('weekly invitation limit')"
    )
    if await weekly_limit_dialog.count() > 0:
        dismiss_btn = page.locator("button[aria-label='Dismiss'], button:has-text('Got it')").first
        if await dismiss_btn.count() > 0:
            await dismiss_btn.click()
        return {
            "success": False,
            "status": "WEEKLY_LIMIT_REACHED",
            "message": "LinkedIn weekly invitation limit reached on this account."
        }

    # Handle "Add a note" vs "Send without a note"
    has_custom_note = bool(note and note.strip())
    if has_custom_note:
        clean_note = note.strip()[:300]
        add_note_btn = page.locator("button[aria-label='Add a note'], button:has-text('Add a note')").first
        if await add_note_btn.count() > 0:
            await add_note_btn.click()
            await human_delay(1.0, 1.5)

        textarea = page.locator("textarea[name='message'], textarea#custom-message").first
        if await textarea.count() > 0:
            await textarea.fill(clean_note)
            await human_delay(1.0, 2.0)

        # When a note is provided, click "Send" / "Send invitation", NOT "Send without a note"
        send_selectors = [
            "button[aria-label='Send invitation']:not([disabled])",
            "button[aria-label='Send now']:not([disabled])",
            "div.artdeco-modal button:has-text('Send'):not(:has-text('without')):not([disabled])",
        ]
    else:
        # When no note is provided, "Send without a note" is appropriate
        send_selectors = [
            "button[aria-label='Send without a note']:not([disabled])",
            "button:has-text('Send without a note'):not([disabled])",
            "button[aria-label='Send invitation']:not([disabled])",
            "button:has-text('Send'):not([disabled])",
        ]

    send_btn = None
    for sel in send_selectors:
        candidate = page.locator(sel)
        if await candidate.count() > 0 and await candidate.last.is_enabled():
            send_btn = candidate.last
            break

    if not send_btn:
        return {"success": False, "status": "SEND_FAILED", "message": "Could not locate or click Send invitation button."}

    await send_btn.click()
    await human_delay(2.0, 3.5)

    # Record safe action
    stats = record_action("invite")

    return {
        "success": True,
        "status": "SENT",
        "profile_url": profile_url,
        "has_note": has_custom_note,
        "daily_invites_used": stats.get("invites", 0),
    }
