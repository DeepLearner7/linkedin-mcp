"""
Tests for DeterministicJobSchema and ID generation.
"""

from datetime import datetime
from linkedin_mcp.db.schema import (
    DeterministicJobSchema,
    WorkplaceType,
    SourceType,
    generate_job_id,
)


def test_generate_job_id_job_board():
    url = "https://www.linkedin.com/jobs/view/4461144578/?refId=123"
    job_id = generate_job_id(SourceType.JOB_BOARD, url)
    assert job_id == "job_4461144578"


def test_generate_job_id_feed_post():
    url = "https://www.linkedin.com/feed/update/urn:li:activity:71234567890/"
    post_id = generate_job_id(SourceType.FEED_POST, url)
    assert post_id.startswith("post_")
    assert len(post_id) > 10

    # Ensure deterministic output
    post_id_2 = generate_job_id(SourceType.FEED_POST, url)
    assert post_id == post_id_2


def test_job_schema_defaults_and_validation():
    job = DeterministicJobSchema(
        job_id="job_12345",
        source_type=SourceType.JOB_BOARD,
        source_url="https://www.linkedin.com/jobs/view/12345/",
        title="Senior Data Engineer",
        company="Mastercard",
        location="Pune, India",
        workplace_type=WorkplaceType.HYBRID,
        tech_stack=["PySpark", "Kafka", "pyspark", "SQL"],
        experience_min_years=5,
    )

    assert job.job_id == "job_12345"
    assert job.workplace_type == WorkplaceType.HYBRID
    # Check deduplication in tech_stack (case-insensitive dedupe preserves first seen)
    assert len(job.tech_stack) == 3
    assert "PySpark" in job.tech_stack
    assert "Kafka" in job.tech_stack
    assert "SQL" in job.tech_stack
    assert job.relevance_score == 1.0
    assert job.is_hiring_confirmed is True
    assert isinstance(job.scraped_at, datetime)
