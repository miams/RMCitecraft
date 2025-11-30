#!/usr/bin/env python3
"""
Keep Chrome running with FamilySearch image viewer open for E2E tests.

This script launches Chrome once and keeps it running indefinitely with the
image viewer page open. E2E tests can then connect to this existing Chrome
instance and navigate without issues.

Usage:
    uv run python tests/e2e/keep_chrome_running.py

Press Ctrl+C to stop.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def keep_chrome_running():
    """Keep Chrome running with image viewer page open."""
    print("=" * 80)
    print("Keep Chrome Running for E2E Tests")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Launch Chrome with persistent profile")
    print("2. Navigate to a FamilySearch census image viewer")
    print("3. Keep Chrome running for E2E tests to connect to")
    print()
    print("Press Ctrl+C to stop Chrome and exit.")
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

        # Navigate to FamilySearch image viewer
        image_url = "https://www.familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM"
        print(f"\nNavigating to FamilySearch image viewer: {image_url}")
        await page.goto(image_url)

        print()
        print("=" * 80)
        print("✓ Chrome is running and ready for E2E tests!")
        print("=" * 80)
        print()
        print("FamilySearch image viewer is loaded in Chrome.")
        print("E2E tests can now connect to this Chrome instance.")
        print()
        print("To run E2E tests:")
        print("   uv run pytest tests/e2e/test_census_batch_with_downloads.py -v -s")
        print()
        print("Press Ctrl+C to stop Chrome.")
        print()

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(60)
                print(".", end="", flush=True)
        except KeyboardInterrupt:
            print("\n\nStopping Chrome...")

        # Close browser
        await context.close()

    finally:
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(keep_chrome_running())
