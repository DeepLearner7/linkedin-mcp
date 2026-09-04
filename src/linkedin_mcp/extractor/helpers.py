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
    "i am looking for", "i'm looking for", "open to work", "#opentowork",
    "seeking new opportunities", "looking for my next role", "recently laid off",
    "thrilled to announce that i have joined", "excited to share that i've joined",
    "happy to share that i have joined", "started a new position",
]

POSITIVE_TRIGGERS = [
    "we are hiring", "we're hiring", "our team is hiring", "urgent requirement",
    "immediate opening", "job alert", "looking for a senior data engineer",
    "looking for senior data engineer", "hiring for", "send your resume",
    "share your cv", "send cv to", "share resume to", "apply here",
    "apply at", "open positions", "join our team",
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
            return False, f"Matches candidate/celebratory pattern: '{neg}'"

    # Check for positive hiring triggers
    for pos in POSITIVE_TRIGGERS:
        if pos in lower:
            return True, f"Matches hiring trigger: '{pos}'"

    # Secondary heuristic: mentions 'data engineer' and ('apply' or 'email' or 'experience')
    if "data engineer" in lower and any(w in lower for w in ["experience", "location", "apply", "contact", "pune", "salary"]):
        return True, "Contextual match for Data Engineer role announcement"

    return False, "No strong hiring signals found"
