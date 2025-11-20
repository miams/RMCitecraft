#!/usr/bin/env python3
"""Test data quality validation on the problematic entries."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.rmcitecraft.validation.data_quality import validate_before_update

# Simulate the data that was extracted (empty state/county)
bad_data = {
    'state': '',  # MISSING!
    'county': '',  # MISSING!
    'person_name': 'Verne D Adams',
    'familysearch_url': 'https://www.familysearch.org/ark:/61903/1:1:6XYT-2R3N',
    'enumeration_district': '',  # Also missing for 1950
    'sheet': '',
    'line': '',
}

print("Testing data quality validation on incomplete extraction:")
print("="*80)
print(f"Input data: {bad_data}\n")

result = validate_before_update(bad_data, census_year=1950)

print(result.summary())
print()

if result.errors:
    print("❌ CRITICAL ERRORS:")
    for error in result.errors:
        print(f"  - {error}")
    print()

if result.warnings:
    print("⚠️  WARNINGS:")
    for warning in result.warnings:
        print(f"  - {warning}")
    print()

if result.missing_optional:
    print("ℹ️  MISSING OPTIONAL FIELDS:")
    for field in result.missing_optional:
        print(f"  - {field}")
    print()

print("="*80)
if result.is_valid:
    print("✅ WOULD PROCEED with database update")
else:
    print("❌ SHOULD NOT PROCEED - Data quality check failed!")
    print("   Database update should be blocked until data is corrected.")

# Now test with good data
print("\n\n")
print("Testing data quality validation on complete extraction:")
print("="*80)

good_data = {
    'state': 'Ohio',
    'county': 'Stark',
    'person_name': 'Verne D Adams',
    'familysearch_url': 'https://www.familysearch.org/ark:/61903/1:1:6XYT-2R3N',
    'enumeration_district': '95-123',
    'sheet': '5A',
    'line': '42',
    'town_ward': 'Canton',
}

print(f"Input data: {good_data}\n")

result2 = validate_before_update(good_data, census_year=1950)
print(result2.summary())

if result2.is_valid:
    print("\n✅ SAFE TO PROCEED with database update")
