#!/usr/bin/env python3
"""
Analyze Ancestry collection 1002 (WW2 Draft Registration Cards, 1942) record
to understand citation requirements and build NAID lookup table.
"""

import asyncio
from playwright.async_api import async_playwright


async def analyze_record():
    """Analyze a collection 1002 record and extract citation elements."""

    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else await context.new_page()

    print("=" * 80)
    print("ANALYZING COLLECTION 1002 RECORD")
    print("=" * 80)

    # Navigate to record page
    record_url = "https://www.ancestrylibrary.com/search/collections/1002/records/2351336"
    print(f"\n📄 Navigating to: {record_url}")
    await page.goto(record_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)

    # Extract all visible text for analysis
    print("\n" + "=" * 80)
    print("DETAIL TAB - Person Information")
    print("=" * 80)

    detail_data = await page.evaluate("""
        () => {
            const data = {};
            const allText = document.body.innerText;

            // Collection title
            const titleEl = document.querySelector('h1, [class*="title"]');
            if (titleEl) {
                data.collection_title = titleEl.innerText.trim();
            }

            // Extract person details
            const patterns = {
                name: /Name[:\\s]+([A-Z][a-z]+(?: [A-Z][a-z]+)+)/i,
                registration_date: /Registration Date[:\\s]+([^\\n]+)/i,
                registration_place: /Registration Place[:\\s]+([^\\n]+)/i,
                birth_date: /Birth Date[:\\s]+([^\\n]+)/i,
                birth_place: /Birth Place[:\\s]+([^\\n]+)/i,
                residence: /Residence[:\\s]+([^\\n]+)/i,
            };

            for (const [key, pattern] of Object.entries(patterns)) {
                const match = allText.match(pattern);
                if (match) {
                    data[key] = match[1].trim();
                }
            }

            return data;
        }
    """)

    print("\n📋 Extracted Details:")
    for key, value in detail_data.items():
        print(f"  {key}: {value}")

    # Click Source tab to get citation info
    print("\n" + "=" * 80)
    print("SOURCE TAB - Citation Information")
    print("=" * 80)

    try:
        print("\n🔍 Clicking Source tab...")
        source_tab = page.locator('button:has-text("Source"), a:has-text("Source")').first
        await source_tab.click()
        await page.wait_for_timeout(1000)

        source_info = await page.evaluate("""
            () => {
                const data = {};
                const sourceText = document.body.innerText;

                // Extract Source Citation section
                const citationMatch = sourceText.match(/Source Citation[:\\s]+([^]+?)(?=\\n\\n|About|$)/i);
                if (citationMatch) {
                    data.source_citation = citationMatch[1].trim();
                }

                // Extract microfilm title
                const microfilmMatch = sourceText.match(/([^;]+?Draft Registration Cards[^;,]*)/i);
                if (microfilmMatch) {
                    data.microfilm_title = microfilmMatch[1].trim();
                }

                // Extract NARA location
                const naraMatch = sourceText.match(/National Archives at ([^;\\n]+)/i);
                if (naraMatch) {
                    data.nara_location = 'National Archives at ' + naraMatch[1].trim();
                }

                // Extract Record Group
                const rgMatch = sourceText.match(/Record Group[:\\s]+([^\\n]+)/i);
                if (rgMatch) {
                    data.record_group = rgMatch[1].trim();
                }

                // Extract Box
                const boxMatch = sourceText.match(/Box[:\\s]+(\\d+)/i);
                if (boxMatch) {
                    data.box = boxMatch[1].trim();
                }

                return data;
            }
        """)

        print("\n📜 Source Citation Information:")
        for key, value in source_info.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"⚠️  Error extracting Source tab: {e}")

    # Navigate to moreinfo page to get NAID mappings
    print("\n" + "=" * 80)
    print("MOREINFO PAGE - NAID Lookup Table")
    print("=" * 80)

    moreinfo_url = "https://www.ancestrylibrary.com/search/collections/1002/moreinfo"
    print(f"\n📄 Navigating to: {moreinfo_url}")
    await page.goto(moreinfo_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)

    # Extract NAID information by state
    naid_data = await page.evaluate("""
        () => {
            const data = {};
            const pageText = document.body.innerText;

            // Look for NAID patterns in the text
            // Example: "Alabama: Series M1936; Roll: 1; NAID: 5678901"
            const naids = {};

            // Try to find state-specific NAID information
            const statePattern = /([A-Z][a-z]+(?: [A-Z][a-z]+)?)[:\\s,]+.*?NAID[:\\s]+(\\d+)/gi;
            let match;
            while ((match = statePattern.exec(pageText)) !== null) {
                const state = match[1].trim();
                const naid = match[2].trim();
                naids[state] = naid;
            }

            data.state_naids = naids;
            data.page_text = pageText.substring(0, 2000); // First 2000 chars for analysis

            return data;
        }
    """)

    print("\n🗺️  State NAID Mappings Found:")
    if naid_data.get('state_naids'):
        for state, naid in naid_data['state_naids'].items():
            print(f"  {state}: {naid}")
    else:
        print("  (No state-specific NAIDs found in standard pattern)")
        print("\n📝 Page text sample (first 500 chars):")
        print(naid_data.get('page_text', '')[:500])

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    await playwright.stop()


async def main():
    """Main entry point."""
    try:
        await analyze_record()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
