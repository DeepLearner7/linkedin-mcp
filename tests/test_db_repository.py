"""
Tests for SQLite repository, schema DDL, upserts, queries, and analytics.
"""

from pathlib import Path
import pytest
from linkedin_mcp.db.schema import DeterministicJobSchema, JobQueryParams, WorkplaceType, SourceType
from linkedin_mcp.db.repository import (
    upsert_job,
    bulk_upsert_jobs,
    query_stored_jobs,
    get_storage_stats,
)


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_jobs.db"


def test_upsert_single_job_and_idempotency(test_db_path: Path):
    job = DeterministicJobSchema(
        job_id="job_4461144578",
        source_type=SourceType.JOB_BOARD,
        source_url="https://www.linkedin.com/jobs/view/4461144578/",
        title="Senior Data Engineer - Spark / Kafka / NiFi",
        company="Mastercard",
        location="Pune Division, Maharashtra, India (Hybrid)",
        workplace_type=WorkplaceType.HYBRID,
        tech_stack=["Spark", "Kafka", "NiFi", "Scala"],
        experience_min_years=6,
        description_summary="Lead large-scale streaming pipelines.",
    )

    # 1. Insert new job
    is_new, job_id = upsert_job(job, custom_path=test_db_path)
    assert is_new is True
    assert job_id == "job_4461144578"

    # 2. Update existing job (simulate re-scraping with new summary)
    job.description_summary = "Updated responsibilities for real-time platforms."
    is_new_2, job_id_2 = upsert_job(job, custom_path=test_db_path)
    assert is_new_2 is False
    assert job_id_2 == "job_4461144578"

    # Verify query returns exactly 1 updated record
    results = query_stored_jobs(JobQueryParams(keywords="Mastercard"), custom_path=test_db_path)
    assert len(results) == 1
    assert results[0]["job_id"] == "job_4461144578"
    assert results[0]["description_summary"] == "Updated responsibilities for real-time platforms."
    assert "Spark" in results[0]["tech_stack"]


def test_bulk_upsert_and_skill_filtering(test_db_path: Path):
    jobs = [
        DeterministicJobSchema(
            job_id="job_1",
            source_type=SourceType.JOB_BOARD,
            source_url="https://www.linkedin.com/jobs/view/1/",
            title="Senior Data Engineer",
            company="Citi",
            location="Pune, India",
            workplace_type=WorkplaceType.HYBRID,
            tech_stack=["Databricks", "PySpark", "AWS"],
            experience_min_years=8,
        ),
        DeterministicJobSchema(
            job_id="post_2",
            source_type=SourceType.FEED_POST,
            source_url="https://www.linkedin.com/feed/update/urn:li:activity:2/",
            title="Lead Data Engineer",
            company="FinTech Startup",
            location="Pune, India",
            workplace_type=WorkplaceType.REMOTE,
            tech_stack=["Snowflake", "dbt", "Airflow"],
            hiring_contact_email="careers@startup.io",
        ),
    ]

    summary = bulk_upsert_jobs(jobs, source_name="test_sync", custom_path=test_db_path)
    assert summary["total"] == 2
    assert summary["inserted"] == 2
    assert summary["updated"] == 0

    # Query by skill: Databricks
    databricks_jobs = query_stored_jobs(
        JobQueryParams(skills=["databricks"]),
        custom_path=test_db_path,
    )
    assert len(databricks_jobs) == 1
    assert databricks_jobs[0]["company"] == "Citi"

    # Query by source_type: feed_post
    feed_jobs = query_stored_jobs(
        JobQueryParams(source_type="feed_post"),
        custom_path=test_db_path,
    )
    assert len(feed_jobs) == 1
    assert feed_jobs[0]["hiring_contact_email"] == "careers@startup.io"

    # Query stats
    stats = get_storage_stats(custom_path=test_db_path)
    assert stats["total_jobs"] == 2
    assert stats["job_board_jobs"] == 1
    assert stats["feed_post_jobs"] == 1
    assert any(s["skill"] == "Databricks" for s in stats["top_skills"])
