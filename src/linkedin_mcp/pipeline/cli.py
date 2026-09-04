"""
Command Line Interface (CLI) for executing LinkedIn job scraping, extraction, and database querying.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from linkedin_mcp.pipeline.orchestrator import run_job_sync
from linkedin_mcp.db.repository import query_stored_jobs, get_storage_stats
from linkedin_mcp.db.schema import JobQueryParams
from linkedin_mcp.db.database import DEFAULT_DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("linkedin-mcp.cli")


def _format_markdown_report(result: dict) -> str:
    jobs = result.get("jobs", [])
    summary = result.get("sync_summary", {})
    stats = result.get("database_stats", {})

    lines = [
        "# LinkedIn Job Sync Report",
        f"**Sync Run ID:** {summary.get('run_id')} | **Time:** {summary.get('run_at')}",
        f"**Processed:** {summary.get('total')} | **New Inserted:** {summary.get('inserted')} | **Updated:** {summary.get('updated')}",
        f"**Total in Database:** {stats.get('total_jobs')} jobs (`{DEFAULT_DB_PATH}`)\n",
        "---",
        "## Synchronized Openings\n",
        "| # | Role | Company | Location | Source | Tech Stack | Details / Apply |",
        "|---|---|---|---|---|---|---|",
    ]

    for idx, j in enumerate(jobs, 1):
        stack_str = ", ".join(j.get("tech_stack", [])) or "-"
        src = j.get("source_type", "").replace("_", " ").title()
        apply_link = f"[Apply / View]({j.get('source_url', '#')})"
        if j.get("hiring_contact_email"):
            apply_link += f"<br>📧 {j.get('hiring_contact_email')}"
        lines.append(
            f"| {idx} | **{j.get('title')}** | {j.get('company')} | {j.get('location')} | {src} | {stack_str} | {apply_link} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape and synchronize LinkedIn jobs and recruiter posts into a deterministic database."
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default="Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead",
        help="Job search query terms (comma-separated for multiple roles; default: 'Senior Data Engineer, Senior Data Platform Engineer, Data Engineering Lead')",
    )
    parser.add_argument(
        "--location",
        type=str,
        default="Pune, Bangalore",
        help="Target locations (comma-separated for multiple cities; default: 'Pune, Bangalore')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max job board openings to fetch (default: 10)",
    )
    parser.add_argument(
        "--date-posted",
        type=str,
        default="past-month",
        choices=["past-24h", "past-week", "past-month"],
        help="Time window filter (default: past-month)",
    )
    parser.add_argument(
        "--no-feed",
        action="store_true",
        help="Disable searching recruiter feed posts",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database storage stats without running a scrape",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Query stored jobs by keyword without scraping",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default=None,
        help="Filter stored jobs by comma-separated skills (e.g. 'Spark, Databricks')",
    )
    parser.add_argument(
        "--export",
        choices=["markdown", "json", "none"],
        default="markdown",
        help="Report export format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save export output to specified file path",
    )

    args = parser.parse_args()

    # 1. Just stats
    if args.stats:
        stats = get_storage_stats()
        print(json.dumps(stats, indent=2))
        return

    # 2. Query stored jobs
    if args.query or args.skills:
        skill_list = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else None
        params = JobQueryParams(keywords=args.query, skills=skill_list, limit=25)
        rows = query_stored_jobs(params)
        print(f"Found {len(rows)} matching job(s) in local SQLite database:")
        for idx, r in enumerate(rows, 1):
            print(f"[{idx}] {r['title']} @ {r['company']} ({r['location']}) - {r['source_url']}")
            if r.get("tech_stack"):
                print(f"    Skills: {', '.join(r['tech_stack'])}")
            if r.get("hiring_contact_email"):
                print(f"    Email: {r['hiring_contact_email']}")
        return

    # 3. Live Sync Run
    print(f"Starting LinkedIn Job Sync for '{args.keywords}' in '{args.location}'...")
    result = asyncio.run(
        run_job_sync(
            keywords=args.keywords,
            location=args.location,
            limit=args.limit,
            date_posted=args.date_posted,
            include_feed_posts=not args.no_feed,
            source_name="cli_sync",
        )
    )

    # Format output
    if args.export == "markdown":
        report = _format_markdown_report(result)
        print("\n" + report)
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            print(f"\nReport saved to: {args.output}")
    elif args.export == "json":
        json_str = json.dumps(result, indent=2)
        print(json_str)
        if args.output:
            Path(args.output).write_text(json_str, encoding="utf-8")
            print(f"\nReport saved to: {args.output}")
    else:
        summary = result["sync_summary"]
        print(
            f"Sync complete! Processed: {summary['total']}, Inserted: {summary['inserted']}, Updated: {summary['updated']}"
        )


if __name__ == "__main__":
    main()
