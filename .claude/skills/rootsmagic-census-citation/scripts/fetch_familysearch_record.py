#!/usr/bin/env python3
"""Fetch the indexed fields and image ARK from a FamilySearch record URL.

Connects to the user's existing Chrome CDP instance on localhost:9222 (never
launches a new browser — relies on the user's authenticated FamilySearch
session). Prints the record's structured fields to stdout, and the image ARK
(`3:1:...`) plus the image TH-ID needed for download_fs_image.py.

Usage:
    uv run python3 fetch_familysearch_record.py <ark-url>

Example:
    uv run python3 fetch_familysearch_record.py \\
        https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3

Output sections:
    HEADER         - URL, title, ARK ID
    FIELDS         - definition-list (DT/DD) pairs from the indexed record
    HOUSEHOLD      - other persons listed on the same record
    IMAGE          - image viewer URL, image ARK (3:1:...), image TH-ID

Notes:
    - If Chrome CDP isn't running on localhost:9222, this fails with a clear
      message. Start it (see project CLAUDE.md "Playwright Browser Automation"
      section) and re-run.
    - The 1950 experimental sample format leaves "Supervisor District Field"
      EMPTY in the indexed text; ED must be read off the image or supplied
      by the user.
"""
import asyncio
import re
import sys
from urllib.parse import urlparse


CDP_URL = "http://localhost:9222"


async def fetch(ark_url: str) -> dict:
    from playwright.async_api import async_playwright

    result = {
        'url': ark_url,
        'final_url': None,
        'title': None,
        'fields': [],
        'household': [],
        'image_viewer_url': None,
        'image_ark': None,
        'image_th_id': None,
    }

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            raise SystemExit(
                f"Could not connect to Chrome CDP at {CDP_URL}: {e}\n"
                "Start Chrome with --remote-debugging-port=9222 first."
            )

        ctx = browser.contexts[0]
        page = None
        for p in ctx.pages:
            if "familysearch.org" in p.url:
                page = p
                break
        if page is None:
            page = await ctx.new_page()

        try:
            await page.goto(ark_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"goto warning: {e}", file=sys.stderr)
        await page.wait_for_timeout(5000)

        result['final_url'] = page.url
        result['title'] = await page.title()

        # Extract DT/DD pairs (record fields)
        dts = await page.evaluate("""() => {
            const pairs = [];
            document.querySelectorAll('dt').forEach(dt => {
                const dd = dt.nextElementSibling;
                if (dd && dd.tagName === 'DD') {
                    pairs.push([dt.innerText.trim(), dd.innerText.trim()]);
                }
            });
            return pairs;
        }""")
        result['fields'] = dts

        # Heuristically extract "household" (other persons on the same record).
        # The "Spouses and Children" / "Other People" sections render as plain text rows
        # — use the body text as fallback.
        body = await page.evaluate("() => document.body.innerText")
        # Pull anything that looks like a household row (Name <tab> Relation <tab> Sex <tab> Age...)
        for line in body.split('\n'):
            line = line.strip()
            if re.match(r'^[A-Z][\w.\'\- ]+\s+(Wife|Husband|Son|Daughter|Head|Father|Mother|Boarder|Servant|Lodger|Brother|Sister)\b', line):
                result['household'].append(line)

        # Find image viewer link (anchor with 3:1: ARK)
        viewer_links = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a').forEach(el => {
                if (el.href && el.href.includes('ark:/61903/3:1:')) out.push(el.href);
            });
            return [...new Set(out)];
        }""")
        if viewer_links:
            result['image_viewer_url'] = viewer_links[0]
            m = re.search(r'ark:/61903/(3:1:[A-Z0-9-]+)', viewer_links[0])
            if m:
                result['image_ark'] = m.group(1)

        # Try to find image TH-ID from page HTML (used for direct download)
        html = await page.content()
        ths = re.findall(r'TH-\d+-\d+-\d+-\d+', html)
        if ths:
            from collections import Counter
            result['image_th_id'] = Counter(ths).most_common(1)[0][0]

        return result


def print_report(r: dict) -> None:
    print("=" * 70)
    print(f"URL:           {r['url']}")
    print(f"Final URL:     {r['final_url']}")
    print(f"Title:         {r['title']}")
    print()
    print("FIELDS")
    print("-" * 70)
    if r['fields']:
        for k, v in r['fields']:
            v_short = v if len(v) < 80 else v[:77] + "..."
            print(f"  {k:30}  {v_short}")
    else:
        print("  (no fields found)")
    print()
    print("HOUSEHOLD")
    print("-" * 70)
    if r['household']:
        for h in r['household']:
            print(f"  {h}")
    else:
        print("  (no household members detected)")
    print()
    print("IMAGE")
    print("-" * 70)
    print(f"  Viewer URL:  {r['image_viewer_url']}")
    print(f"  Image ARK:   {r['image_ark']}")
    print(f"  Image TH-ID: {r['image_th_id']}")
    print()
    if r['image_th_id']:
        print("Download command:")
        print(f"  uv run python3 download_fs_image.py {r['image_th_id']} <out-path.jpg>")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    ark_url = sys.argv[1]
    parsed = urlparse(ark_url)
    if not parsed.netloc.endswith('familysearch.org'):
        print(f"Warning: URL doesn't look like a FamilySearch ARK: {ark_url}", file=sys.stderr)

    result = asyncio.run(fetch(ark_url))
    print_report(result)


if __name__ == '__main__':
    main()
