"""
Pydantic v2 deterministic schema definitions for LinkedIn jobs and posts.
"""

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class WorkplaceType(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNSPECIFIED = "unspecified"


class SourceType(str, Enum):
    JOB_BOARD = "job_board"
    FEED_POST = "feed_post"


def generate_job_id(
    source_type: str,
    source_url: str,
    title: str = "",
    company: str = "",
) -> str:
    """
    Generate a deterministic, canonical job_id.
    - If job board URL contains numeric ID (e.g. /jobs/view/123456/), returns 'job_123456'.
    - Otherwise, generates SHA-256 hash of canonicalized URL or content signature.
    """
    if source_type in (SourceType.JOB_BOARD, "job_board"):
        match = re.search(r"/jobs/view/(\d+)", source_url)
        if match:
            return f"job_{match.group(1)}"

    # Normalize URL: strip query parameters and trailing slashes
    clean_url = source_url.split("?")[0].rstrip("/").lower()
    if clean_url and clean_url != "https://www.linkedin.com":
        raw = f"{source_type}:{clean_url}"
    else:
        # Fallback to normalized title and company
        norm_title = re.sub(r"\W+", "", title.lower())
        norm_company = re.sub(r"\W+", "", company.lower())
        raw = f"{source_type}:{norm_title}:{norm_company}"

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    prefix = "job" if source_type in (SourceType.JOB_BOARD, "job_board") else "post"
    return f"{prefix}_{digest}"


class DeterministicJobSchema(BaseModel):
    """
    Strict, deterministic schema capturing complete job opening information.
    """
    job_id: str = Field(
        description="Deterministic unique ID (e.g. 'job_4461144578' or 'post_e3b0c44298fc1c14')"
    )
    source_type: SourceType = Field(
        description="'job_board' for official job postings or 'feed_post' for recruiter posts"
    )
    source_url: str = Field(
        description="Canonical URL to job opening or post"
    )

    # Core metadata
    title: str = Field(
        description="Normalized Job Title (e.g. 'Senior Data Engineer')"
    )
    company: str = Field(
        description="Hiring Company or Organization Name"
    )
    location: str = Field(
        default="Pune, India",
        description="Standardized location (e.g. 'Pune, Maharashtra, India')"
    )
    workplace_type: WorkplaceType = Field(
        default=WorkplaceType.UNSPECIFIED,
        description="Workplace model: onsite, hybrid, remote, or unspecified"
    )

    # Requirements & Seniority
    experience_min_years: Optional[int] = Field(
        default=None,
        description="Minimum years of experience required (e.g. 5)"
    )
    experience_level: str = Field(
        default="mid-senior",
        description="Seniority classification: entry, associate, mid-senior, lead, director"
    )
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Normalized list of key technologies (e.g. ['PySpark', 'Kafka', 'Databricks', 'AWS'])"
    )

    # Compensation (if disclosed)
    salary_raw: Optional[str] = Field(
        default=None,
        description="Raw salary/compensation string if mentioned (e.g. '25-35 LPA', '$150k')"
    )
    salary_currency: Optional[str] = Field(
        default=None,
        description="Currency code: INR, USD, EUR, etc."
    )

    # Summary & Content
    description_summary: str = Field(
        default="",
        description="Concise 2-4 sentence summary of responsibilities and qualifications"
    )
    raw_text: str = Field(
        default="",
        description="Raw post text or full job description"
    )

    # Application & Contact Details
    application_url: Optional[str] = Field(
        default=None,
        description="Direct application link (ATS, external form, or job board URL)"
    )
    hiring_contact_name: Optional[str] = Field(
        default=None,
        description="Name of recruiter, hiring manager, or poster"
    )
    hiring_contact_profile: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL of the recruiter/poster"
    )
    hiring_contact_email: Optional[str] = Field(
        default=None,
        description="Direct recruiter/careers contact email"
    )
    is_easy_apply: bool = Field(
        default=False,
        description="True if LinkedIn Easy Apply is available"
    )

    # Scoring & Validation
    is_hiring_confirmed: bool = Field(
        default=True,
        description="True if verified active hiring opening (filters out job seekers / generic announcements)"
    )
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Match score against target search criteria from 0.0 to 1.0"
    )

    # Timestamps
    posted_relative: str = Field(
        default="recently",
        description="Relative posting time string (e.g. '3 hours ago', '1 day ago')"
    )
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the job was ingested"
    )

    @field_validator("title", "company", mode="before")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "Unknown"
        return v.strip()

    @field_validator("tech_stack", mode="before")
    @classmethod
    def normalize_tech_stack(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = [s.strip() for s in v.split(",") if s.strip()]
        # Deduplicate while preserving order and casing
        seen = set()
        deduped = []
        for item in v:
            clean = str(item).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                deduped.append(clean)
        return deduped


class JobQueryParams(BaseModel):
    """Parameters for querying stored jobs from the database."""
    keywords: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None
    workplace_type: Optional[str] = None
    source_type: Optional[str] = None
    min_score: Optional[float] = None
    days_back: Optional[int] = None
    limit: int = 20
    offset: int = 0


class SyncRunSummary(BaseModel):
    """Audit summary of an automated or manual sync run."""
    run_id: Optional[int] = None
    source: str
    total_scraped: int
    new_inserted: int
    updated: int
    run_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
