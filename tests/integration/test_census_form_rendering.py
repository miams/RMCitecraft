"""Integration tests for census form rendering.

These tests verify the full rendering pipeline from database to HTML output.
They use a temporary SQLite database with test data.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    CensusPage,
    CensusPerson,
    SCHEMA_SQL,
)
from rmcitecraft.models.census_form_data import (
    CensusFormContext,
    FieldValue,
    FormPageData,
    FormPersonRow,
)
from rmcitecraft.services.census_form_service import CensusFormDataService
from rmcitecraft.services.census_form_renderer import CensusFormRenderer


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize schema
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)

    # Create test batch
    cursor = conn.execute(
        "INSERT INTO extraction_batch (source, notes) VALUES (?, ?)",
        ("test", "Integration test data")
    )
    batch_id = cursor.lastrowid

    # Create test page (1950 census)
    cursor = conn.execute("""
        INSERT INTO census_page (
            batch_id, census_year, state, county, township_city,
            enumeration_district, page_number, stamp_number,
            enumeration_date, enumerator_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        batch_id, 1950, "California", "San Diego", "San Diego",
        "72-91", "10", "10", "April 4, 1950", "Test Enumerator"
    ))
    page_id = cursor.lastrowid

    # Create test persons
    test_persons = [
        (1, "Smith, John A", "John", "Smith", "Head", "M", "W", 45, "Mar", "Ohio", True),
        (2, "Smith, Mary B", "Mary", "Smith", "Wife", "F", "W", 42, "Mar", "Indiana", False),
        (6, "Jones, Robert C", "Robert", "Jones", "Head", "M", "W", 35, "Mar", "California", True),
        (7, "Jones, Alice D", "Alice", "Jones", "Wife", "F", "W", 32, "Mar", "Texas", False),
    ]

    person_ids = []
    for line, full_name, given, surname, rel, sex, race, age, marital, birthplace, is_target in test_persons:
        cursor = conn.execute("""
            INSERT INTO census_person (
                page_id, line_number, full_name, given_name, surname,
                relationship_to_head, sex, race, age, marital_status,
                birthplace, is_target_person
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (page_id, line, full_name, given, surname, rel, sex, race, age, marital, birthplace, 1 if is_target else 0))
        person_ids.append(cursor.lastrowid)

    # Add extended fields for sample line persons (lines 1 and 6)
    sample_fields = [
        (person_ids[0], "highest_grade_attended", "H4", "string", "Grade"),
        (person_ids[0], "income_wages_1949", "3500", "integer", "Wages"),
        (person_ids[2], "highest_grade_attended", "C2", "string", "Grade"),
        (person_ids[2], "veteran_status", "Yes", "string", "Veteran"),
    ]

    for person_id, field_name, field_value, field_type, fs_label in sample_fields:
        conn.execute("""
            INSERT INTO census_person_field (
                person_id, field_name, field_value, field_type, familysearch_label
            ) VALUES (?, ?, ?, ?, ?)
        """, (person_id, field_name, field_value, field_type, fs_label))

    # Add dwelling numbers
    conn.execute("""
        INSERT INTO census_person_field (person_id, field_name, field_value, field_type)
        VALUES (?, 'dwelling_number', '101', 'integer')
    """, (person_ids[0],))
    conn.execute("""
        INSERT INTO census_person_field (person_id, field_name, field_value, field_type)
        VALUES (?, 'dwelling_number', '101', 'integer')
    """, (person_ids[1],))
    conn.execute("""
        INSERT INTO census_person_field (person_id, field_name, field_value, field_type)
        VALUES (?, 'dwelling_number', '102', 'integer')
    """, (person_ids[2],))
    conn.execute("""
        INSERT INTO census_person_field (person_id, field_name, field_value, field_type)
        VALUES (?, 'dwelling_number', '102', 'integer')
    """, (person_ids[3],))

    conn.commit()
    conn.close()

    yield db_path, page_id, person_ids

    # Cleanup
    db_path.unlink()


class TestCensusFormDataService:
    """Integration tests for CensusFormDataService."""

    def test_load_form_context(self, temp_db):
        """Test loading form context from database."""
        db_path, page_id, person_ids = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)

        assert context is not None
        assert context.census_year == 1950
        assert len(context.pages) == 1
        assert len(context.pages[0].persons) == 4

    def test_load_form_context_page_metadata(self, temp_db):
        """Test page metadata is loaded correctly."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)
        page = context.primary_page

        assert page.state == "California"
        assert page.county == "San Diego"
        assert page.enumeration_district == "72-91"
        assert page.page_number == "10"

    def test_load_form_context_persons_sorted_by_line(self, temp_db):
        """Test persons are sorted by line number."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)
        persons = context.pages[0].persons

        line_numbers = [p.line_number for p in persons]
        assert line_numbers == sorted(line_numbers)

    def test_load_form_context_extended_fields(self, temp_db):
        """Test extended fields are loaded."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)

        # Find person on line 1 (sample line)
        person1 = next(p for p in context.pages[0].persons if p.line_number == 1)

        assert person1.has_field("highest_grade_attended")
        assert person1.get_field("highest_grade_attended") == "H4"

    def test_load_form_context_sample_persons_marked(self, temp_db):
        """Test sample line persons are correctly marked."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)
        persons = context.pages[0].persons

        # Lines 1 and 6 should be sample lines
        for person in persons:
            if person.line_number in (1, 6):
                assert person.is_sample_person
            else:
                assert not person.is_sample_person

    def test_load_form_context_households_grouped(self, temp_db):
        """Test persons are grouped into households."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id)

        # Should have 2 households (dwelling 101 and 102)
        assert len(context.households) == 2

    def test_load_form_context_for_person(self, temp_db):
        """Test loading context centered on a specific person."""
        db_path, page_id, person_ids = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context_for_person(person_ids[0])

        assert context is not None
        assert context.target_person is not None
        assert context.target_person.person_id == person_ids[0]

    def test_load_form_context_nonexistent_page(self, temp_db):
        """Test loading nonexistent page returns None."""
        db_path, _, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id=99999)

        assert context is None


