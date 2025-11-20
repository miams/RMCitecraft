#!/usr/bin/env python3
"""Debug script to test dashboard rendering with Playwright."""

import asyncio
from playwright.async_api import async_playwright


async def debug_dashboard():
    """Test dashboard navigation and capture console errors."""
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Capture console messages
        console_messages = []
        errors = []

        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: errors.append(str(err)))

        try:
            # Navigate to app
            print("Navigating to http://localhost:8080...")
            await page.goto("http://localhost:8080", wait_until="networkidle")
            print("✓ Page loaded")

            # Wait a moment for initial render
            await page.wait_for_timeout(2000)

            # Take screenshot of home page
            await page.screenshot(path="debug_home.png")
            print("✓ Screenshot saved: debug_home.png")

            # Find and click Dashboard button in header
            print("\nLooking for Dashboard button in header...")
            dashboard_button = page.locator('button:has-text("Dashboard")').first

            if await dashboard_button.count() > 0:
                print("✓ Found Dashboard button")

                # Click it
                print("Clicking Dashboard button...")
                await dashboard_button.click()

                # Wait for navigation/render
                await page.wait_for_timeout(3000)

                # Take screenshot after click
                await page.screenshot(path="debug_dashboard.png")
                print("✓ Screenshot saved: debug_dashboard.png")

                # Check page content
                body_text = await page.inner_text("body")

                if "Master Progress" in body_text or "Find a Grave Batch Operations Dashboard" in body_text:
                    print("\n✓✓✓ Dashboard rendered successfully!")
                    print(f"Page contains {len(body_text)} characters")
                else:
                    print("\n✗ Dashboard did NOT render (no expected text found)")
                    print(f"First 500 chars of body: {body_text[:500]}")
            else:
                print("✗ Dashboard button not found")

            # Print console messages
            if console_messages:
                print("\n=== Console Messages ===")
                for msg in console_messages:
                    print(msg)

            # Print errors
            if errors:
                print("\n=== JavaScript Errors ===")
                for err in errors:
                    print(err)
            else:
                print("\n✓ No JavaScript errors detected")

            # Keep browser open for inspection
            print("\nBrowser will stay open for 10 seconds for manual inspection...")
            await page.wait_for_timeout(10000)

        except Exception as e:
            print(f"\n✗ Error during test: {e}")
            import traceback
            traceback.print_exc()

            # Save error screenshot
            try:
                await page.screenshot(path="debug_error.png")
                print("Error screenshot saved: debug_error.png")
            except:
                pass

        finally:
            await browser.close()


if __name__ == "__main__":
    print("Dashboard Debug Script")
    print("=" * 50)
    print("\nMake sure RMCitecraft is running on http://localhost:8080")
    print("Starting browser automation test...\n")

    asyncio.run(debug_dashboard())
