"""
Repository layer providing CRUD, upsert, and analytical queries for stored LinkedIn jobs.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from linkedin_mcp.db.database import get_db_connection, init_db
from linkedin_mcp.db.schema import DeterministicJobSchema, JobQueryParams, WorkplaceType, SourceType

logger = logging.getLogger("linkedin-mcp.db")


def upsert_job(
    job: DeterministicJobSchema,
    custom_path: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Insert a new job or update an existing one idempotently based on job_id.

    Returns:
        Tuple of (is_new: bool, job_id: str)
    """
    init_db(custom_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    scraped_iso = job.scraped_at.isoformat() if isinstance(job.scraped_at, datetime) else str(job.scraped_at)

    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()

        # Check if record already exists
        cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?;", (job.job_id,))
        existing = cursor.fetchone()
        is_new = existing is None

        tech_stack_json = json.dumps(job.tech_stack)

        if is_new:
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, source_type, source_url, title, company, location,
                    workplace_type, experience_min_years, experience_level,
                    tech_stack_json, salary_raw, salary_currency,
                    description_summary, raw_text, application_url,
                    hiring_contact_name, hiring_contact_profile, hiring_contact_email,
                    is_easy_apply, is_hiring_confirmed, relevance_score,
                    posted_relative, scraped_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                job.job_id,
                job.source_type.value if hasattr(job.source_type, "value") else str(job.source_type),
                job.source_url,
                job.title,
                job.company,
                job.location,
                job.workplace_type.value if hasattr(job.workplace_type, "value") else str(job.workplace_type),
                job.experience_min_years,
                job.experience_level,
                tech_stack_json,
                job.salary_raw,
                job.salary_currency,
                job.description_summary,
                job.raw_text,
                job.application_url,
                job.hiring_contact_name,
                job.hiring_contact_profile,
                job.hiring_contact_email,
                1 if job.is_easy_apply else 0,
                1 if job.is_hiring_confirmed else 0,
                job.relevance_score,
                job.posted_relative,
                scraped_iso,
                now_iso,
            ))
        else:
            cursor.execute("""
                UPDATE jobs SET
                    title = ?,
                    company = ?,
                    location = ?,
                    workplace_type = ?,
                    experience_min_years = COALESCE(?, experience_min_years),
                    experience_level = ?,
                    tech_stack_json = ?,
                    salary_raw = COALESCE(?, salary_raw),
                    description_summary = ?,
                    application_url = COALESCE(?, application_url),
                    hiring_contact_name = COALESCE(?, hiring_contact_name),
                    hiring_contact_profile = COALESCE(?, hiring_contact_profile),
                    hiring_contact_email = COALESCE(?, hiring_contact_email),
                    is_easy_apply = ?,
                    relevance_score = ?,
                    posted_relative = ?,
                    updated_at = ?
                WHERE job_id = ?;
            """, (
                job.title,
                job.company,
                job.location,
                job.workplace_type.value if hasattr(job.workplace_type, "value") else str(job.workplace_type),
                job.experience_min_years,
                job.experience_level,
                tech_stack_json,
                job.salary_raw,
                job.description_summary,
                job.application_url,
                job.hiring_contact_name,
                job.hiring_contact_profile,
                job.hiring_contact_email,
                1 if job.is_easy_apply else 0,
                job.relevance_score,
                job.posted_relative,
                now_iso,
                job.job_id,
            ))

        # Synchronize relational job_skills
        cursor.execute("DELETE FROM job_skills WHERE job_id = ?;", (job.job_id,))
        for skill in job.tech_stack:
            clean_skill = skill.strip()
            if clean_skill:
                cursor.execute(
                    "INSERT OR IGNORE INTO job_skills (job_id, skill) VALUES (?, ?);",
                    (job.job_id, clean_skill),
                )

        conn.commit()

    return is_new, job.job_id


def bulk_upsert_jobs(
    jobs: List[DeterministicJobSchema],
    source_name: str = "sync_run",
    custom_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Atomically upsert a batch of jobs and log the sync run to sync_runs.

    Returns:
        Dict with total, inserted, updated counts, and run_id.
    """
    init_db(custom_path)
    inserted = 0
    updated = 0

    for job in jobs:
        is_new, _ = upsert_job(job, custom_path=custom_path)
        if is_new:
            inserted += 1
        else:
            updated += 1

    # Record sync run
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sync_runs (source, total_scraped, new_inserted, updated, run_at)
            VALUES (?, ?, ?, ?, ?);
        """, (source_name, len(jobs), inserted, updated, now_iso))
        run_id = cursor.lastrowid
        conn.commit()

    return {
        "run_id": run_id,
        "total": len(jobs),
        "inserted": inserted,
        "updated": updated,
        "run_at": now_iso,
    }