class TestCensusFormRenderer:
    """Integration tests for CensusFormRenderer."""

    def test_render_page_produces_html(self, temp_db):
        """Test rendering produces valid HTML."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_page(page_id)

        assert html is not None
        assert "<html" in html
        assert "</html>" in html

    def test_render_page_includes_page_data(self, temp_db):
        """Test rendered HTML includes page metadata."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_page(page_id)

        assert "California" in html
        assert "San Diego" in html
        assert "72-91" in html

    def test_render_page_includes_persons(self, temp_db):
        """Test rendered HTML includes person data."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_page(page_id)

        assert "Smith, John A" in html
        assert "Smith, Mary B" in html
        assert "Jones, Robert C" in html

    def test_render_page_includes_sample_section(self, temp_db):
        """Test rendered HTML includes sample line section."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_page(page_id, include_sample_columns=True)

        # Should have sample section for 1950 census
        assert "SAMPLE LINE PERSONS" in html

    def test_render_for_person(self, temp_db):
        """Test rendering centered on a person."""
        db_path, page_id, person_ids = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_for_person(person_ids[0])

        assert html is not None
        assert "Smith, John A" in html

    def test_render_nonexistent_page_returns_error(self, temp_db):
        """Test rendering nonexistent page returns error HTML."""
        db_path, _, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        html = renderer.render_page(page_id=99999)

        assert "Error" in html
        assert "not found" in html

    def test_render_from_context(self, temp_db):
        """Test rendering from pre-built context."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)
        renderer = CensusFormRenderer(data_service=service)

        context = service.load_form_context(page_id)
        html = renderer.render_from_context(context)

        assert html is not None
        assert "San Diego" in html


class TestRenderingQuality:
    """Tests for quality indicator rendering."""

    def test_context_includes_quality_flag(self, temp_db):
        """Test context includes quality indicator flag."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id, include_quality=True)

        assert context.show_quality_indicators is True

    def test_context_without_quality(self, temp_db):
        """Test context can be loaded without quality data."""
        db_path, page_id, _ = temp_db
        service = CensusFormDataService(db_path)

        context = service.load_form_context(page_id, include_quality=False)

        # Should still load successfully
        assert context is not None


class TestTemplateFiles:
    """Tests for template file existence."""

    def test_jinja_templates_exist(self):
        """Test that Jinja2 template files exist."""
        templates_dir = Path(__file__).parent.parent.parent / "src" / "rmcitecraft" / "templates" / "census" / "jinja"

        assert (templates_dir / "base.html").exists()
        assert (templates_dir / "1950.html").exists()

    def test_css_file_exists(self):
        """Test that CSS file exists."""
        css_path = Path(__file__).parent.parent.parent / "src" / "rmcitecraft" / "templates" / "census" / "static" / "census_forms.css"

        assert css_path.exists()

    def test_css_contains_1950_styles(self):
        """Test CSS file contains 1950-specific styles."""
        css_path = Path(__file__).parent.parent.parent / "src" / "rmcitecraft" / "templates" / "census" / "static" / "census_forms.css"

        css_content = css_path.read_text()

        assert ".census-1950" in css_content
        assert ".sample-line" in css_content
        assert ".quality-" in css_content
