#!/usr/bin/env python3
"""Test source name fallback parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.rmcitecraft.parsers.source_name_parser import (
    SourceNameParser,
    augment_citation_data_from_source
)

# Test parsing
test_sources = [
    "Fed Census: 1950, Ohio, Stark [] Adams, Verne",
    "Fed Census: 1940, Kansas, Clay [citing ED 95] Iams, Henrietta",
    "Fed Census: 1930, Georgia, Spalding [sheet 3B, family 57] Imes,Jessie (Allen)",
]

print("Testing Source Name Parser")
print("="*80)

for source in test_sources:
    print(f"\nSource: {source}")
    parsed = SourceNameParser.parse(source)
    print(f"  Year: {parsed.get('year')}")
    print(f"  State: {parsed.get('state')}")
    print(f"  County: {parsed.get('county')}")
    print(f"  Brackets: {parsed.get('bracket_content')}")
    print(f"  Person: {parsed.get('person_ref')}")

print("\n\n")
print("Testing Fallback Augmentation")
print("="*80)

# Simulate incomplete extraction (like the problem we had)
incomplete_data = {
    'state': '',  # MISSING
    'county': '',  # MISSING
    'person_name': 'Verne D Adams',
    'familysearch_url': 'https://www.familysearch.org/ark:/61903/1:1:6XYT-2R3N',
}

source_name = "Fed Census: 1950, Ohio, Stark [] Adams, Verne"

print(f"\nIncomplete extraction data: {incomplete_data}")
print(f"Source name: {source_name}")

# Augment with fallback
augmented = augment_citation_data_from_source(incomplete_data, source_name)

print(f"\nAugmented data: {augmented}")
print(f"\n✅ State filled from source name: {augmented.get('state')}")
print(f"✅ County filled from source name: {augmented.get('county')}")
print(f"📋 Source: {augmented.get('_state_source')}")
