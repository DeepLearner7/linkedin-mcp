#!/usr/bin/env python3
"""
Live MCP Validation & Smoke Test Runner for LinkedIn MCP.
Tests all MCP tools against live LinkedIn endpoints safely.
"""

import asyncio
import sys
from linkedin_mcp.server import (
    linkedin_status,
    linkedin_get_safety_stats,
    linkedin_get_profile,
    linkedin_search_people,
    linkedin_search_feed_posts,
)
from linkedin_mcp.safety import check_action_allowed, get_safety_summary


async def run_live_validation():
    print("==================================================")
    print("   LinkedIn MCP Live Health & Validation Suite   ")
    print("==================================================")
    results = {}

    # Test 1: linkedin_status
    print("\n[1/5] Testing `linkedin_status`...")
    try:
        status_out = linkedin_status()
        assert "=== LinkedIn MCP Status ===" in status_out
        assert "Status: ACTIVE" in status_out
        print("   ✅ PASSED: Status check returned active status and safety stats.")
        results["status"] = True
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        results["status"] = False

    # Test 2: linkedin_get_safety_stats
    print("\n[2/5] Testing `linkedin_get_safety_stats`...")
    try:
        safety_stats = linkedin_get_safety_stats()
        assert "Daily LinkedIn Safety Stats" in safety_stats
        print("   ✅ PASSED: Safety stats formatted cleanly.")
        results["safety_stats"] = True
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        results["safety_stats"] = False

    # Test 3: linkedin_get_profile('me') via REST API
    print("\n[3/5] Testing `linkedin_get_profile('me')` via REST API...")
    try:
        self_profile = await linkedin_get_profile("me")
        assert "Authenticated LinkedIn Profile (Self)" in self_profile
        assert "Member ID (sub)" in self_profile
        print(f"   ✅ PASSED: Live profile retrieved via REST API.")
        results["profile_self"] = True
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        results["profile_self"] = False

    # Test 4: linkedin_search_people
    print("\n[4/5] Testing `linkedin_search_people` (live browser)...")
    try:
        people_out = await linkedin_search_people(keywords="Senior Data Engineer Pune", limit=2)
        assert "Found" in people_out or "profile" in people_out.lower()
        print("   ✅ PASSED: Live people search executed successfully.")
        results["search_people"] = True
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        results["search_people"] = False

    # Test 5: linkedin_search_feed_posts
    print("\n[5/5] Testing `linkedin_search_feed_posts` (live browser)...")
    try:
        posts_out = await linkedin_search_feed_posts(
            keywords="Senior Data Engineer Pune hiring",
            limit=2,
            sort_by="date_posted",
            date_posted="past-month"
        )
        assert "Found" in posts_out or "post" in posts_out.lower()
        print("   ✅ PASSED: Live content feed search executed successfully.")
        results["search_posts"] = True
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        results["search_posts"] = False

    print("\n==================================================")
    print("               Validation Summary                 ")
    print("==================================================")
    all_passed = True
    for test_name, passed in results.items():
        icon = "✅ PASS" if passed else "❌ FAIL"
        print(f"  • {test_name.ljust(20)}: {icon}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll live LinkedIn MCP tools verified successfully! 🎉\n")
        sys.exit(0)
    else:
        print("\nSome tests failed. Please review errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_live_validation())
