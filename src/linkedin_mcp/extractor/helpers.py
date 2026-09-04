"""
Deterministic extraction and heuristic helper utilities for parsing LinkedIn posts.
"""

import re
from typing import List, Optional, Tuple

# Comprehensive Data Engineering, Cloud, & AI Technology Taxonomy
TECH_TAXONOMY = [
    # Distributed & Big Data Processing
    "PySpark", "Apache Spark", "Spark", "Databricks", "Apache Kafka", "Kafka",
    "Apache NiFi", "NiFi", "Apache Flink", "Flink", "Hadoop", "Hive", "Presto", "Trino",
    "Airflow", "Dagster", "Prefect", "DBT", "Luigi", "Beam",

    # Lakehouse & Storage Formats
    "Delta Lake", "Apache Iceberg", "Iceberg", "Apache Hudi", "Hudi",
    "Parquet", "Avro", "Ceph", "Apache Ozone",

    # Cloud Data Warehouses & Lake Platforms
    "Snowflake", "BigQuery", "Redshift", "Azure Synapse", "Microsoft Fabric",
    "Fabric", "AWS Glue", "Glue", "AWS EMR", "EMR", "Athena", "ADLS", "S3",

    # Cloud Providers
    "AWS", "Azure", "GCP", "Google Cloud",

    # Relational & NoSQL Databases
    "PostgreSQL", "Postgres", "MySQL", "Oracle", "PL/SQL", "MongoDB",
    "Cassandra", "Redis", "DynamoDB", "Neo4j", "GraphDB", "Elasticsearch",

    # Languages & Core Engineering
    "Python", "SQL", "Scala", "Java", "Go", "Rust", "Bash", "Linux",
    "Docker", "Kubernetes", "Terraform", "CI/CD", "Git",

    # ETL & Integration Tools
    "Informatica", "Talend", "Ab Initio", "ODI", "Oracle Data Integrator",
    "Fivetran", "Airbyte", "Stitch", "DataStage"
]

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

URL_REGEX = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
)

EXPERIENCE_REGEXES = [
    re.compile(r"(\d{1,2})\s*(?:\+|-\s*\d{1,2})?\s*(?:years?|yrs?)(?:\s+of)?\s+experience", re.IGNORECASE),
    re.compile(r"experience\s*:\s*(\d{1,2})\s*(?:\+|-\s*\d{1,2})?\s*(?:years?|yrs?)", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b", re.IGNORECASE),
]

# Hiring triggers vs candidate self-promotion triggers
NEGATIVE_TRIGGERS = [
    "looking for a job", "looking for an opportunity", "looking for opportunities",
    "looking for new opportunities", "looking for my next role", "looking for my next opportunity",
    "seeking new opportunities", "seeking a job", "seeking a role",
    "open to work", "#opentowork", "recently laid off",
    "thrilled to announce that i have joined", "excited to share that i've joined",
    "happy to share that i have joined", "started a new position",
    "started a new role", "joined as", "completed my certification"
]

POSITIVE_TRIGGERS = [
    "we are hiring", "we're hiring", "our team is hiring", "urgent requirement",
    "immediate opening", "immediate requirement", "job alert", "#hiring", "actively hiring",
    "hiring for", "send your resume", "share your cv", "send cv to", "share resume to",
    "send your cv", "apply here", "apply at", "open positions", "open roles",
    "join our team", "looking for a", "looking for senior", "looking for data",
    "dm me your resume", "dm your resume", "drop your cv", "drop your resume",
    "dm your profile", "reach out to me at", "interested candidates can share"
]


def extract_emails(text: str) -> List[str]:
    """Extract distinct valid email addresses from text."""
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    # Filter out common false positives (e.g. image extensions)
    valid = []
    for m in matches:
        lower = m.lower()
        if not any(lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            if lower not in [v.lower() for v in valid]:
                valid.append(m)
    return valid


def extract_urls(text: str) -> List[str]:
    """Extract application links, forms, and external URLs."""
    if not text:
        return []
    matches = URL_REGEX.findall(text)
    urls = []
    for u in matches:
        clean = u.rstrip(".,;!)\"'>")
        if clean not in urls:
            urls.append(clean)
    return urls


def extract_experience_years(text: str) -> Optional[int]:
    """Extract minimum required years of experience from text."""
    if not text:
        return None
    for pattern in EXPERIENCE_REGEXES:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
    return None


def match_tech_stack(text: str) -> List[str]:
    """Match key data engineering skills and tools present in text."""
    if not text:
        return []
    matched = []
    for tech in TECH_TAXONOMY:
        # Word boundary match to prevent substring false matches (e.g., 'R' in 'Spark')
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(tech) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            matched.append(tech)
    return matched


def is_likely_hiring_post(text: str) -> Tuple[bool, str]:
    """
    Check whether a post represents a legitimate job opening announcement.
    Returns (is_hiring: bool, reason: str).
    """
    if not text or len(text.strip()) < 20:
        return False, "Post text too short"

    lower = text.lower()

    # Check for candidate / job seeker / celebratory triggers
    for neg in NEGATIVE_TRIGGERS:
        if neg in lower:
            # Verify it's not actually a recruiter post sharing an opening
            if not any(pos in lower for pos in ["we are hiring", "we're hiring", "hiring for", "urgent requirement"]):
                return False, f"Matches candidate/celebratory pattern: '{neg}'"

    # Check for positive hiring triggers
    for pos in POSITIVE_TRIGGERS:
        if pos in lower:
            return True, f"Matches hiring trigger: '{pos}'"

    # Secondary heuristic: mentions data engineering / platform role terms and hiring context words
    role_terms = ["data engineer", "data engineering", "data platform", "platform engineer"]
    context_words = [
        "experience", "location", "apply", "contact", "pune", "bangalore", "bengaluru",
        "salary", "lead", "hybrid", "remote", "onsite", "resumes", "cv", "email", "mail",
        "candidate", "opening", "openings", "skills", "kafka", "spark", "sql"
    ]
    if any(r in lower for r in role_terms) and any(w in lower for w in context_words):
        return True, "Contextual match for Data Engineering / Platform role announcement"

    # If an email address is present alongside data skills, treat as hiring lead
    emails = extract_emails(text)
    if emails and any(s in lower for s in ["spark", "python", "kafka", "sql", "data"]):
        return True, f"Contains recruiter contact email ({emails[0]}) with data skills"

    return False, "No strong hiring signals found"
