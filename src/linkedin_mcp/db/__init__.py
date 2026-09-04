"""
Database package for LinkedIn MCP job storage and querying.
"""

from linkedin_mcp.db.schema import (
    DeterministicJobSchema,
    WorkplaceType,
    SourceType,
    generate_job_id,
)
from linkedin_mcp.db.database import get_db_connection, init_db, DEFAULT_DB_PATH
from linkedin_mcp.db.repository import (
    upsert_job,
    bulk_upsert_jobs,
    query_stored_jobs,
    get_storage_stats,
)

__all__ = [
    "DeterministicJobSchema",
    "WorkplaceType",
    "SourceType",
    "generate_job_id",
    "get_db_connection",
    "init_db",
    "DEFAULT_DB_PATH",
    "upsert_job",
    "bulk_upsert_jobs",
    "query_stored_jobs",
    "get_storage_stats",
]
