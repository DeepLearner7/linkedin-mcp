"""
Interactive login helper for LinkedIn MCP.
Launches a visible browser window where the user can log into their LinkedIn account.
Once logged in, saves the session state (cookies) to ~/.config/linkedin-mcp/session.json.
"""

import asyncio
import sys
import logging
from pathlib import Path
from playwright.async_api import async_playwright
from linkedin_mcp.browser import launch_stealth_context, get_session_file, is_authenticated

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("linkedin-mcp.auth")


async def run_interactive_login(timeout_seconds: int = 300) -> bool:
    session_file = get_session_file()
    print("==================================================", file=sys.stderr)
    print("  LinkedIn MCP Interactive Session Login          ", file=sys.stderr)
    print("==================================================", file=sys.stderr)
    print("1. A Chromium browser window will open shortly.", file=sys.stderr)
    print("2. Enter your LinkedIn email & password in the browser.", file=sys.stderr)
    print("3. Complete any 2FA or CAPTCHA verification if required.", file=sys.stderr)
    print("4. Once you reach the LinkedIn feed, your session will be saved automatically.", file=sys.stderr)
    print(f"Waiting up to {timeout_seconds} seconds...\n", file=sys.stderr)

    async with async_playwright() as p:
        browser, context = await launch_stealth_context(p, headless=False)
        page = await context.new_page()

        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

            # Polling loop to check when user has logged in
            start_time = asyncio.get_event_loop().time()
            logged_in = False

            while asyncio.get_event_loop().time() - start_time < timeout_seconds:
                # Check cookies for li_at
                cookies = await context.cookies()
                has_li_at = any(c.get("name") == "li_at" and len(c.get("value", "")) > 10 for c in cookies)

                current_url = page.url
                if has_li_at and ("/feed" in current_url or "/in/" in current_url or "/search" in current_url or await is_authenticated(page)):
                    logged_in = True
                    break

                await asyncio.sleep(2.0)

            if logged_in:
                # Give a couple of seconds for all auth tokens/cookies to settle
                await asyncio.sleep(2.0)
                await context.storage_state(path=str(session_file))
                print("\n==================================================", file=sys.stderr)
                print(" SUCCESS: LinkedIn session captured and saved! ", file=sys.stderr)
                print(f" Saved to: {session_file}", file=sys.stderr)
                print("==================================================", file=sys.stderr)
                return True
            else:
                print("\nLogin timed out or was not completed.", file=sys.stderr)
                return False

        except Exception as e:
            logger.error("Error during interactive login: %s", e)
            return False
        finally:
            await browser.close()


def main():
    try:
        success = asyncio.run(run_interactive_login())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nLogin canceled by user.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
