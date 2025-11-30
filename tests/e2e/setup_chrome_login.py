#!/usr/bin/env python3
"""
One-time setup script to launch Chrome and log into FamilySearch.

Run this once to set up your FamilySearch login in the persistent Chrome profile.
After logging in, you can close Chrome and the login will persist for all future tests.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def setup_familysearch_login():
    """Launch Chrome with persistent context and wait for user to log in."""
    print("=" * 80)
    print("FamilySearch Login Setup")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Launch Chrome with persistent profile")
    print("2. Open FamilySearch.org")
    print("3. Wait for you to log in")
    print("4. Save your login for future test runs")
    print()
    print("-" * 80)

    chrome_profile = Path.home() / "chrome-debug-profile"
    print(f"Using profile directory: {chrome_profile}")

    playwright = await async_playwright().start()

    try:
        # Launch Chrome with persistent context
        print("\nLaunching Chrome...")
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(chrome_profile),
            headless=False,
            channel="chrome",
            args=[
                "--remote-debugging-port=9222",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Get the first page or create new one
        page = context.pages[0] if context.pages else await context.new_page()

        # Navigate to FamilySearch
        print("Opening FamilySearch.org...")
        await page.goto("https://www.familysearch.org")

        print()
        print("=" * 80)
        print("PLEASE LOG IN TO FAMILYSEARCH NOW")
        print("=" * 80)
        print()
        print("Instructions:")
        print("1. Use the Chrome window that just opened")
        print("2. Click 'Sign In' and log in with your FamilySearch account")
        print("3. Once logged in, come back here and press Enter")
        print()
        print("Your login will be saved in the persistent profile.")
        print("You won't need to log in again for future test runs.")
        print()

        # Keep Chrome open for 5 minutes to allow login
        print("\nChrome will stay open for 5 minutes.")
        print("Log in now, then you can close this terminal or press Ctrl+C.")
        print()

        try:
            for remaining in range(300, 0, -10):
                print(f"Time remaining: {remaining} seconds...", end="\r", flush=True)
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")

        print("\n\nChecking login status...")
        await page.goto("https://www.familysearch.org")
        await asyncio.sleep(2)

        # Simple check: look for sign-in button
        sign_in_button = await page.query_selector('a[href*="signin"]')

        print()
        print("=" * 80)
        if sign_in_button:
            print("⚠️  Sign-in button still visible - you may not be logged in")
            print("You can run this script again if needed.")
        else:
            print("✓ Login appears successful!")
            print("Your FamilySearch session is saved in ~/chrome-debug-profile")
        print("=" * 80)
        print()
        print("You can now run E2E tests:")
        print("   uv run pytest tests/e2e/test_census_batch_with_downloads.py -v -s")
        print()
        print("Closing Chrome...")

        # Close browser
        await context.close()

    finally:
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(setup_familysearch_login())
