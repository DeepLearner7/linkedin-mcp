"""
Pipeline package for orchestrating LinkedIn job scraping, extraction, and database persistence.
"""

from linkedin_mcp.pipeline.orchestrator import run_job_sync

__all__ = ["run_job_sync"]
