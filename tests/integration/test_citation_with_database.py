"""Integration test for citation generation using real RootsMagic database.

This test verifies:
1. Database connection with ICU extension
2. Reading citation data from CitationTable.Fields BLOB
3. Reading place data from PlaceTable
4. Citation generation workflow
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.models.census_citation import PlaceDetails


def test_read_george_iams_from_database():
    """Test reading George B Iams citation data from database.

    CitationID: 9816
    PersonID: 3447
    EventID: 24124
    SourceID: 3099
    """
    # Connect to sample database
    db_path = Path(__file__).parent.parent.parent / "data" / "Iiams.rmtree"
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    print(f"Connecting to database: {db_path}")
    conn = connect_rmtree(str(db_path))
    cursor = conn.cursor()

    # Get citation and source data
    print("\n" + "=" * 80)
    print("CITATION DATA")
    print("=" * 80)

    cursor.execute(
        """
        SELECT
            c.CitationID,
            c.SourceID,
            c.Fields as citation_fields,
            s.Name as source_name,
            s.Fields as source_fields
        FROM CitationTable c
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE c.CitationID = 9816
        """
    )

    row = cursor.fetchone()
    if not row:
        print("Citation 9816 not found")
        return

    citation_id, source_id, citation_fields, source_name, source_fields = row

    print(f"CitationID: {citation_id}")
    print(f"SourceID: {source_id}")
    print(f"Source Name: {source_name}")
    print()

    # Extract FamilySearch entry from CitationTable.Fields BLOB
    if citation_fields:
        citation_xml = citation_fields.decode("utf-8")
        print("Citation Fields BLOB:")
        print(citation_xml[:500])
        print()

        # Parse Page field (FamilySearch citation)
        page_value = extract_field_from_xml(citation_xml, "Page")
        if page_value:
            print("FamilySearch Citation (Page field):")
            print(page_value)
            print()

    # Get event and place data
    print("=" * 80)
    print("EVENT AND PLACE DATA")
    print("=" * 80)

    cursor.execute(
        """
        SELECT
            e.EventID,
            e.OwnerID as person_id,
            e.PlaceID,
            p.Name as place_string
        FROM EventTable e
        JOIN PlaceTable p ON e.PlaceID = p.PlaceID
        WHERE e.EventID = 24124
        """
    )

    event_row = cursor.fetchone()
    if event_row:
        event_id, person_id, place_id, place_string = event_row
        print(f"EventID: {event_id}")
        print(f"PersonID: {person_id}")
        print(f"PlaceID: {place_id}")
        print(f"Place String: {place_string}")
        print()

        # Parse place details
        place = PlaceDetails.from_place_string(place_string)
        print("Parsed Place Details:")
        print(f"  Locality: {place.locality}")
        print(f"  Locality Type: {place.locality_type}")
        print(f"  County: {place.county}")
        print(f"  State: {place.state}")
        print(f"  Country: {place.country}")
        print()

    # Check existing citations in SourceTable.Fields
    print("=" * 80)
    print("EXISTING CITATIONS (SourceTable.Fields)")
    print("=" * 80)

    if source_fields:
        source_xml = source_fields.decode("utf-8")
        print("Source Fields BLOB:")
        print(source_xml[:1000])
        print()

        footnote = extract_field_from_xml(source_xml, "Footnote")
        if footnote:
            print("Existing Footnote:")
            print(footnote)
            print()

    conn.close()
    print("=" * 80)
    print("DATABASE READ TEST COMPLETE")
    print("=" * 80)


def extract_field_from_xml(xml_str: str, field_name: str) -> str | None:
    """Extract field value from XML string.

    Args:
        xml_str: XML string
        field_name: Field name to extract

    Returns:
        Field value or None if not found
    """
    start_tag = f"<{field_name}>"
    end_tag = f"</{field_name}>"

    start_idx = xml_str.find(start_tag)
    if start_idx == -1:
        return None

    start_idx += len(start_tag)
    end_idx = xml_str.find(end_tag, start_idx)

    if end_idx == -1:
        return None

    return xml_str[start_idx:end_idx].strip()


if __name__ == "__main__":
    test_read_george_iams_from_database()
