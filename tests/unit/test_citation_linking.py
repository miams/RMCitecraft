"""
Unit tests for Find a Grave citation linking logic.

Tests the three citation linking rules:
1. ALWAYS link to Person (OwnerType=0)
2. CONDITIONALLY link to Burial Event (OwnerType=2) - if cemetery exists
3. CONDITIONALLY link to Families (OwnerType=1) - if spouse/parents mentioned
"""

import pytest
import sqlite3
from pathlib import Path

from rmcitecraft.database.findagrave_queries import (
    link_citation_to_person,
    link_citation_to_families,
    create_findagrave_source_and_citation,
)
from rmcitecraft.database.connection import connect_rmtree


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary test database with minimal schema."""
    db_path = tmp_path / "test.rmtree"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create minimal schema for citation linking tests
    cursor.executescript("""
        CREATE TABLE PersonTable (
            PersonID INTEGER PRIMARY KEY,
            UTCModDate FLOAT
        );

        CREATE TABLE NameTable (
            NameID INTEGER PRIMARY KEY,
            OwnerID INTEGER,
            Surname TEXT COLLATE NOCASE,
            Given TEXT COLLATE NOCASE,
            Prefix TEXT,
            Suffix TEXT,
            IsPrimary INTEGER,
            UTCModDate FLOAT
        );

        CREATE TABLE FamilyTable (
            FamilyID INTEGER PRIMARY KEY,
            FatherID INTEGER,
            MotherID INTEGER,
            UTCModDate FLOAT
        );

        CREATE TABLE ChildTable (
            RecID INTEGER PRIMARY KEY,
            ChildID INTEGER,
            FamilyID INTEGER,
            RelFather INTEGER,
            RelMother INTEGER,
            UTCModDate FLOAT
        );

        CREATE TABLE SourceTable (
            SourceID INTEGER PRIMARY KEY,
            Name TEXT,
            RefNumber TEXT,
            ActualText TEXT,
            Comments TEXT,
            IsPrivate INTEGER,
            TemplateID INTEGER,
            Fields BLOB,
            UTCModDate FLOAT
        );

        CREATE TABLE CitationTable (
            CitationID INTEGER PRIMARY KEY,
            SourceID INTEGER,
            Comments TEXT,
            ActualText TEXT,
            RefNumber TEXT,
            Footnote TEXT,
            ShortFootnote TEXT,
            Bibliography TEXT,
            Fields BLOB,
            CitationName TEXT,
            UTCModDate FLOAT
        );

        CREATE TABLE CitationLinkTable (
            LinkID INTEGER PRIMARY KEY,
            CitationID INTEGER,
            OwnerType INTEGER,
            OwnerID INTEGER,
            SortOrder INTEGER,
            Quality TEXT,
            IsPrivate INTEGER,
            Flags INTEGER,
            UTCModDate FLOAT
        );
    """)

    conn.commit()
    conn.close()

    return str(db_path)


def create_test_person(db_path, person_id, surname, given):
    """Helper to create a test person with primary name."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO PersonTable (PersonID, UTCModDate) VALUES (?, ?)",
        (person_id, 0.0)
    )

    cursor.execute(
        """INSERT INTO NameTable (OwnerID, Surname, Given, Prefix, Suffix, IsPrimary, UTCModDate)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (person_id, surname, given, '', '', 1, 0.0)
    )

    conn.commit()
    conn.close()


def create_test_family(db_path, family_id, father_id, mother_id, child_ids=None):
    """Helper to create a test family."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO FamilyTable (FamilyID, FatherID, MotherID, UTCModDate) VALUES (?, ?, ?, ?)",
        (family_id, father_id, mother_id, 0.0)
    )

    if child_ids:
        for child_id in child_ids:
            cursor.execute(
                """INSERT INTO ChildTable (ChildID, FamilyID, RelFather, RelMother, UTCModDate)
                   VALUES (?, ?, ?, ?, ?)""",
                (child_id, family_id, 0, 0, 0.0)
            )

    conn.commit()
    conn.close()


