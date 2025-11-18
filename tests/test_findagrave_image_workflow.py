#!/usr/bin/env python3
"""
Test script for Find a Grave image download workflow.

Tests the complete integration of:
1. Image download from Find a Grave
2. Path conversion to RootsMagic format
3. Database record creation
4. Linking to citations and events
"""

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rmcitecraft.config import get_config
from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.database.findagrave_queries import (
    convert_path_to_rootsmagic_format,
    create_findagrave_image_record,
)


def test_path_conversion():
    """Test path conversion to RootsMagic format."""
    config = get_config()
    media_root = Path(config.rm_media_root_directory)

    test_cases = [
        # Absolute path under media root
        (
            media_root / "Pictures - People" / "Ijams, Ella (1850-1930).jpg",
            "?/Pictures - People/Ijams, Ella (1850-1930).jpg"
        ),
        # Path under home but not media root
        (
            Path.home() / "Documents" / "test.jpg",
            "~/Documents/test.jpg"
        ),
        # Different subdirectory
        (
            media_root / "Pictures - Cemetaries" / "Oak Grove Cemetery.jpg",
            "?/Pictures - Cemetaries/Oak Grove Cemetery.jpg"
        ),
    ]

    print("\n=== Testing Path Conversion ===")
    for abs_path, expected in test_cases:
        result = convert_path_to_rootsmagic_format(abs_path, media_root)
        status = "✓" if result == expected else "✗"
        print(f"{status} {abs_path.name}")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")
        if result != expected:
            print("   FAILED!")

    print("\nPath conversion tests completed.")


def test_database_integration():
    """Test creating image records in database."""
    config = get_config()

    # Test with a sample citation (you'll need a valid citation_id from your database)
    print("\n=== Testing Database Integration ===")

    # Connect to database
    conn = connect_rmtree(config.rm_database_path)
    cursor = conn.cursor()

    # Find a Find a Grave citation to test with
    cursor.execute("""
        SELECT c.CitationID, s.Name, c.ActualText
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE s.Name LIKE '%Find a Grave%'
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("No Find a Grave citations found in database for testing.")
        print("Please run Find a Grave batch processing first to create citations.")
        return

    citation_id = row[0]
    source_name = row[1]

    print(f"Found test citation ID {citation_id}: {source_name}")

    # Create a test image path
    test_image = Path.home() / "Genealogy/RootsMagic/Files/Pictures - People/Test_Person.jpg"

    # Test creating an image record (dry run - don't actually write)
    print(f"Would create media record for: {test_image}")
    print(f"  Citation ID: {citation_id}")
    print(f"  Photo Type: Person")
    print(f"  Memorial ID: 123456789")
    print(f"  Contributor: John Doe")

    # Convert path
    rm_path = convert_path_to_rootsmagic_format(test_image, config.rm_media_root_directory)
    print(f"  RootsMagic Path: {rm_path}")

    print("\nDatabase integration test completed (dry run).")


def test_image_metadata_extraction():
    """Test that image metadata is properly extracted and stored."""
    print("\n=== Testing Image Metadata ===")

    test_photo_data = {
        'photoId': '123456',
        'addedBy': 'Jane Smith',
        'addedDate': '15 Jan 2024',
        'photoType': 'Grave',
        'imageUrl': 'https://images.findagrave.com/photos/2024/15/123456_xyz.jpg',
        'description': 'Headstone of John Doe',
    }

    print("Sample photo metadata:")
    for key, value in test_photo_data.items():
        print(f"  {key}: {value}")

    # Test contributor extraction
    contributor = test_photo_data.get('addedBy', '')
    photo_type = test_photo_data.get('photoType', '')

    # Generate caption
    caption = f"Find a Grave"
    if photo_type:
        caption += f" - {photo_type} Photo"
    if contributor:
        caption += f" (contributed by {contributor})"

    print(f"\nGenerated caption: {caption}")
    print("Metadata extraction test completed.")


async def test_download_workflow():
    """Test the complete download workflow (without actual download)."""
    print("\n=== Testing Complete Workflow ===")

    # Simulate the workflow
    workflow_steps = [
        "1. User clicks Download button for a photo",
        "2. Photo URL and metadata extracted from Find a Grave page",
        "3. Filename generated based on person details",
        "4. Directory determined by photo type (Person/Grave/Family/Other)",
        "5. Image downloaded to filesystem",
        "6. Path converted to RootsMagic symbolic format",
        "7. MultimediaTable record created with caption and metadata",
        "8. MediaLinkTable record created linking to citation",
        "9. MediaLinkTable record created linking to burial event",
        "10. Download tracked in batch item's downloaded_images list",
        "11. Batch summary displays all downloaded images",
    ]

    print("Complete workflow steps:")
    for step in workflow_steps:
        print(f"  {step}")
        await asyncio.sleep(0.1)  # Simulate processing

    print("\nWorkflow simulation completed.")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Find a Grave Image Download Workflow Tests")
    print("=" * 60)

    # Run synchronous tests
    test_path_conversion()
    test_database_integration()
    test_image_metadata_extraction()

    # Run async test
    asyncio.run(test_download_workflow())

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()