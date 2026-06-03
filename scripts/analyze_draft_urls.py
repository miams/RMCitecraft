#!/usr/bin/env python3
"""
Analyze URL distribution in ww2_draft_updated.xlsx.
"""

from pathlib import Path

import openpyxl
from loguru import logger


def is_blank(value) -> bool:
    """Check if a cell value is blank/empty."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def main():
    """Analyze the spreadsheet."""
    xlsx_path = Path(__file__).parent.parent / "ww2_draft_updated.xlsx"

    if not xlsx_path.exists():
        logger.error(f"File not found: {xlsx_path}")
        return 1

    logger.info(f"📖 Loading {xlsx_path.name}...")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    sheet = wb.active

    # Find column indexes
    headers = [cell.value for cell in sheet[1]]
    try:
        fs_citation_col = headers.index("familysearch_citation") + 1
        ancestry_url_col = headers.index("ancestry_url") + 1
    except ValueError as e:
        logger.error(f"Required column not found: {e}")
        wb.close()
        return 1

    # Initialize counters
    fs_citation_stats = {
        "familysearch_url": 0,
        "ancestrylibrary_url": 0,
        "other_text": 0,
        "blank": 0,
    }

    ancestry_url_stats = {
        "ancestrylibrary_url": 0,
        "other_text": 0,
        "blank": 0,
    }

    total_rows = 0

    # Process rows
    for row in sheet.iter_rows(min_row=2):  # Skip header
        total_rows += 1

        # Analyze familysearch_citation column
        fs_citation = row[fs_citation_col - 1].value

        if is_blank(fs_citation):
            fs_citation_stats["blank"] += 1
        else:
            fs_citation_str = str(fs_citation)
            if "familysearch.org" in fs_citation_str.lower():
                fs_citation_stats["familysearch_url"] += 1
            elif "ancestrylibrary.com" in fs_citation_str.lower():
                fs_citation_stats["ancestrylibrary_url"] += 1
            else:
                fs_citation_stats["other_text"] += 1

        # Analyze ancestry_url column
        ancestry_url = row[ancestry_url_col - 1].value

        if is_blank(ancestry_url):
            ancestry_url_stats["blank"] += 1
        else:
            ancestry_url_str = str(ancestry_url)
            if "ancestrylibrary.com" in ancestry_url_str.lower():
                ancestry_url_stats["ancestrylibrary_url"] += 1
            else:
                ancestry_url_stats["other_text"] += 1

    wb.close()

    # Display results
    logger.info("\n" + "="*60)
    logger.info("📊 URL Distribution Analysis")
    logger.info("="*60)
    logger.info(f"\nTotal rows analyzed: {total_rows}\n")

    logger.info("familysearch_citation column:")
    logger.info(f"  • FamilySearch URLs:    {fs_citation_stats['familysearch_url']:>5} ({fs_citation_stats['familysearch_url']/total_rows*100:>5.1f}%)")
    logger.info(f"  • AncestryLibrary URLs: {fs_citation_stats['ancestrylibrary_url']:>5} ({fs_citation_stats['ancestrylibrary_url']/total_rows*100:>5.1f}%)")
    logger.info(f"  • Other text:           {fs_citation_stats['other_text']:>5} ({fs_citation_stats['other_text']/total_rows*100:>5.1f}%)")
    logger.info(f"  • Blank:                {fs_citation_stats['blank']:>5} ({fs_citation_stats['blank']/total_rows*100:>5.1f}%)")

    logger.info("\nancestry_url column:")
    logger.info(f"  • AncestryLibrary URLs: {ancestry_url_stats['ancestrylibrary_url']:>5} ({ancestry_url_stats['ancestrylibrary_url']/total_rows*100:>5.1f}%)")
    logger.info(f"  • Other text:           {ancestry_url_stats['other_text']:>5} ({ancestry_url_stats['other_text']/total_rows*100:>5.1f}%)")
    logger.info(f"  • Blank:                {ancestry_url_stats['blank']:>5} ({ancestry_url_stats['blank']/total_rows*100:>5.1f}%)")

    # Sanity check
    fs_total = sum(fs_citation_stats.values())
    ancestry_total = sum(ancestry_url_stats.values())

    if fs_total != total_rows or ancestry_total != total_rows:
        logger.warning(f"\n⚠️  Sanity check failed: counts don't match total rows")

    return 0


if __name__ == "__main__":
    exit(main())
