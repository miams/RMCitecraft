#!/usr/bin/env python3
"""
Test script for RootsMagic gazetteer search functionality.

Demonstrates how to search and validate places using PlaceDB.dat.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.utils.gazetteer_search import GazetteerSearch, search_gazetteer, validate_place


def main():
    print("RootsMagic Gazetteer Search Test")
    print("=" * 60)

    try:
        searcher = GazetteerSearch()
        print(f"✓ Gazetteer loaded: {searcher.db_path}\n")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("  Make sure RootsMagic 11 is installed at default location.")
        return 1

    # Test 1: Search for Princeton
    print("Test 1: Search for 'Princeton'")
    print("-" * 60)
    results = searcher.search("Princeton", max_results=20)
    print(f"Found {len(results)} matches:")
    for i, place in enumerate(results[:10], 1):
        print(f"  {i:2d}. {place}")
    if len(results) > 10:
        print(f"  ... and {len(results) - 10} more")
    print()

    # Test 2: Search for Ohio
    print("Test 2: Search for 'Ohio'")
    print("-" * 60)
    results = searcher.search("Ohio", max_results=15)
    print(f"Found {len(results)} matches:")
    for i, place in enumerate(results, 1):
        print(f"  {i:2d}. {place}")
    print()

    # Test 3: Validate specific places
    print("Test 3: Validate place names")
    print("-" * 60)
    test_places = [
        ("Princeton", False),
        ("Princeton Township", False),
        ("Noble", False),
        ("Ohio", False),
        ("United States", False),
        ("New Jersey", False),
        ("Princeton, Mercer, New Jersey", True),  # Full hierarchy (fuzzy)
    ]

    for place, fuzzy in test_places:
        exists = searcher.exists(place, fuzzy=fuzzy)
        match_type = "fuzzy" if fuzzy else "exact"
        status = "✓" if exists else "✗"
        print(f"  {status} '{place}' ({match_type}): {exists}")
    print()

    # Test 4: Validate hierarchy
    print("Test 4: Validate place hierarchy")
    print("-" * 60)
    validation = searcher.validate_hierarchy(
        city="Princeton",
        state="New Jersey",
        country="United States"
    )
    print("  Princeton, New Jersey, United States:")
    for component, result in validation.items():
        status = "✓" if result else "✗"
        print(f"    {status} {component:15s}: {result}")
    print()

    # Test 5: Suggest places
    print("Test 5: Get place suggestions")
    print("-" * 60)
    partial = "Prince"
    suggestions = searcher.suggest_places(partial, max_suggestions=10)
    print(f"  Suggestions for '{partial}':")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"    {i:2d}. {suggestion}")
    print()

    # Test 6: Search for Find a Grave example locations
    print("Test 6: Find a Grave example locations")
    print("-" * 60)
    findagrave_locations = [
        "Princeton",
        "Mercer",
        "Noble",
        "Baltimore",
        "Texas",
        "Milam"
    ]

    for location in findagrave_locations:
        exists = searcher.exists(location, fuzzy=True, threshold=0.85)
        status = "✓" if exists else "✗"
        print(f"  {status} {location:20s}: {exists}")
    print()

    print("=" * 60)
    print("✓ All tests completed successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
