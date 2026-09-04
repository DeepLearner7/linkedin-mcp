"""
LinkedIn Job Board search and details actions using Playwright.
"""

import asyncio
import logging
import re
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import Page

from linkedin_mcp.browser import human_delay

logger = logging.getLogger("linkedin-mcp.jobs")

# Mapping friendly filter values to LinkedIn query parameters
DATE_POSTED_MAP = {
    "past-24h": "r86400",
    "past-week": "r604800",
    "past-month": "r2592000",
}

WORKPLACE_TYPE_MAP = {
    "onsite": "1",
    "on-site": "1",
    "remote": "2",
    "hybrid": "3",
}

EXPERIENCE_LEVEL_MAP = {
    "internship": "1",
    "entry": "2",
    "entry-level": "2",
    "associate": "3",
    "mid-senior": "4",
    "director": "5",
    "executive": "6",
}


def build_jobs_search_url(
    keywords: str,
    location: str = "Pune",
    sort_by: str = "date_posted",
    date_posted: Optional[str] = "past-month",
    workplace_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    start: int = 0,
) -> str:
    """Build the LinkedIn job search URL with applied filters."""
    params = {
        "keywords": keywords,
        "location": location,
    }
    encoded_query = urllib.parse.urlencode(params)
    url = f"https://www.linkedin.com/jobs/search/?{encoded_query}"

    if sort_by == "date_posted":
        url += "&sortBy=DD"
    elif sort_by == "relevance":
        url += "&sortBy=R"

    if date_posted and date_posted.lower() in DATE_POSTED_MAP:
        url += f"&f_TPR={DATE_POSTED_MAP[date_posted.lower()]}"

    if workplace_type and workplace_type.lower() in WORKPLACE_TYPE_MAP:
        url += f"&f_WT={WORKPLACE_TYPE_MAP[workplace_type.lower()]}"

    if experience_level and experience_level.lower() in EXPERIENCE_LEVEL_MAP:
        url += f"&f_E={EXPERIENCE_LEVEL_MAP[experience_level.lower()]}"

    if start > 0:
        url += f"&start={start}"

    return url


def parse_job_card(card: Any) -> Optional[Dict[str, Any]]:
    """Parse a single job card element from search results."""
    # 1. Job ID
    job_id = card.get("data-job-id") or card.get("data-occludable-job-id")
    if not job_id:
        link = card.select_one("a[href*='/jobs/view/']")
        if link:
            m = re.search(r"/jobs/view/(\d+)", link.get("href", ""))
            if m:
                job_id = m.group(1)
    if not job_id:
        return None

    # 2. Title
    title = ""
    title_strong = card.select_one("a.job-card-list__title--link strong, a[href*='/jobs/view/'] strong")
    if title_strong:
        title = title_strong.get_text(strip=True)
    else:
        title_a = card.select_one("a.job-card-list__title--link, a[href*='/jobs/view/']")
        if title_a:
            raw_title = title_a.get_text(separator=" ", strip=True)
            clean_title = re.sub(r"\s+with verification.*$", "", raw_title, flags=re.IGNORECASE)
            clean_title = re.sub(r"^([^\n\r]+?)\1+$", r"\1", clean_title).strip()
            title = clean_title

    # 3. Company
    company_elem = card.select_one(".artdeco-entity-lockup__subtitle, .job-card-container__primary-description")
    company = company_elem.get_text(strip=True) if company_elem else ""

    if not title or not company:
        return None

    # 4. Location & Workplace Type
    loc_elem = card.select_one(".artdeco-entity-lockup__caption, .job-card-container__metadata-wrapper")
    location_text = loc_elem.get_text(separator=" ", strip=True) if loc_elem else ""

    # 5. Footer & Timing
    footer_elem = card.select_one(".job-card-container__footer-wrapper, .job-card-list__footer-wrapper")
    footer_text = footer_elem.get_text(separator=" | ", strip=True) if footer_elem else ""
    is_easy_apply = "easy apply" in footer_text.lower()

    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

    return {
        "job_id": str(job_id),
        "title": title,
        "company": company,
        "location": location_text,
        "footer_status": footer_text,
        "is_easy_apply": is_easy_apply,
        "job_url": job_url,
    }


