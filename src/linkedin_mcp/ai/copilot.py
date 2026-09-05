"""
Career Copilot engine integrating LinkedIn database context with LLM inference.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from linkedin_mcp.ai.client import LLMClient
from linkedin_mcp.ai.settings import load_settings
from linkedin_mcp.db.repository import get_job_by_id, get_jobs_for_context, get_storage_stats

logger = logging.getLogger("linkedin-mcp.ai.copilot")


class CareerCopilot:
    """Intelligent Career Assistant operating on local LinkedIn SQLite data."""

    def __init__(self):
        self.client = LLMClient()

    async def chat(
        self,
        message: str,
        target_job_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Execute a conversational turn with grounded context.
        """
        settings = load_settings()
        user_profile = settings.get("user_profile", "")

        # Build grounded context
        job_context = ""
        target_job = None
        if target_job_id and target_job_id != "all":
            target_job = get_job_by_id(target_job_id)

        if target_job:
            job_context = (
                "### TARGET JOB DETAILS (GROUND TRUTH FROM LOCAL DATABASE):\n"
                f"- Job ID: {target_job.get('job_id')}\n"
                f"- Title: {target_job.get('title')}\n"
                f"- Company: {target_job.get('company')}\n"
                f"- Location: {target_job.get('location')} ({target_job.get('workplace_type')})\n"
                f"- Experience Level: {target_job.get('experience_level')} (Min years: {target_job.get('experience_min_years') or 'Not specified'})\n"
                f"- Tech Stack: {', '.join(target_job.get('tech_stack', [])) or 'Not explicitly tagged'}\n"
                f"- Salary / Compensation: {target_job.get('salary_raw') or 'Not disclosed'}\n"
                f"- Posted Time: {target_job.get('posted_relative')}\n"
                f"- Hiring Contact Name: {target_job.get('hiring_contact_name') or 'None listed'}\n"
                f"- Hiring Contact Profile: {target_job.get('hiring_contact_profile') or 'None listed'}\n"
                f"- Hiring Contact Email: {target_job.get('hiring_contact_email') or 'None listed'}\n"
                f"- Canonical Source URL: {target_job.get('source_url')}\n"
                f"- Summary: {target_job.get('description_summary')}\n"
                f"- Full Description / Post Content:\n```text\n{target_job.get('raw_text', '')[:3000]}\n```\n"
            )
        else:
            # Entire database overview
            stats = get_storage_stats()
            recent_jobs = get_jobs_for_context(limit=35)
            
            jobs_brief = []
            for j in recent_jobs:
                recruiter = j.get('hiring_contact_name') or 'N/A'
                email = j.get('hiring_contact_email') or ''
                contact_str = f"{recruiter} ({email})" if email else recruiter
                jobs_brief.append(
                    f"• [{j.get('job_id')}] **{j.get('title')}** at **{j.get('company')}** | {j.get('location')} ({j.get('workplace_type')}) | "
                    f"Posted: {j.get('posted_relative')} | Skills: {', '.join(j.get('tech_stack', []))} | Recruiter: {contact_str} | URL: {j.get('source_url')}"
                )

            top_skills_str = ", ".join([f"{s['skill']} ({s['count']})" for s in stats.get("top_skills", [])[:10]])
            top_companies_str = ", ".join([f"{c['company']} ({c['count']})" for c in stats.get("top_companies", [])[:8]])

            job_context = (
                "### CURRENT DATABASE SUMMARY (LOCAL LINKEDIN JOBS):\n"
                f"- Total Active Stored Jobs: {stats.get('total_jobs')}\n"
                f"- Job Board Openings: {stats.get('job_board_jobs')}\n"
                f"- Recruiter Feed Posts: {stats.get('feed_post_jobs')}\n"
                f"- Top In-Demand Tech Skills: {top_skills_str}\n"
                f"- Top Actively Hiring Companies: {top_companies_str}\n\n"
                "### RECENT SCRAPED JOBS CATALOG:\n"
                + "\n".join(jobs_brief)
                + "\n"
            )

        system_instruction = (
            "You are the **LinkedIn Career Copilot**, an expert career strategist, technical coach, "
            "and hiring expert for senior and lead tech professionals (specifically Data Engineering, "
            "Data Platforms, Cloud Architecture, and Software Engineering).\n\n"
            "YOUR OBJECTIVES:\n"
            "1. Give sharp, actionable, and zero-fluff advice grounded in the provided LinkedIn database context.\n"
            "2. When answering queries about available jobs or market trends, ALWAYS cite the actual company names, "
            "titles, tech stacks, and source URLs from the database context.\n"
            "3. When drafting recruiter outreach:\n"
            "   - Provide a **LinkedIn Connection Request Note** strictly under 300 characters.\n"
            "   - Provide an optional **Direct Email / InMail message** (crisp, 100-150 words) referencing the specific post, recruiter name, and relevant technical stack alignment.\n"
            "4. When analyzing resume fit, provide an objective Match Score (0-100%), highlighted overlaps, "
            "missing/bonus skills, and 2-3 specific bullet-point suggestions to tailor for the role.\n"
            "5. When generating interview prep, give realistic, deep technical architecture and scenario-based questions "
            "tailored to the company's stated stack and engineering challenges.\n\n"
            f"### USER'S PROFESSIONAL PROFILE & RESUME CONTEXT:\n{user_profile}\n\n"
            f"{job_context}"
        )

        # Build prompt with optional recent history
        prompt_parts = []
        if conversation_history:
            recent = conversation_history[-6:]  # keep last few turns
            prompt_parts.append("### PREVIOUS CONVERSATION:")
            for turn in recent:
                role = "User" if turn.get("role") == "user" else "Copilot"
                prompt_parts.append(f"{role}: {turn.get('content')}")
            prompt_parts.append("### CURRENT USER QUERY:")

        prompt_parts.append(message)
        final_prompt = "\n\n".join(prompt_parts)

        return await self.client.generate(
            prompt=final_prompt,
            system_instruction=system_instruction,
            temperature=0.7,
        )