def create_test_citation(db_path, source_id=1, citation_id=1):
    """Helper to create a test source and citation."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create source
    cursor.execute(
        """INSERT INTO SourceTable (SourceID, Name, RefNumber, ActualText, Comments,
                                      IsPrivate, TemplateID, Fields, UTCModDate)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source_id, "Test Source", "", "", "", 0, 0, b'<Root><Fields></Fields></Root>', 0.0)
    )

    # Create citation
    cursor.execute(
        """INSERT INTO CitationTable (CitationID, SourceID, Comments, ActualText, RefNumber,
                                       Footnote, ShortFootnote, Bibliography, Fields,
                                       CitationName, UTCModDate)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (citation_id, source_id, "", "", "", "", "", "", b'<Root><Fields></Fields></Root>', "", 0.0)
    )

    conn.commit()
    conn.close()

    return citation_id


# =============================================================================
# Tests for link_citation_to_person() - RULE #1: ALWAYS link to Person
# =============================================================================

def test_link_citation_to_person_creates_link(test_db_path):
    """Test that link_citation_to_person() creates a Person link."""
    # Setup
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Execute
    link_id = link_citation_to_person(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id
    )

    # Verify
    assert link_id is not None

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT LinkID, OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?",
        (citation_id,)
    )
    links = cursor.fetchall()
    conn.close()

    assert len(links) == 1
    assert links[0][1] == 0  # OwnerType = 0 (Person)
    assert links[0][2] == 1  # OwnerID = PersonID 1


def test_link_citation_to_person_prevents_duplicate(test_db_path):
    """Test that linking same citation to person twice doesn't create duplicate."""
    # Setup
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Execute - link twice
    link_id1 = link_citation_to_person(test_db_path, person_id=1, citation_id=citation_id)
    link_id2 = link_citation_to_person(test_db_path, person_id=1, citation_id=citation_id)

    # Verify
    assert link_id1 is not None
    assert link_id2 is None  # Second call should skip (duplicate)

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE CitationID = ?", (citation_id,))
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 1  # Only one link created


# =============================================================================
# Tests for link_citation_to_families() - RULE #3A: Parent families (spouse)
# =============================================================================

def test_link_to_parent_family_spouse_mentioned(test_db_path):
    """Test linking to family where person is parent AND spouse is mentioned."""
    # Setup: John (1) married to Alice (2)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=2, surname="Johnson", given="Alice")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2)
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with spouse mentioned
    family_data = {
        'spouse': [{'name': 'Alice Johnson', 'dates': '1850-1920'}]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 1
    assert family_ids[0] == 1

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ? AND OwnerType = 1",
        (citation_id,)
    )
    links = cursor.fetchall()
    conn.close()

    assert len(links) == 1
    assert links[0][0] == 1  # OwnerType = 1 (Family)
    assert links[0][1] == 1  # FamilyID = 1


def test_link_to_parent_family_spouse_not_mentioned(test_db_path):
    """Test NO link to family where person is parent but spouse NOT mentioned."""
    # Setup: John (1) married to Alice (2)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=2, surname="Johnson", given="Alice")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2)
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with NO spouse mentioned
    family_data = {
        'spouse': []  # Empty spouse list
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 0  # No families linked

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE CitationID = ?", (citation_id,))
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0  # No links created


def test_link_to_parent_family_multiple_spouses(test_db_path):
    """Test linking to multiple families when person remarried and both spouses mentioned."""
    # Setup: John (1) married to Alice (2), then remarried to Betty (3)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=2, surname="Johnson", given="Alice")
    create_test_person(test_db_path, person_id=3, surname="Williams", given="Betty")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2)
    create_test_family(test_db_path, family_id=2, father_id=1, mother_id=3)
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with BOTH spouses mentioned
    family_data = {
        'spouse': [
            {'name': 'Alice Johnson', 'dates': '1850-1920'},
            {'name': 'Betty Williams', 'dates': '1860-1930'}
        ]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 2  # Both families linked
    assert 1 in family_ids
    assert 2 in family_ids


def test_link_to_parent_family_one_spouse_mentioned(test_db_path):
    """Test linking only to family where spouse mentioned (not all families)."""
    # Setup: John (1) married to Alice (2), then remarried to Betty (3)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=2, surname="Johnson", given="Alice")
    create_test_person(test_db_path, person_id=3, surname="Williams", given="Betty")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2)
    create_test_family(test_db_path, family_id=2, father_id=1, mother_id=3)
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with ONLY Alice mentioned
    family_data = {
        'spouse': [
            {'name': 'Alice Johnson', 'dates': '1850-1920'}
        ]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 1  # Only Alice's family linked
    assert family_ids[0] == 1


# =============================================================================
# Tests for link_citation_to_families() - RULE #3B: Child families (parents)
# =============================================================================

def test_link_to_child_family_parents_mentioned(test_db_path):
    """Test linking to family where person is child AND parents are mentioned."""
    # Setup: Father (1), Mother (2), Child John (3)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="William")
    create_test_person(test_db_path, person_id=2, surname="Smith", given="Mary")
    create_test_person(test_db_path, person_id=3, surname="Smith", given="John")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2, child_ids=[3])
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with parents mentioned
    family_data = {
        'parents': [
            {'name': 'William Smith', 'dates': '1820-1890'},
            {'name': 'Mary Smith', 'dates': '1825-1895'}
        ]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=3,  # John is the child
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 1
    assert family_ids[0] == 1

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ? AND OwnerType = 1",
        (citation_id,)
    )
    links = cursor.fetchall()
    conn.close()

    assert len(links) == 1
    assert links[0][1] == 1  # FamilyID = 1


def test_link_to_child_family_parents_not_mentioned(test_db_path):
    """Test NO link to family where person is child but parents NOT mentioned."""
    # Setup: Father (1), Mother (2), Child John (3)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="William")
    create_test_person(test_db_path, person_id=2, surname="Smith", given="Mary")
    create_test_person(test_db_path, person_id=3, surname="Smith", given="John")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2, child_ids=[3])
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with NO parents mentioned
    family_data = {
        'parents': []  # Empty parents list
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=3,  # John is the child
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 0  # No families linked


def test_link_to_child_family_one_parent_mentioned(test_db_path):
    """Test linking to child family when only ONE parent is mentioned."""
    # Setup: Father (1), Mother (2), Child John (3)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="William")
    create_test_person(test_db_path, person_id=2, surname="Smith", given="Mary")
    create_test_person(test_db_path, person_id=3, surname="Smith", given="John")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2, child_ids=[3])
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with ONLY father mentioned
    family_data = {
        'parents': [
            {'name': 'William Smith', 'dates': '1820-1890'}
        ]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=3,
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 1  # Family linked if ANY parent mentioned
    assert family_ids[0] == 1


# =============================================================================
# Tests for combined scenarios
# =============================================================================

def test_link_to_both_parent_and_child_families(test_db_path):
    """Test linking to BOTH parent family (spouse) and child family (parents)."""
    # Setup: Person John (3) is child of William (1) + Mary (2), and married to Alice (4)
    create_test_person(test_db_path, person_id=1, surname="Smith", given="William")
    create_test_person(test_db_path, person_id=2, surname="Smith", given="Mary")
    create_test_person(test_db_path, person_id=3, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=4, surname="Johnson", given="Alice")

    # Parent family (John is child)
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2, child_ids=[3])

    # John's family (John is parent)
    create_test_family(test_db_path, family_id=2, father_id=3, mother_id=4)

    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Family data with BOTH spouse AND parents mentioned
    family_data = {
        'spouse': [{'name': 'Alice Johnson', 'dates': '1850-1920'}],
        'parents': [{'name': 'William Smith', 'dates': '1820-1890'}]
    }

    # Execute
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=3,  # John
        citation_id=citation_id,
        family_data=family_data
    )

    # Verify
    assert len(family_ids) == 2  # Both families linked
    assert 1 in family_ids  # Parent family
    assert 2 in family_ids  # Spouse family


def test_no_family_data_backward_compatibility(test_db_path):
    """Test that passing None for family_data creates links (backward compatibility)."""
    # Setup
    create_test_person(test_db_path, person_id=1, surname="Smith", given="John")
    create_test_person(test_db_path, person_id=2, surname="Johnson", given="Alice")
    create_test_family(test_db_path, family_id=1, father_id=1, mother_id=2)
    citation_id = create_test_citation(test_db_path, source_id=1, citation_id=1)

    # Execute with family_data=None
    family_ids = link_citation_to_families(
        db_path=test_db_path,
        person_id=1,
        citation_id=citation_id,
        family_data=None  # Backward compatibility mode
    )

    # Verify - should create link (old behavior)
    assert len(family_ids) == 1
    assert family_ids[0] == 1
