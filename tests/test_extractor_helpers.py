"""
Tests for extraction helpers: emails, URLs, experience, tech stack, and hiring classification.
"""

from linkedin_mcp.extractor.helpers import (
    extract_emails,
    extract_urls,
    extract_experience_years,
    match_tech_stack,
    is_likely_hiring_post,
)


def test_extract_emails():
    text = "Please send your resume to priya.recruiter@techcorp.com or talent-team@fintech.io! Avoid avatar.png"
    emails = extract_emails(text)
    assert "priya.recruiter@techcorp.com" in emails
    assert "talent-team@fintech.io" in emails
    assert not any("avatar.png" in e for e in emails)


def test_extract_urls():
    text = "Apply directly via our form: https://forms.gle/xyz123 or visit https://jobs.lever.co/company/role."
    urls = extract_urls(text)
    assert "https://forms.gle/xyz123" in urls
    assert "https://jobs.lever.co/company/role" in urls


def test_extract_experience_years():
    assert extract_experience_years("Looking for candidates with 5+ years of experience in Big Data") == 5
    assert extract_experience_years("Experience: 7-9 yrs required") == 7
    assert extract_experience_years("Must have 8+ yrs building pipelines") == 8
    assert extract_experience_years("No explicit number") is None


def test_match_tech_stack():
    text = "We are seeking a Senior Data Engineer skilled in PySpark, Databricks, Apache Kafka, and AWS Glue with Postgres and Docker."
    skills = match_tech_stack(text)
    assert "PySpark" in skills
    assert "Databricks" in skills
    assert "Kafka" in skills
    assert "AWS Glue" in skills
    assert "Postgres" in skills
    assert "Docker" in skills


def test_is_likely_hiring_post_positive():
    hiring_text = "We're hiring a Senior Data Engineer in Pune! Join our high-scale data platform team. Apply at careers@company.com"
    is_hiring, reason = is_likely_hiring_post(hiring_text)
    assert is_hiring is True

    platform_text = "Looking for a Senior Data Platform Engineer in Bangalore. Experience with Kubernetes, Kafka, and Snowflake. Send CV to hr@clouddata.io"
    is_hiring_p, _ = is_likely_hiring_post(platform_text)
    assert is_hiring_p is True

    lead_text = "Job Alert: Data Engineering Lead in Bengaluru! 10+ years experience building data architectures. Apply at careers@tech.com"
    is_hiring_l, _ = is_likely_hiring_post(lead_text)
    assert is_hiring_l is True


def test_is_likely_hiring_post_negative():
    candidate_text = "I'm excited to share that I've joined Google as a Senior Data Engineer! Looking forward to this new chapter. #opentowork"
    is_hiring, reason = is_likely_hiring_post(candidate_text)
    assert is_hiring is False
