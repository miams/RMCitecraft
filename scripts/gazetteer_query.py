#!/usr/bin/env python3
"""
Gazetteer query script - mimics RootsMagic Gazetteer tool output.

Usage:
    python scripts/gazetteer_query.py "Hamburg"
    python scripts/gazetteer_query.py "Princeton"
"""

import sys
from pathlib import Path
from difflib import SequenceMatcher

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.utils.gazetteer_search import GazetteerSearch


def calculate_score(place_name: str, query: str) -> int:
    """
    Calculate similarity score (0-10000) similar to RootsMagic.

    10000 = exact match or contains exact query
    8000-9999 = very close match
    5000-7999 = partial match
    """
    place_upper = place_name.upper()
    query_upper = query.upper()

    # Exact match
    if place_upper == query_upper:
        return 10000

    # Contains exact query
    if query_upper in place_upper:
        return 10000

    # Fuzzy similarity
    similarity = SequenceMatcher(None, place_upper, query_upper).ratio()
    return int(similarity * 10000)


def format_gazetteer_results(query: str, max_results: int = 50):
    """
    Format gazetteer search results similar to RootsMagic Gazetteer tool.
    """
    searcher = GazetteerSearch()
    results = searcher.search(query, max_results=max_results)

    print("=" * 80)
    print(f"GAZETTEER SEARCH RESULTS")
    print("=" * 80)
    print(f"\nQuery: '{query}'")
    print(f"Found: {len(results)} matches\n")

    print(f"{'Place Name':<65} {'Score':>10}")
    print("-" * 80)

    # Calculate scores and sort by score (descending)
    scored_results = [
        (place, calculate_score(place, query))
        for place in results
    ]
    scored_results.sort(key=lambda x: (-x[1], x[0]))  # Sort by score desc, then name

    # Display results
    display_count = min(30, len(scored_results))
    for place_name, score in scored_results[:display_count]:
        # Clean up artifacts
        cleaned = place_name.strip()
        # Truncate if too long
        if len(cleaned) > 64:
            cleaned = cleaned[:61] + "..."

        print(f"{cleaned:<65} {score:>10}")

    if len(scored_results) > display_count:
        print(f"\n... and {len(scored_results) - display_count} more matches")

    print("\n" + "=" * 80)

    # Show note about hierarchies
    print("\nNOTE: PlaceDB.dat stores individual place components only.")
    print("Full hierarchies like 'Hamburg, Germany' are NOT in this file.")
    print("RootsMagic builds those from your database's PlaceTable or another source.")
    print("=" * 80)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/gazetteer_query.py <place_name>")
        print("\nExamples:")
        print("  python scripts/gazetteer_query.py Hamburg")
        print("  python scripts/gazetteer_query.py Princeton")
        print("  python scripts/gazetteer_query.py 'New Jersey'")
        sys.exit(1)

    query = ' '.join(sys.argv[1:])
    format_gazetteer_results(query)


if __name__ == '__main__':
    main()
