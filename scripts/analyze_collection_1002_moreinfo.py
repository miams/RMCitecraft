#!/usr/bin/env python3
"""
Extract detailed moreinfo page content for collection 1002 to build NAID lookup table.
"""

import asyncio
from playwright.async_api import async_playwright


async def analyze_moreinfo():
    """Get full moreinfo page content."""

    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else await context.new_page()

    # Navigate to moreinfo page
    moreinfo_url = "https://www.ancestrylibrary.com/search/collections/1002/moreinfo"
    print(f"Navigating to: {moreinfo_url}\n")
    await page.goto(moreinfo_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)

    # Get full page text
    page_html = await page.content()

    # Also get formatted text
    page_text = await page.evaluate("() => document.body.innerText")

    print("=" * 80)
    print("FULL PAGE TEXT")
    print("=" * 80)
    print(page_text)
    print("\n" + "=" * 80)

    # Look for any tables or structured content
    tables_info = await page.evaluate("""
        () => {
            const tables = document.querySelectorAll('table');
            const result = [];

            tables.forEach((table, idx) => {
                const rows = [];
                const tableRows = table.querySelectorAll('tr');

                tableRows.forEach(tr => {
                    const cells = [];
                    tr.querySelectorAll('td, th').forEach(cell => {
                        cells.push(cell.innerText.trim());
                    });
                    if (cells.length > 0) {
                        rows.push(cells);
                    }
                });

                if (rows.length > 0) {
                    result.push({
                        index: idx,
                        rows: rows
                    });
                }
            });

            return result;
        }
    """)

    if tables_info:
        print("\nTABLES FOUND:")
        print("=" * 80)
        for table in tables_info:
            print(f"\nTable {table['index']}:")
            for row in table['rows']:
                print(f"  {' | '.join(row)}")

    await playwright.stop()


async def main():
    """Main entry point."""
    try:
        await analyze_moreinfo()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
