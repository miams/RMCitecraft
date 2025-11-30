"""
Debug script to inspect FamilySearch page and find download button.
"""
import asyncio
from playwright.async_api import async_playwright

async def inspect_page():
    """Inspect the FamilySearch image viewer page."""
    async with async_playwright() as p:
        # Connect to existing Chrome instance
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # Get the page
        pages = context.pages
        page = None
        for p in pages:
            if "familysearch.org/ark:/61903/3:1:S3HT-DC17-RCM" in p.url:
                page = p
                break

        if not page:
            print("FamilySearch page not found!")
            return

        print(f"Found page: {page.url}")
        print(f"Title: {await page.title()}")

        # Get all buttons
        print("\n=== ALL BUTTONS ON PAGE ===")
        buttons = await page.query_selector_all("button")
        print(f"Total buttons found: {len(buttons)}")

        for i, btn in enumerate(buttons):
            try:
                text = await btn.inner_text()
                aria_label = await btn.get_attribute("aria-label")
                data_testid = await btn.get_attribute("data-testid")
                class_name = await btn.get_attribute("class")

                print(f"\nButton {i+1}:")
                print(f"  Text: {text[:50] if text else 'None'}")
                print(f"  aria-label: {aria_label}")
                print(f"  data-testid: {data_testid}")
                print(f"  class: {class_name[:50] if class_name else 'None'}")
            except Exception as e:
                print(f"  Error inspecting button {i+1}: {e}")

        # Look for elements with role="button"
        print("\n=== ELEMENTS WITH role='button' ===")
        role_buttons = await page.query_selector_all('[role="button"]')
        print(f"Total found: {len(role_buttons)}")

        for i, btn in enumerate(role_buttons):
            try:
                text = await btn.inner_text()
                print(f"Role button {i+1}: {text[:50] if text else 'None'}")
            except Exception as e:
                print(f"  Error: {e}")

        # Look for download-related elements
        print("\n=== DOWNLOAD-RELATED ELEMENTS ===")
        download_elements = await page.query_selector_all('[aria-label*="Download" i], [title*="Download" i]')
        print(f"Total found: {len(download_elements)}")

        for i, elem in enumerate(download_elements):
            try:
                tag = await elem.evaluate("el => el.tagName")
                text = await elem.inner_text()
                aria_label = await elem.get_attribute("aria-label")
                title = await elem.get_attribute("title")

                print(f"\nDownload element {i+1}:")
                print(f"  Tag: {tag}")
                print(f"  Text: {text[:50] if text else 'None'}")
                print(f"  aria-label: {aria_label}")
                print(f"  title: {title}")
            except Exception as e:
                print(f"  Error: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_page())
