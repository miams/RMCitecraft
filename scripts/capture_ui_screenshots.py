"""Capture UI screenshots for User Journey Map documentation.

This script launches the RMCitecraft application and captures screenshots
of all major UI interfaces for documentation purposes.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def capture_screenshots():
    """Capture screenshots of RMCitecraft UI."""
    output_dir = Path("docs/screenshots/user_journey")
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})

        # Navigate to RMCitecraft (assuming it's running on localhost:8080)
        await page.goto('http://localhost:8080')
        await page.wait_for_load_state('networkidle')

        # 1. Home Page
        print("Capturing: Home Page...")
        await page.screenshot(path=output_dir / "01_home_page.png")

        # 2. Census Batch Processing Tab
        print("Capturing: Census Batch Processing...")
        await page.click('text=Census Batch')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=output_dir / "02_census_batch_empty.png")

        # Try to load a small batch if possible (optional)
        try:
            await page.click('button:has-text("Load")')
            await page.wait_for_selector('input[label="Number of citations to load"]', timeout=2000)
            await page.fill('input[label="Number of citations to load"]', '5')
            await page.click('button:has-text("Load"):visible')
            await page.wait_for_timeout(2000)
            await page.screenshot(path=output_dir / "03_census_batch_loaded.png")
        except Exception as e:
            print(f"Skipped census batch loaded view: {e}")

        # 3. Find a Grave Tab
        print("Capturing: Find a Grave Batch Processing...")
        await page.click('text=Find a Grave')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=output_dir / "04_findagrave_empty.png")

        # 4. Citation Manager Tab
        print("Capturing: Citation Manager...")
        await page.click('text=Citation Manager')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=output_dir / "05_citation_manager.png")

        # 5. Dashboard Tab
        print("Capturing: Dashboard...")
        await page.click('text=Dashboard')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=output_dir / "06_dashboard.png")

        print(f"\nScreenshots saved to: {output_dir}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
