"""
Comprehensive test suite for AI settings, multi-provider LLM client, Career Copilot,
and edge cases in repository and UI server.
"""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport

from linkedin_mcp.ai.client import LLMClient
from linkedin_mcp.ai.copilot import CareerCopilot
from linkedin_mcp.ai.settings import load_settings, save_settings, DEFAULT_SETTINGS
from linkedin_mcp.db.repository import get_job_by_id, get_jobs_for_context, upsert_job
from linkedin_mcp.db.schema import DeterministicJobSchema, SourceType, WorkplaceType
from linkedin_mcp.ui.server import app, sync_state


# --- 1. Settings Tests ---
def test_settings_load_and_save(tmp_path):
    with patch("linkedin_mcp.ai.settings.SETTINGS_FILE", tmp_path / "settings.json"), \
         patch("linkedin_mcp.ai.settings.SETTINGS_DIR", tmp_path):
        
        # Initial load defaults
        cfg = load_settings()
        assert cfg["llm_provider"] == "gemini"
        assert cfg["gemini_model"] == "gemini-1.5-flash"
        assert "Lead / Senior Data Engineer" in cfg["user_profile"]

        # Save updates
        save_settings({
            "gemini_api_key": "AIzaSyTestKey123",
            "gemini_model": "gemini-2.0-flash",
            "user_profile": "Lead Streaming Architect (Kafka + Flink)"
        })

        # Reload and verify persistence
        updated = load_settings()
        assert updated["gemini_api_key"] == "AIzaSyTestKey123"
        assert updated["gemini_model"] == "gemini-2.0-flash"
        assert updated["user_profile"] == "Lead Streaming Architect (Kafka + Flink)"


# --- 2. Repository Helper Tests ---
def test_repository_get_job_by_id_and_context(tmp_path):
    db_file = tmp_path / "test_jobs.db"
    test_job = DeterministicJobSchema(
        job_id="job_unittest_9999",
        source_type=SourceType.JOB_BOARD,
        source_url="https://www.linkedin.com/jobs/view/9999/",
        title="Principal Data Platform Engineer",
        company="Antigravity Technologies",
        location="Pune, Maharashtra, India",
        workplace_type=WorkplaceType.HYBRID,
        tech_stack=["Kafka", "PySpark", "Trino"],
        hiring_contact_name="Sarah Connor",
        hiring_contact_email="sarah@example.com",
        description_summary="Leading distributed data platform.",
        raw_text="Full JD description with Kafka and PySpark requirements."
    )

    upsert_job(test_job, custom_path=db_file)

    # 1. Existing job retrieval
    retrieved = get_job_by_id("job_unittest_9999", custom_path=db_file)
    assert retrieved is not None
    assert retrieved["title"] == "Principal Data Platform Engineer"
    assert retrieved["company"] == "Antigravity Technologies"
    assert retrieved["tech_stack"] == ["Kafka", "PySpark", "Trino"]
    assert retrieved["hiring_contact_name"] == "Sarah Connor"
    assert retrieved["hiring_contact_email"] == "sarah@example.com"
    assert retrieved["is_hiring_confirmed"] is True

    # 2. Non-existent job retrieval returns None
    assert get_job_by_id("job_non_existent_0000", custom_path=db_file) is None

    # 3. Context list retrieval
    context_jobs = get_jobs_for_context(custom_path=db_file, limit=10)
    assert len(context_jobs) >= 1
    assert any(j["job_id"] == "job_unittest_9999" for j in context_jobs)
    assert isinstance(context_jobs[0]["tech_stack"], list)


# --- 3. LLM Client Tests ---
@pytest.mark.asyncio
async def test_llm_client_missing_key_warning():
    client = LLMClient(settings={"llm_provider": "gemini", "gemini_api_key": ""})
    resp = await client.generate("Draft outreach note.")
    assert "Gemini API Key Needed" in resp
    assert "aistudio.google.com" in resp


@pytest.mark.asyncio
async def test_llm_client_unknown_provider():
    client = LLMClient(settings={"llm_provider": "unknown_vendor"})
    resp = await client.generate("Hello")
    assert "Unknown LLM provider" in resp


