"""
Tests for FastAPI Web UI, Career Copilot, and REST endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from linkedin_mcp.ui.server import app


@pytest.mark.asyncio
async def test_ui_index():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "LinkedIn Career Intelligence" in resp.text


@pytest.mark.asyncio
async def test_ui_stats():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_jobs" in data
        assert "job_board_jobs" in data
        assert "feed_post_jobs" in data
        assert isinstance(data["total_jobs"], int)


@pytest.mark.asyncio
async def test_ui_jobs_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/jobs?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "count" in data
        assert len(data["jobs"]) <= 10


@pytest.mark.asyncio
async def test_ui_jobs_brief():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/jobs/brief?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "job_id" in data[0]
            assert "title" in data[0]
            assert "company" in data[0]


@pytest.mark.asyncio
async def test_ui_settings_get_and_post():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get settings
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_provider" in data
        assert "user_profile" in data

        # Post update
        post_resp = await client.post("/api/settings", json={
            "user_profile": "Senior Data Architect with 12+ years experience in Snowflake and Kafka."
        })
        assert post_resp.status_code == 200
        assert post_resp.json()["status"] == "success"

        # Verify change persisted
        get_again = await client.get("/api/settings")
        assert "12+ years" in get_again.json()["user_profile"]


@pytest.mark.asyncio
async def test_ui_chat_no_key_graceful_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/ai/chat", json={
            "message": "Draft a recruiter outreach note.",
            "target_job_id": "all"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        # If no key set, should provide friendly instruction instead of 500 error
        assert len(data["reply"]) > 0


@pytest.mark.asyncio
async def test_ui_sync_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "logs" in data