async def search_job_board(
    page: Page,
    keywords: str,
    location: str = "Pune",
    limit: int = 10,
    sort_by: str = "date_posted",
    date_posted: Optional[str] = "past-month",
    workplace_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    start_offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Search LinkedIn Job Board for active openings with filtering and pagination.

    Args:
        page: Active authenticated Playwright Page.
        keywords: Search query terms (e.g. 'Senior Data Engineer').
        location: City or location name (e.g. 'Pune', 'Bengaluru').
        limit: Max jobs to return.
        sort_by: 'date_posted' (most recent) or 'relevance'.
        date_posted: 'past-24h', 'past-week', 'past-month', or None/any.
        workplace_type: 'onsite', 'remote', 'hybrid', or None.
        experience_level: 'internship', 'entry', 'associate', 'mid-senior', 'director', 'executive', or None.
        start_offset: Starting pagination offset (multiples of 25).
    """
    results: List[Dict[str, Any]] = []
    seen_ids = set()
    current_offset = start_offset

    while len(results) < limit:
        url = build_jobs_search_url(
            keywords=keywords,
            location=location,
            sort_by=sort_by,
            date_posted=date_posted,
            workplace_type=workplace_type,
            experience_level=experience_level,
            start=current_offset,
        )

        logger.info("Navigating to LinkedIn job search: %s", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await human_delay(1.2, 2.0)

        # Scroll down list pane to load cards
        for _ in range(3):
            await page.evaluate("""
                () => {
                    const el = document.querySelector('.jobs-search-results-list') ||
                               document.querySelector('.scaffold-layout__list') ||
                               window;
                    el.scrollBy(0, 1000);
                }
            """)
            await human_delay(0.5, 0.9)

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select(
            "div.job-card-container[data-job-id], "
            "li[data-occludable-job-id], "
            "div[data-job-id]"
        )

        if not cards:
            break

        cards_added_this_page = 0
        for card in cards:
            parsed = parse_job_card(card)
            if not parsed or parsed["job_id"] in seen_ids:
                continue

            seen_ids.add(parsed["job_id"])
            results.append(parsed)
            cards_added_this_page += 1

            if len(results) >= limit:
                break

        # If no new cards were added or we hit the target limit, stop
        if cards_added_this_page == 0 or len(results) >= limit:
            break

        # Move to next page of 25 jobs
        current_offset += 25
        await human_delay(1.5, 2.5)

    return results


async def get_job_details(page: Page, job_identifier: str) -> Dict[str, Any]:
    """
    Fetch full details, requirements, and job description for a specific LinkedIn job posting.

    Args:
        page: Active authenticated Playwright Page.
        job_identifier: Full LinkedIn job URL or numeric job ID.
    """
    clean_id = re.sub(r"\D", "", job_identifier) if not job_identifier.startswith("http") else None
    if clean_id:
        url = f"https://www.linkedin.com/jobs/view/{clean_id}/"
    else:
        url = job_identifier.split("?")[0]
        if not url.endswith("/"):
            url += "/"

    logger.info("Fetching job details from: %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
    await human_delay(2.5, 3.5)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Title and Company from title tag or DOM
    page_title = soup.title.string.strip() if soup.title else ""
    title = ""
    company = ""
    if "|" in page_title:
        parts = [p.strip() for p in page_title.split("|")]
        if len(parts) >= 2:
            title = parts[0]
            company = parts[1]

    h1 = soup.find("h1")
    if h1 and not title:
        title = h1.get_text(strip=True)

    # Description extraction
    description = ""
    about_h2 = soup.find(lambda tag: tag.name in ["h2", "h3"] and "About the job" in tag.get_text())
    if about_h2:
        parent = about_h2.find_parent(
            lambda t: t.name in ["div", "article", "section"] and len(t.get_text()) > 200
        )
        if parent:
            lines = [l.strip() for l in parent.get_text(separator="\n", strip=True).split("\n") if l.strip()]
            description = "\n".join(lines)

    if not description:
        for sel in ["#job-details", ".jobs-description__content", ".jobs-box__html-content", "article"]:
            el = soup.select_one(sel)
            if el and len(el.get_text()) > 100:
                description = el.get_text(separator="\n", strip=True)
                break

    # Metadata & Insights (experience level, workplace type, applicant count)
    insights = []
    insight_elements = soup.select(
        ".jobs-unified-top-card__job-insight, .job-details-jobs-unified-top-card__primary-description-container span"
    )
    for el in insight_elements:
        txt = el.get_text(separator=" ", strip=True)
        if txt and txt not in insights and len(txt) < 100:
            insights.append(txt)

    return {
        "job_url": url,
        "title": title or "Unknown Title",
        "company": company or "Unknown Company",
        "description": description or "No description could be extracted.",
        "insights": insights,
    }