@pytest.mark.asyncio
async def test_llm_client_gemini_success():
    client = LLMClient(settings={
        "llm_provider": "gemini",
        "gemini_api_key": "AIzaSyFakeKey",
        "gemini_model": "gemini-1.5-flash"
    })

    mock_response = MagicMock()
    mock_response.text = "Here is your personalized LinkedIn outreach note!"

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_instance

        resp = await client.generate("Draft note", system_instruction="You are a career coach")
        assert resp == "Here is your personalized LinkedIn outreach note!"
        mock_instance.aio.models.generate_content.assert_awaited_once()


# --- 4. Career Copilot Grounding Tests ---
@pytest.mark.asyncio
async def test_career_copilot_target_job_grounding(tmp_path):
    copilot = CareerCopilot()
    mock_generate = AsyncMock(return_value="Tailored connection request for Barclays!")

    with patch.object(copilot.client, "generate", mock_generate), \
         patch("linkedin_mcp.ai.copilot.get_job_by_id") as mock_get_job:

        mock_get_job.return_value = {
            "job_id": "job_123",
            "title": "Lead Data Engineer",
            "company": "Barclays",
            "location": "Pune",
            "workplace_type": "hybrid",
            "experience_level": "lead",
            "tech_stack": ["Spark", "Kafka", "AWS"],
            "hiring_contact_name": "Priya Sharma",
            "hiring_contact_email": "priya@barclays.com",
            "description_summary": "Looking for streaming lead in Pune.",
            "raw_text": "We need 10+ yrs experience in Kafka.",
            "source_url": "https://linkedin.com/jobs/view/123",
        }

        reply = await copilot.chat(
            message="Draft a recruiter note",
            target_job_id="job_123",
            conversation_history=[{"role": "user", "content": "Hi"}, {"role": "copilot", "content": "Hello!"}]
        )

        assert reply == "Tailored connection request for Barclays!"
        mock_generate.assert_awaited_once()

        call_kwargs = mock_generate.call_args.kwargs
        system_instr = call_kwargs["system_instruction"]
        prompt = call_kwargs["prompt"]

        # Verify ground truth was injected
        assert "Barclays" in system_instr
        assert "Priya Sharma" in system_instr
        assert "Spark" in system_instr
        assert "Kafka" in system_instr
        assert "Hi" in prompt  # history included


@pytest.mark.asyncio
async def test_career_copilot_all_database_grounding():
    copilot = CareerCopilot()
    mock_generate = AsyncMock(return_value="Market trend summary: PySpark and AWS are leading.")

    with patch.object(copilot.client, "generate", mock_generate), \
         patch("linkedin_mcp.ai.copilot.get_storage_stats") as mock_stats, \
         patch("linkedin_mcp.ai.copilot.get_jobs_for_context") as mock_context:

        mock_stats.return_value = {
            "total_jobs": 42,
            "job_board_jobs": 31,
            "feed_post_jobs": 11,
            "top_skills": [{"skill": "PySpark", "count": 10}, {"skill": "AWS", "count": 8}],
            "top_companies": [{"company": "Mastercard", "count": 3}],
        }
        mock_context.return_value = [
            {
                "job_id": "job_01",
                "title": "Senior Data Engineer",
                "company": "Mastercard",
                "location": "Pune",
                "workplace_type": "hybrid",
                "tech_stack": ["PySpark", "AWS"],
                "source_url": "https://linkedin.com/jobs/1",
                "posted_relative": "2 days ago",
                "hiring_contact_name": None,
                "hiring_contact_email": None,
            }
        ]

        reply = await copilot.chat(message="What skills are trending?", target_job_id="all")
        assert "Market trend summary" in reply
        
        system_instr = mock_generate.call_args.kwargs["system_instruction"]
        assert "Total Active Stored Jobs: 42" in system_instr
        assert "PySpark" in system_instr


# --- 5. UI Server Endpoint Edge Cases ---
@pytest.mark.asyncio
async def test_ui_job_details_not_found_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/jobs/definitely_does_not_exist_404")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_ui_sync_prevent_duplicate_concurrent_runs():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            # Simulate a sync running
            sync_state["status"] = "running"
            resp = await client.post("/api/sync/run")
            assert resp.status_code == 200
            assert resp.json()["status"] == "already_running"
        finally:
            sync_state["status"] = "idle"
