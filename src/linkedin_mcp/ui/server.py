"""
FastAPI Server for LinkedIn MCP Discovery Dashboard & Career Copilot.
"""

import asyncio
import logging
import os
import sys
import threading
import webbrowser

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from linkedin_mcp.ai.copilot import CareerCopilot
from linkedin_mcp.ai.settings import load_settings, save_settings
from linkedin_mcp.db.repository import (
    get_storage_stats,
    query_stored_jobs,
    get_job_by_id,
    get_jobs_for_context,
)
from linkedin_mcp.db.schema import JobQueryParams

logger = logging.getLogger("linkedin-mcp.ui")

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"
REPO_DIR = Path(__file__).resolve().parent.parent.parent.parent
DAILY_SYNC_SCRIPT = REPO_DIR / "scripts" / "daily_sync.sh"

app = FastAPI(
    title="LinkedIn Career Intelligence",
    description="Jobs Discovery Dashboard & AI Career Copilot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state for background sync execution
sync_state: Dict[str, Any] = {
    "status": "idle",  # idle | running | completed | error
    "started_at": None,
    "completed_at": None,
    "exit_code": None,
    "logs": [],
}

copilot_instance = CareerCopilot()


# --- Models ---
class ChatRequest(BaseModel):
    message: str
    target_job_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    user_profile: Optional[str] = None


# --- Static Frontend Serving ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return HTMLResponse("<h1>LinkedIn UI frontend under construction</h1>")


# --- API Routes ---
@app.get("/api/stats")
async def api_get_stats():
    """Return analytical stats and counts from SQLite."""
    try:
        return get_storage_stats()
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
async def api_get_jobs(
    keywords: Optional[str] = None,
    location: Optional[str] = None,
    workplace_type: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Query jobs with full filters."""
    params = JobQueryParams(
        keywords=keywords if keywords else None,
        location=location if location else None,
        workplace_type=workplace_type if workplace_type and workplace_type != "all" else None,
        source_type=source_type if source_type and source_type != "all" else None,
        limit=limit,
        offset=offset,
    )
    jobs = query_stored_jobs(params)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/api/jobs/brief")
async def api_get_brief_jobs(limit: int = Query(default=60, ge=1, le=150)):
    """Return brief job list for AI target dropdown."""
    return get_jobs_for_context(limit=limit)


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    """Retrieve full single job information."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/settings")
async def api_get_settings():
    """Retrieve current settings, masking secret API keys."""
    cfg = load_settings()
    raw_key = cfg.get("gemini_api_key", "").strip()
    masked_key = ""
    if raw_key:
        if len(raw_key) > 8:
            masked_key = raw_key[:4] + "..." + raw_key[-4:]
        else:
            masked_key = "********"

    return {
        "llm_provider": cfg.get("llm_provider", "gemini"),
        "gemini_model": cfg.get("gemini_model", "gemini-1.5-flash"),
        "has_gemini_key": bool(raw_key),
        "masked_gemini_key": masked_key,
        "ollama_url": cfg.get("ollama_url", "http://localhost:11434"),
        "ollama_model": cfg.get("ollama_model", "llama3.1"),
        "user_profile": cfg.get("user_profile", ""),
    }


@app.post("/api/settings")
async def api_save_settings(data: SettingsUpdate):
    """Update settings and persist to ~/.config/linkedin-mcp/settings.json."""
    updates: Dict[str, Any] = {}
    if data.llm_provider is not None:
        updates["llm_provider"] = data.llm_provider
    if data.gemini_api_key is not None and data.gemini_api_key.strip():
        updates["gemini_api_key"] = data.gemini_api_key.strip()
    if data.gemini_model is not None:
        updates["gemini_model"] = data.gemini_model
    if data.ollama_url is not None:
        updates["ollama_url"] = data.ollama_url
    if data.ollama_model is not None:
        updates["ollama_model"] = data.ollama_model
    if data.user_profile is not None:
        updates["user_profile"] = data.user_profile

    saved = save_settings(updates)
    return {"status": "success", "saved": bool(saved)}


@app.post("/api/ai/chat")
async def api_chat(req: ChatRequest):
    """Execute conversational turn with Career Copilot."""
    try:
        reply = await copilot_instance.chat(
            message=req.message,
            target_job_id=req.target_job_id,
            conversation_history=req.history,
        )
        return {"reply": reply, "target_job_id": req.target_job_id}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return {"reply": f"❌ An error occurred during chat generation: {str(e)}"}


# --- Daily Sync Background Runner ---
async def _execute_sync_process():
    global sync_state
    sync_state["status"] = "running"
    sync_state["started_at"] = datetime.now(timezone.utc).isoformat()
    sync_state["completed_at"] = None
    sync_state["logs"] = [f"[{datetime.now().strftime('%H:%M:%S')}] Starting background sync pipeline..."]

    try:
        cmd = [str(DAILY_SYNC_SCRIPT)] if DAILY_SYNC_SCRIPT.exists() else [sys.executable, "-m", "linkedin_mcp.pipeline.cli"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(REPO_DIR),
        )

        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if decoded:
                sync_state["logs"].append(decoded)
                if len(sync_state["logs"]) > 500:
                    sync_state["logs"].pop(0)

        await proc.wait()
        sync_state["exit_code"] = proc.returncode
        sync_state["status"] = "completed" if proc.returncode == 0 else "error"
        sync_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Sync finished with exit code {proc.returncode}.")
    except Exception as e:
        sync_state["status"] = "error"
        sync_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
    finally:
        sync_state["completed_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/api/sync/run")
async def api_trigger_sync(background_tasks: BackgroundTasks):
    """Trigger the daily sync process asynchronously."""
    global sync_state
    if sync_state["status"] == "running":
        return {"status": "already_running", "message": "A sync run is already in progress."}

    background_tasks.add_task(_execute_sync_process)
    return {"status": "started", "message": "Daily sync initiated in background."}


@app.get("/api/sync/status")
async def api_get_sync_status():
    """Check sync progress and retrieve logs."""
    return sync_state


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LinkedIn Career Intelligence Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("\n" + "=" * 60)
    print("🚀 LinkedIn Career Intelligence Hub & Copilot")
    print(f"👉 Running at: {url}")
    print("=" * 60 + "\n")

    if not args.no_browser:
        timer = threading.Timer(1.0, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    uvicorn.run("linkedin_mcp.ui.server:app", host=args.host, port=args.port, reload=False)



if __name__ == "__main__":
    main()