def query_stored_jobs(
    params: JobQueryParams,
    custom_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Filter and query stored jobs from SQLite.
    """
    init_db(custom_path)

    clauses = ["is_hiring_confirmed = 1"]
    args: List[Any] = []

    if params.keywords:
        kw = f"%{params.keywords.strip()}%"
        clauses.append("(title LIKE ? OR description_summary LIKE ? OR company LIKE ?)")
        args.extend([kw, kw, kw])

    if params.location:
        loc = f"%{params.location.strip()}%"
        clauses.append("location LIKE ?")
        args.append(loc)

    if params.workplace_type and params.workplace_type != "all":
        clauses.append("workplace_type = ?")
        args.append(params.workplace_type.lower())

    if params.source_type and params.source_type != "all":
        clauses.append("source_type = ?")
        args.append(params.source_type.lower())

    if params.min_score is not None:
        clauses.append("relevance_score >= ?")
        args.append(params.min_score)

    if params.days_back is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=params.days_back)).isoformat()
        clauses.append("scraped_at >= ?")
        args.append(cutoff)

    # Filter by required skills
    if params.skills:
        placeholders = ",".join("?" for _ in params.skills)
        clauses.append(f"""
            job_id IN (
                SELECT job_id FROM job_skills
                WHERE LOWER(skill) IN ({placeholders})
                GROUP BY job_id
                HAVING COUNT(DISTINCT LOWER(skill)) >= 1
            )
        """)
        args.extend([s.strip().lower() for s in params.skills])

    where_sql = " AND ".join(clauses)
    query_sql = f"""
        SELECT * FROM jobs
        WHERE {where_sql}
        ORDER BY scraped_at DESC, relevance_score DESC
        LIMIT ? OFFSET ?;
    """
    args.extend([params.limit, params.offset])

    results: List[Dict[str, Any]] = []
    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query_sql, args)
        rows = cursor.fetchall()

        for row in rows:
            d = dict(row)
            try:
                d["tech_stack"] = json.loads(d.get("tech_stack_json", "[]"))
            except Exception:
                d["tech_stack"] = []
            d.pop("tech_stack_json", None)
            d["is_easy_apply"] = bool(d.get("is_easy_apply", 0))
            d["is_hiring_confirmed"] = bool(d.get("is_hiring_confirmed", 1))
            results.append(d)

    return results


def get_storage_stats(custom_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Retrieve analytical and summary statistics of stored jobs.
    """
    init_db(custom_path)
    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jobs;")
        total_jobs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE source_type = 'job_board';")
        job_board_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE source_type = 'feed_post';")
        feed_post_count = cursor.fetchone()[0]

        # Top skills
        cursor.execute("""
            SELECT skill, COUNT(*) as count
            FROM job_skills
            GROUP BY skill
            ORDER BY count DESC
            LIMIT 12;
        """)
        top_skills = [{"skill": r[0], "count": r[1]} for r in cursor.fetchall()]

        # Top hiring companies
        cursor.execute("""
            SELECT company, COUNT(*) as count
            FROM jobs
            GROUP BY company
            ORDER BY count DESC
            LIMIT 8;
        """)
        top_companies = [{"company": r[0], "count": r[1]} for r in cursor.fetchall()]

        # Latest sync run
        cursor.execute("""
            SELECT run_id, source, total_scraped, new_inserted, updated, run_at
            FROM sync_runs
            ORDER BY run_id DESC
            LIMIT 1;
        """)
        latest_run_row = cursor.fetchone()
        latest_run = dict(latest_run_row) if latest_run_row else None

    return {
        "total_jobs": total_jobs,
        "job_board_jobs": job_board_count,
        "feed_post_jobs": feed_post_count,
        "top_skills": top_skills,
        "top_companies": top_companies,
        "latest_sync_run": latest_run,
    }


def get_job_by_id(job_id: str, custom_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full details of a specific job opening by its job_id."""
    init_db(custom_path)
    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["tech_stack"] = json.loads(d.get("tech_stack_json", "[]"))
        except Exception:
            d["tech_stack"] = []
        d.pop("tech_stack_json", None)
        d["is_easy_apply"] = bool(d.get("is_easy_apply", 0))
        d["is_hiring_confirmed"] = bool(d.get("is_hiring_confirmed", 1))
        return d


def get_jobs_for_context(custom_path: Optional[Path] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve a concise list of jobs for LLM grounding and UI dropdowns."""
    init_db(custom_path)
    with get_db_connection(custom_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT job_id, title, company, location, workplace_type, source_type,
                   posted_relative, hiring_contact_name, hiring_contact_email,
                   tech_stack_json, description_summary, source_url
            FROM jobs
            WHERE is_hiring_confirmed = 1
            ORDER BY scraped_at DESC
            LIMIT ?;
        """, (limit,))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            try:
                d["tech_stack"] = json.loads(d.get("tech_stack_json", "[]"))
            except Exception:
                d["tech_stack"] = []
            d.pop("tech_stack_json", None)
            results.append(d)
        return results

