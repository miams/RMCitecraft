#!/usr/bin/env python3
"""Download a high-resolution census image from FamilySearch via the deep-zoom scale endpoint.

The image is fetched through the user's existing Chrome CDP session
(localhost:9222) so authentication cookies / session apply automatically.

Usage:
    uv run python3 download_fs_image.py <TH-ID> <output-path> [--width N]

Args:
    <TH-ID>        Image TH ID like 'TH-1942-27890-6409-22' (see fetch_familysearch_record.py).
    <output-path>  Absolute path to save the .jpg.
    --width N      Resolution width in pixels. Default 6000 (~2-3 MB, fully readable).
                   Try 12000 for top-of-card ED stamps.

Example:
    uv run python3 download_fs_image.py TH-1942-27890-6409-22 \\
        "$HOME/Genealogy/RootsMagic/Files/Records - Census/1940 Federal/1940, New Mexico, Santa Fe - Iams, John Willis.jpg"

The download endpoint pattern (from observing the FamilySearch viewer):
    https://sg30p0.familysearch.org/service/records/storage/deepzoomcloud/dz/v1/<TH-ID>/scale?width=<N>

Some images live on different region subdomains (sg30p0, sg30p1, etc.); this
script tries `sg30p0` first and falls back to `apid:` prefix variant if needed.
"""
import asyncio
import os
import sys


CDP_URL = "http://localhost:9222"


def _build_urls(th_id: str, width: int) -> list[str]:
    return [
        f"https://sg30p0.familysearch.org/service/records/storage/deepzoomcloud/dz/v1/{th_id}/scale?width={width}",
        f"https://sg30p0.familysearch.org/service/records/storage/deepzoomcloud/dz/v1/apid:{th_id}/scale?width={width}",
    ]


async def download(th_id: str, out_path: str, width: int) -> int:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"ERROR: Could not connect to Chrome CDP at {CDP_URL}: {e}", file=sys.stderr)
            print("Start Chrome with --remote-debugging-port=9222 first (see project CLAUDE.md).", file=sys.stderr)
            return 2

        ctx = browser.contexts[0]

        for url in _build_urls(th_id, width):
            print(f"Trying: {url}", file=sys.stderr)
            try:
                resp = await ctx.request.get(url, timeout=90000)
            except Exception as e:
                print(f"  Request error: {e}", file=sys.stderr)
                continue
            ctype = resp.headers.get('content-type', '')
            print(f"  Status: {resp.status}, Content-Type: {ctype}", file=sys.stderr)
            if resp.status == 200 and 'image' in ctype:
                body = await resp.body()
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, 'wb') as f:
                    f.write(body)
                print(f"SAVED {len(body):,} bytes -> {out_path}", file=sys.stderr)
                print(out_path)  # stdout: path so callers can pipe
                return 0
        print("ERROR: All download URLs failed.", file=sys.stderr)
        return 1


def main():
    args = sys.argv[1:]
    width = 6000
    if '--width' in args:
        i = args.index('--width')
        try:
            width = int(args[i + 1])
        except (IndexError, ValueError):
            print("--width requires an integer", file=sys.stderr)
            sys.exit(2)
        args = args[:i] + args[i + 2:]

    if len(args) != 2:
        print(__doc__)
        sys.exit(2)

    th_id, out_path = args
    if not th_id.startswith('TH-'):
        print(f"Warning: TH-ID doesn't start with 'TH-': {th_id}", file=sys.stderr)
    if not out_path.endswith('.jpg'):
        print(f"Warning: output path doesn't end with .jpg: {out_path}", file=sys.stderr)

    out_path = os.path.expanduser(out_path)
    sys.exit(asyncio.run(download(th_id, out_path, width)))


if __name__ == '__main__':
    main()
