# LinkedIn MCP Server

A Python-based [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for LinkedIn integration, built for **Google Antigravity (`agy`)** and compatible with Claude Code.

Installed once, it is available **system-wide** across any project directory on your machine.

---

## Features

- **Global Availability:** Registers into `~/.gemini/config/mcp_config.json` (and optionally `~/.claude.json`).
- **Live Local Development:** Installed in editable mode (`pip install -e .`). Code changes you make in this repository are immediately active without reinstalling.
- **Built-in Tools:**
  - `linkedin_status`: Diagnostic check of MCP connection, API credentials, browser session, and daily safety stats.
  - `linkedin_search_feed_posts`: Live search for posts by keywords with date/sort filters and computed engagement scores (reactions & comments).
  - `linkedin_comment_on_post`: Post insightful comments to LinkedIn posts with built-in daily safety limits.
  - `linkedin_search_people`: Find targeted leads, hiring managers, recruiters, or peers.
  - `linkedin_send_connect_request`: Send connection requests with custom personalized notes (up to 300 chars).
  - `linkedin_get_safety_stats`: View daily remaining quota for comments and connection invites.
  - `linkedin_search_jobs`: Search the official LinkedIn Job Board by keywords, location (e.g. 'Pune'), workplace type ('remote', 'hybrid', 'onsite'), experience level, and date posted, with pagination support.
  - `linkedin_get_job_details`: Fetch full job descriptions, role requirements, and hiring details by job ID or URL.
  - `linkedin_save_parsed_jobs`: Validate and bulk-upsert parsed openings into local SQLite database with deterministic deduplication.
  - `linkedin_query_stored_jobs`: Query and filter stored openings from local SQLite by skills, location, or date with zero network calls.
  - `linkedin_get_db_stats`: Analytical statistics on stored jobs, top in-demand skills, and latest sync history.
  - `linkedin_get_profile`: Fetch profile details by member ID or `me`.
  - `linkedin_create_post`: Publish or draft text posts with visibility control.

---

## Installation (Clone & Run Anywhere)

To install this on any machine:

```bash
# 1. Clone the repository
git clone https://github.com/DeepLearner7/linkedin-mcp.git
cd linkedin-mcp

# 2. Run the automated installer
./install.sh
```

The installer will:
1. Create a isolated `.venv` virtual environment.
2. Install all dependencies and the package in editable mode.
3. Automatically register the server globally in `~/.gemini/config/mcp_config.json`.
4. Create a local `.env` file from `.env.example`.

### Also Enable for Claude Code CLI

If you also use Claude Code CLI, pass the `--claude` flag:

```bash
./install.sh --claude
```

---

## Authentication & Setup

### 1. Browser Session Authentication (For Post Search, Comments & Connect Requests)

To search public posts, interact, and send connection requests, LinkedIn requires a logged-in browser session. Run the interactive login helper:

```bash
python login.py
```

This will launch a visible Chromium window:
1. Log into your LinkedIn account normally.
2. Complete 2FA or CAPTCHA if prompted.
3. Once you reach the feed, the session is captured automatically and saved to `~/.config/linkedin-mcp/session.json`.

*(Alternatively, you can set `LINKEDIN_LI_AT_COOKIE=your_cookie` in `.env` if you prefer).*

### 2. LinkedIn REST API (Optional, for Publishing Posts directly)

Add your LinkedIn OAuth2 Access Token to `.env`:

```bash
LINKEDIN_ACCESS_TOKEN=your_oauth_token_here
```

Tokens can be created from the [LinkedIn Developer Portal](https://www.linkedin.com/developers/).

The server checks for `.env` in:
1. Current working directory
2. The `linkedin-mcp` repository root
3. `~/.config/linkedin-mcp/.env`
4. Direct environment variable (`export LINKEDIN_ACCESS_TOKEN=...`)

---

## Using with Antigravity (`agy`)

1. Open a terminal in **any** folder on your computer and start `agy`:
   ```bash
   agy
   ```
2. Type `/mcp` to verify:
   - You will see `linkedin` listed under active MCP servers with its tools.
3. Ask the agent directly:
    - *"Check linkedin_status to see if my connection is working."*
    - *"Fetch my linkedin profile details."*
    - *"Draft and post a LinkedIn update announcing our new MCP server."*
    - *"Sync today's Senior Data Engineer openings in Pune and save them to the database."*
    - *"Query stored jobs from the database that require Spark and Kafka."*

---

## Daily Job Scraping & Database Storage

The system includes a daily scraping, deterministic schema extraction, and SQLite database storage pipeline for job board openings and recruiter feed posts:

### 1. Automated Daily Background Cron (Headless Antigravity)
Install the daily cron schedule (defaults to 9:00 AM every morning):
```bash
./scripts/setup_cron.sh --install
```

### 2. Manual On-Demand Sync via CLI
```bash
# Sync jobs and feed posts for Senior Data Engineer in Pune
python -m linkedin_mcp.pipeline.cli --keywords "Senior Data Engineer" --location "Pune" --limit 15

# Export to a markdown report
python -m linkedin_mcp.pipeline.cli --keywords "Senior Data Engineer" --location "Pune" --export markdown --output daily_report.md
```

### 3. Instant Local Querying (Zero Network Calls)
```bash
# Query stored openings by required skills
python -m linkedin_mcp.pipeline.cli --skills "Spark, Kafka"

# Query by company or keyword
python -m linkedin_mcp.pipeline.cli --query "Mastercard"

# View storage analytics and top in-demand skills
python -m linkedin_mcp.pipeline.cli --stats
```

The database is stored locally at `data/linkedin_jobs.db` with SQLite WAL mode and automatic deduplication (`ON CONFLICT(job_id) DO UPDATE`).

## Local Development & Adding Tools

Because the package is installed in editable mode (`pip install -e .`), any edits you make to `src/linkedin_mcp/server.py` are live immediately:

1. Open `src/linkedin_mcp/server.py`.
2. Add a new tool decorated with `@app.tool()`:

```python
@app.tool()
def linkedin_get_connections_count() -> str:
    """Return the total number of LinkedIn connections."""
    return "You have 500+ connections."
```

3. Save the file. The next time an agent runs, the new tool is automatically discovered!

> **Important**: Never use `print()` for debugging inside server code; it writes to `stdout` and breaks the stdio JSON-RPC stream. Use `logger.info()` instead, which writes safely to `stderr`.

---

## Uninstallation

To remove the global registration:

```bash
python3 install.py --uninstall
```
