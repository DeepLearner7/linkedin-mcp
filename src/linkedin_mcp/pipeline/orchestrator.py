"""
Orchestrator for automated scraping, filtering, and database synchronization of LinkedIn jobs.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright

from linkedin_mcp.browser import launch_stealth_context, has_saved_session
from linkedin_mcp.actions.jobs import search_job_board
from linkedin_mcp.actions.posts import search_feed_posts
from linkedin_mcp.extractor.helpers import (
    extract_emails,
    extract_urls,
    extract_experience_years,
    match_tech_stack,
    is_likely_hiring_post,
)
from linkedin_mcp.db.schema import (
    DeterministicJobSchema,
    WorkplaceType,
    SourceType,
    generate_job_id,
)
from linkedin_mcp.db.repository import bulk_upsert_jobs, get_storage_stats
from linkedin_mcp.db.database import DEFAULT_DB_PATH

logger = logging.getLogger("linkedin-mcp.orchestrator")


def _detect_workplace_type(text: str) -> WorkplaceType:
    lower = text.lower()
    if "remote" in lower:
        return WorkplaceType.REMOTE
    elif "hybrid" in lower:
        return WorkplaceType.HYBRID
    elif "on-site" in lower or "onsite" in lower:
        return WorkplaceType.ONSITE
    return WorkplaceType.UNSPECIFIED


async def run_job_sync(
    keywords: str = "Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead",
    location: str = "Pune, Bangalore",
    limit: int = 25,
    date_posted: str = "past-week",
    include_feed_posts: bool = True,
    source_name: str = "daily_orchestrator_sync",
) -> Dict[str, Any]:
    """
    Orchestrate scraping both Job Board and Feed Posts, normalize schema, and save to SQLite.
    Supports comma-separated keywords and locations.

    Args:
        keywords: Job search keywords or comma-separated roles (e.g. 'Senior Data Engineer, Data Engineering Lead').
        location: City location or comma-separated locations (e.g. 'Pune, Bangalore').
        limit: Number of job board results to search per role/location query.
        date_posted: Date window ('past-24h', 'past-week', 'past-month').
        include_feed_posts: Whether to also search recruiter feed posts.
        source_name: Audit tag for sync run.

    Returns:
        Dict with sync stats and list of parsed jobs.
    """
    if not has_saved_session():
        raise RuntimeError("No saved LinkedIn browser session found. Run `python login.py` to authenticate.")

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    location_list = [l.strip() for l in location.split(",") if l.strip()]

    parsed_jobs: List[DeterministicJobSchema] = []
    candidate_feed_posts: List[Dict[str, Any]] = []
    seen_job_ids = set()

    # Construct combined Boolean search expression if multiple roles are requested:
    # e.g. '("Senior Data Engineer" OR "Senior Data Platform Engineer" OR "Data Engineering Lead")'
    if len(keyword_list) > 1:
        query_kw = "(" + " OR ".join(f'"{k.strip(chr(34))}"' for k in keyword_list) + ")"
    elif keyword_list:
        query_kw = f'"{keyword_list[0].strip(chr(34))}"'
    else:
        query_kw = '"Senior Data Engineer"'

    # For Recruiter Feed Posts: LinkedIn content search behaves best with concise, unnested queries
    # e.g., 'hiring "Data Engineer" Pune' rather than complex multi-clause Boolean expressions
    feed_term = "Data Engineer"
    for k in keyword_list:
        clean_k = k.lower().replace("senior", "").replace("lead", "").strip()
        if "data engineer" in clean_k:
            feed_term = "Data Engineer"
            break
        elif "platform" in clean_k:
            feed_term = "Data Platform"
            break
    if not keyword_list:
        feed_term = "Data Engineer"

    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=True)
        page = await context.new_page()

        try:
            for loc in location_list:
                # 1. Scrape Job Board
                logger.info("Searching Job Board for %s in '%s'...", query_kw, loc)
                try:
                    raw_job_cards = await search_job_board(
                        page=page,
                        keywords=query_kw,
                        location=loc,
                        limit=limit,
                        sort_by="date_posted",
                        date_posted=date_posted,
                    )

                    for item in raw_job_cards:
                        job_url = item.get("job_url", "")
                        title = item.get("title", "")
                        company = item.get("company", "")
                        job_id = generate_job_id(SourceType.JOB_BOARD, job_url, title, company)
                        if job_id in seen_job_ids:
                            continue
                        seen_job_ids.add(job_id)

                        workplace = _detect_workplace_type(item.get("location", ""))
                        skills = match_tech_stack(title + " " + item.get("footer_status", ""))

                        job_obj = DeterministicJobSchema(
                            job_id=job_id,
                            source_type=SourceType.JOB_BOARD,
                            source_url=job_url,
                            title=title,
                            company=company,
                            location=item.get("location", loc),
                            workplace_type=workplace,
                            tech_stack=skills,
                            is_easy_apply=bool(item.get("is_easy_apply", False)),
                            is_hiring_confirmed=True,
                            relevance_score=1.0,
                            posted_relative=item.get("footer_status", "recently"),
                            description_summary=f"{title} position at {company} in {item.get('location', loc)}.",
                            raw_text=f"Title: {title} | Company: {company} | Location: {item.get('location', '')} | Status: {item.get('footer_status', '')}",
                        )
                        parsed_jobs.append(job_obj)
                except Exception as e:
                    logger.warning("Error scraping Job Board for '%s' in '%s': %s", query_kw, loc, e)

                # 2. Scrape Recruiter Feed Posts
                if include_feed_posts:
                    post_query = f'hiring "{feed_term}" {loc}'
                    logger.info("Searching Feed Posts for '%s'...", post_query)
                    try:
                        raw_posts = await search_feed_posts(
                            page=page,
                            keywords=post_query,
                            limit=15,
                            sort_by="date_posted",
                            date_posted="past-week",
                        )

                        for post in raw_posts:
                            text = post.get("text", "")
                            if not text or len(text.strip()) < 15:
                                continue

                            post_url = post.get("post_url", "")
                            author = post.get("author_name", "Recruiter")
                            author_url = post.get("author_url", "")
                            headline = post.get("headline", "")

                            post_id = generate_job_id(SourceType.FEED_POST, post_url, feed_term, author)
                            if post_id in seen_job_ids:
                                continue
                            seen_job_ids.add(post_id)

                            emails = extract_emails(text)
                            urls = extract_urls(text)
                            skills = match_tech_stack(text)
                            exp_years = extract_experience_years(text)
                            workplace = _detect_workplace_type(text)

                            # Stage candidate post for Stage 2 Antigravity AI classification
                            candidate_feed_posts.append({
                                "post_id": post_id,
                                "author_name": author,
                                "author_url": author_url,
                                "headline": headline,
                                "post_url": post_url,
                                "target_location": loc,
                                "target_role": feed_term,
                                "text": text,
                                "suggested_emails": emails,
                                "suggested_urls": urls,
                                "suggested_skills": skills,
                                "suggested_exp_years": exp_years,
                                "suggested_workplace": workplace.value,
                            })
                    except Exception as e:
                        logger.warning("Error scraping Feed Posts for '%s': %s", post_query, e)

        finally:
            await browser.close()

    # Save candidate feed posts for Stage 2 Antigravity AI Semantic Classification
    candidate_posts_file = DEFAULT_DB_PATH.parent / "candidate_feed_posts.json"
    try:
        candidate_posts_file.write_text(json.dumps(candidate_feed_posts, indent=2), encoding="utf-8")
        logger.info("Saved %d candidate feed posts for AI classification to: %s", len(candidate_feed_posts), candidate_posts_file)
    except Exception as e:
        logger.warning("Failed saving candidate feed posts: %s", e)

    # Bulk upsert Job Board jobs into SQLite database
    summary = bulk_upsert_jobs(parsed_jobs, source_name=source_name)
    stats = get_storage_stats()

    return {
        "sync_summary": summary,
        "database_stats": stats,
        "jobs": [j.model_dump() for j in parsed_jobs],
        "candidate_feed_posts_count": len(candidate_feed_posts),
        "candidate_feed_posts_file": str(candidate_posts_file),
    }
