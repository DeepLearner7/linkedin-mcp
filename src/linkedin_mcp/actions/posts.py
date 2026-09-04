"""
LinkedIn post search and commenting actions using Playwright.
"""

import asyncio
import logging
import re
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import Page

from linkedin_mcp.browser import human_delay, human_type
from linkedin_mcp.safety import check_action_allowed, record_action

logger = logging.getLogger("linkedin-mcp.posts")


def _parse_count(text: str) -> int:
    """Extract numeric count from string like '1,245 reactions' or '45 comments'."""
    if not text:
        return 0
    clean = text.replace(",", "").replace(".", "").strip()
    match = re.search(r"(\d+)", clean)
    return int(match.group(1)) if match else 0


async def search_feed_posts(
    page: Page,
    keywords: str,
    limit: int = 5,
    sort_by: str = "date_posted",
    date_posted: str = "past-week",
) -> List[Dict[str, Any]]:
    """
    Search LinkedIn content posts for keywords with filters and calculate engagement scores.

    Args:
        page: Active authenticated Playwright Page.
        keywords: Search query string.
        limit: Max results to return.
        sort_by: 'date_posted' (latest) or 'relevance'.
        date_posted: 'past-24h', 'past-week', 'past-month', or None.
    """
    encoded_query = urllib.parse.quote_plus(keywords)
    url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_query}"

    if sort_by == "date_posted":
        url += "&sortBy=%22date_posted%22"
    if date_posted in ["past-24h", "past-week", "past-month"]:
        url += f"&datePosted=%22{date_posted}%22"

    logger.info("Navigating to LinkedIn post search: %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await human_delay(2.5, 4.0)

    # Scroll down to trigger lazy loaded cards
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
        await human_delay(1.5, 2.5)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    results: List[Dict[str, Any]] = []

    # Modern & legacy LinkedIn post card containers
    post_cards = soup.select(
        "div[componentkey*='update-card'], "
        "div[role='listitem'][componentkey*='update'], "
        "div[data-urn*='urn:li:activity'], "
        "div.feed-shared-update-v2, "
        "div[data-view-name='search-entity-result-universal-template']"
    )

    # Fallback container detection using follow buttons
    if not post_cards:
        follow_buttons = [
            btn for btn in soup.find_all("button")
            if "follow" in (btn.get_text() or "").lower()
        ]
        for fb in follow_buttons:
            parent = fb.parent
            for _ in range(8):
                if not parent:
                    break
                p_text = parent.get_text(separator=" ", strip=True).lower()
                if parent.name == "div" and ("comment" in p_text or "repost" in p_text):
                    if parent not in post_cards:
                        post_cards.append(parent)
                    break
                parent = parent.parent

    seen_signatures = set()

    for card in post_cards:
        if len(results) >= limit:
            break

        # Author Name & Profile Link
        author_name = "Unknown Author"
        author_url = ""
        actor_link = card.find("a", href=lambda h: h and "/in/" in h)
        if actor_link:
            raw_href = actor_link.get("href", "")
            author_url = raw_href.split("?")[0]
            if not author_url.startswith("http"):
                author_url = f"https://www.linkedin.com{author_url}"

            raw_name = actor_link.get_text(separator=" ", strip=True)
            clean_name = re.sub(r"•\s*(1st|2nd|3rd\+?|\d+.*)", "", raw_name).strip()
            if clean_name:
                author_name = clean_name
            else:
                for p_tag in card.find_all(["p", "span"], limit=10):
                    txt = p_tag.get_text(strip=True)
                    if txt and txt not in ["Feed post", "Follow", "+ Follow", "View my services"] and not txt.startswith("•"):
                        author_name = txt
                        break

        # Author Headline
        headline = ""
        headline_elem = card.select_one(".update-components-actor__description, .update-components-actor__sub-description")
        if headline_elem:
            headline = headline_elem.get_text(separator=" ", strip=True)
        else:
            strings = [s.strip() for s in card.stripped_strings]
            try:
                name_idx = next(i for i, s in enumerate(strings) if author_name in s or s in author_name)
                for s in strings[name_idx + 1: name_idx + 6]:
                    if s.startswith("•") or "service" in s.lower() or s.endswith("•") or s in ["Follow", "+ Follow"]:
                        continue
                    headline = s
                    break
            except (StopIteration, IndexError):
                pass

        # Post URL
        post_url = ""
        link_elem = card.find("a", href=lambda h: h and any(k in h for k in ["/feed/update/", "activity:", "share:", "/posts/"]))
        if link_elem:
            href = link_elem.get("href", "").split("?")[0]
            post_url = f"https://www.linkedin.com{href}" if href.startswith("/") else href
        elif author_url:
            post_url = f"{author_url.rstrip('/')}/recent-activity/all/"

        # Post Content / Text
        post_text = ""
        text_elem = card.select_one(
            ".feed-shared-update-v2__description, .update-components-text, .feed-shared-inline-show-more-text"
        )
        if text_elem:
            post_text = text_elem.get_text(separator=" ", strip=True)
        else:
            candidate_paras = []
            for p_tag in card.find_all(["p", "div"]):
                t = p_tag.get_text(separator=" ", strip=True)
                if len(t) > 50 and not p_tag.find(["p", "div"]):
                    if t not in candidate_paras and author_name not in t and headline not in t:
                        candidate_paras.append(t)
            if candidate_paras:
                post_text = " ".join(candidate_paras)
            else:
                strings = list(card.stripped_strings)
                try:
                    follow_idx = next(i for i, s in enumerate(strings) if "follow" in s.lower())
                    body_parts = []
                    for s in strings[follow_idx + 1:]:
                        if any(k in s.lower() for k in ["like", "comment", "repost", "send", "reactions"]):
                            break
                        if s not in ["…more", "…", "more"]:
                            body_parts.append(s)
                    post_text = " ".join(body_parts)
                except StopIteration:
                    post_text = " ".join(strings[:20])

        if not post_text and not post_url:
            continue

        # Deduplicate
        sig = (author_url, post_text[:80])
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        # Engagement: Reactions & Comments
        reactions = 0
        comments = 0
        reactions_elem = card.select_one(
            ".social-details-social-counts__reactions-count, button[aria-label*='reaction'], span[aria-label*='reaction']"
        )
        if reactions_elem:
            reactions = _parse_count(reactions_elem.get_text())

        comments_elem = card.select_one(
            ".social-details-social-counts__comments, button[aria-label*='comment']"
        )
        if comments_elem:
            comments = _parse_count(comments_elem.get_text())

        if reactions == 0 or comments == 0:
            for tag in card.find_all(["a", "span", "button"]):
                t = tag.get_text(strip=True).lower()
                if "reaction" in t and reactions == 0:
                    reactions = _parse_count(t)
                elif "comment" in t and comments == 0:
                    comments = _parse_count(t)

        score = reactions + (comments * 2)

        results.append({
            "post_url": post_url,
            "author_name": author_name,
            "author_headline": headline,
            "author_profile_url": author_url,
            "post_text": post_text[:600] + ("..." if len(post_text) > 600 else ""),
            "reactions_count": reactions,
            "comments_count": comments,
            "engagement_score": score,
        })

    return results


async def add_comment_to_post(
    page: Page,
    post_url: str,
    comment_text: str,
) -> Dict[str, Any]:
    """
    Publish a comment on a LinkedIn post.

    Args:
        page: Active authenticated Playwright Page.
        post_url: Direct URL to the LinkedIn post.
        comment_text: The comment message to submit.
    """
    # 1. Check Safety limits
    allowed, reason = check_action_allowed("comment")
    if not allowed:
        return {"success": False, "error": reason}

    if not comment_text.strip():
        return {"success": False, "error": "Comment text cannot be empty."}

    logger.info("Opening post to comment: %s", post_url)
    await page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
    await human_delay(2.0, 3.5)

    # Check if comments are disabled or restricted by author
    restricted_indicator = page.locator(
        "text='Comments on this post are turned off', "
        "text='Comments on this post have been limited', "
        "span:has-text('Comments are turned off')"
    )
    if await restricted_indicator.count() > 0:
        return {
            "success": False,
            "status": "COMMENTS_RESTRICTED",
            "error": "Comments are disabled or restricted by the author on this post."
        }

    # Scroll slightly down to make comment section visible
    await page.evaluate("window.scrollBy(0, 350)")
    await human_delay(1.0, 2.0)

    # Modern and legacy comment editor selectors
    comment_box_selectors = [
        "div[role='textbox'][aria-label*='comment' i]",
        "div.ql-editor[contenteditable='true']",
        "div.comments-comment-box-comment__text-editor div[contenteditable='true']",
        ".comments-comment-box__editor div[contenteditable='true']",
        "div[role='textbox'][aria-label*='Add a comment']",
        "div.editor-content p",
    ]
    combined_box_selector = ", ".join(comment_box_selectors)

    has_box = await page.locator(combined_box_selector).count() > 0

    if not has_box:
        # Click the "Comment" button on the post to open the comment box
        comment_btn = page.locator(
            "button.comment-button, button[aria-label*='Comment on' i], "
            "button[aria-label*='comment' i], button:has-text('Comment')"
        )
        if await comment_btn.count() > 0 and await comment_btn.first.is_visible():
            await comment_btn.first.click()
            await human_delay(1.0, 2.0)

    # Focus comment editor
    editor = page.locator(combined_box_selector).first
    if await editor.count() == 0:
        return {
            "success": False,
            "error": "Could not locate the comment input box on this post (comments may be disabled or page structure changed)."
        }

    await editor.click()
    await human_delay(0.5, 1.0)

    # Enter comment text with fallback for contenteditable ProseMirror / Quill editors
    try:
        await editor.fill(comment_text)
    except Exception:
        # Fallback: type via keyboard or document.execCommand
        await editor.press_sequentially(comment_text, delay=20)

    await human_delay(1.0, 2.0)

    # Find and click Submit button
    submit_selectors = [
        "button.comments-comment-box__submit-button--cr",
        "button.comments-comment-box__submit-button",
        "button[type='submit']:has-text('Comment')",
        "button.comments-comment-box__submit-button:not([disabled])",
        "button:has-text('Comment'):not([disabled])",
        "button:has-text('Post'):not([disabled])",
    ]
    submit_btn = None
    for sel in submit_selectors:
        candidate = page.locator(sel)
        if await candidate.count() > 0 and await candidate.last.is_enabled():
            submit_btn = candidate.last
            break

    if not submit_btn:
        return {"success": False, "error": "Found comment editor, but submit button was not active or clickable."}

    await submit_btn.click()
    await human_delay(2.5, 4.0)

    # Record safe action
    stats = record_action("comment")

    return {
        "success": True,
        "status": "POSTED",
        "post_url": post_url,
        "comment_preview": comment_text[:100],
        "daily_comments_used": stats.get("comments", 0),
    }

