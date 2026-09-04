"""
SQLite Database connection, configuration, and DDL schema manager.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

# Default database location: <repo_root>/data/linkedin_jobs.db
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB_PATH = Path(
    os.getenv("LINKEDIN_JOBS_DB_PATH", str(_REPO_ROOT / "data" / "linkedin_jobs.db"))
)


def get_db_path(custom_path: Optional[Path] = None) -> Path:
    """Get the target database file path, ensuring parent directory exists."""
    path = custom_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_db_connection(custom_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Establish an optimized connection to the SQLite database.
    Enables WAL mode, foreign keys, and dictionary-like Row factory.
    """
    path = get_db_path(custom_path)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(custom_path: Optional[Path] = None) -> None:
    """
    Initialize all database tables and indexes if they do not exist.
    """
    with get_db_connection(custom_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            workplace_type TEXT NOT NULL,
            experience_min_years INTEGER,
            experience_level TEXT,
            tech_stack_json TEXT NOT NULL,
            salary_raw TEXT,
            salary_currency TEXT,
            description_summary TEXT,
            raw_text TEXT,
            application_url TEXT,
            hiring_contact_name TEXT,
            hiring_contact_profile TEXT,
            hiring_contact_email TEXT,
            is_easy_apply INTEGER NOT NULL DEFAULT 0,
            is_hiring_confirmed INTEGER NOT NULL DEFAULT 1,
            relevance_score REAL NOT NULL DEFAULT 1.0,
            posted_relative TEXT,
            scraped_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_source_type ON jobs(source_type);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
        CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_relevance ON jobs(relevance_score);

        CREATE TABLE IF NOT EXISTS job_skills (
            job_id TEXT NOT NULL,
            skill TEXT NOT NULL,
            PRIMARY KEY (job_id, skill),
            FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill);

        CREATE TABLE IF NOT EXISTS sync_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            total_scraped INTEGER NOT NULL,
            new_inserted INTEGER NOT NULL,
            updated INTEGER NOT NULL,
            run_at TEXT NOT NULL
        );
        """)
