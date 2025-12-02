"""Unit tests for census form data models."""

import pytest
from datetime import datetime

from rmcitecraft.models.census_form_data import (
    CensusFormContext,
    FieldQualityLevel,
    FieldValue,
    FormColumnDef,
    FormHousehold,
    FormPageData,
    FormPersonRow,
    get_columns_for_year,
    COLUMNS_1950,
)


class TestFieldValue:
    """Tests for FieldValue dataclass."""

    def test_str_returns_value(self):
        """Test string conversion returns the value."""
        fv = FieldValue(value="John Smith")
        assert str(fv) == "John Smith"

    def test_str_returns_empty_for_none(self):
        """Test string conversion returns empty for None value."""
        fv = FieldValue(value=None)
        assert str(fv) == ""

    def test_str_returns_int_as_string(self):
        """Test integer values are converted to strings."""
        fv = FieldValue(value=25)
        assert str(fv) == "25"

    def test_has_quality_issue_false_for_clear(self):
        """Test clear quality doesn't indicate issue."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.CLEAR)
        assert not fv.has_quality_issue

    def test_has_quality_issue_false_for_verified(self):
        """Test verified quality doesn't indicate issue."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.VERIFIED)
        assert not fv.has_quality_issue

    def test_has_quality_issue_true_for_uncertain(self):
        """Test uncertain quality indicates issue."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.UNCERTAIN)
        assert fv.has_quality_issue

    def test_has_quality_issue_true_for_damaged(self):
        """Test damaged quality indicates issue."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.DAMAGED)
        assert fv.has_quality_issue

    def test_has_quality_issue_true_for_illegible(self):
        """Test illegible quality indicates issue."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.ILLEGIBLE)
        assert fv.has_quality_issue

    def test_css_class_returns_correct_format(self):
        """Test CSS class is correctly formatted."""
        fv = FieldValue(value="test", quality=FieldQualityLevel.UNCERTAIN)
        assert fv.css_class == "quality-uncertain"

        fv = FieldValue(value="test", quality=FieldQualityLevel.DAMAGED)
        assert fv.css_class == "quality-damaged"


class TestFormPersonRow:
    """Tests for FormPersonRow dataclass."""

    def test_get_field_returns_value(self):
        """Test get_field returns field value as string."""
        person = FormPersonRow(
            fields={"full_name": FieldValue(value="John Smith")}
        )
        assert person.get_field("full_name") == "John Smith"

    def test_get_field_returns_default_when_missing(self):
        """Test get_field returns default for missing field."""
        person = FormPersonRow(fields={})
        assert person.get_field("full_name", "Unknown") == "Unknown"

    def test_get_field_returns_default_for_none_value(self):
        """Test get_field returns default when value is None."""
        person = FormPersonRow(
            fields={"full_name": FieldValue(value=None)}
        )
        assert person.get_field("full_name", "N/A") == "N/A"

    def test_get_field_value_returns_field_object(self):
        """Test get_field_value returns FieldValue object."""
        fv = FieldValue(value="John Smith", quality=FieldQualityLevel.VERIFIED)
        person = FormPersonRow(fields={"full_name": fv})
        assert person.get_field_value("full_name") is fv

    def test_get_field_value_returns_none_when_missing(self):
        """Test get_field_value returns None for missing field."""
        person = FormPersonRow(fields={})
        assert person.get_field_value("full_name") is None

    def test_has_field_true_when_present(self):
        """Test has_field returns True when field has value."""
        person = FormPersonRow(
            fields={"age": FieldValue(value=25)}
        )
        assert person.has_field("age")

    def test_has_field_false_when_missing(self):
        """Test has_field returns False when field missing."""
        person = FormPersonRow(fields={})
        assert not person.has_field("age")

    def test_has_field_false_when_empty_string(self):
        """Test has_field returns False when value is empty string."""
        person = FormPersonRow(
            fields={"occupation": FieldValue(value="")}
        )
        assert not person.has_field("occupation")

    def test_has_field_false_when_none(self):
        """Test has_field returns False when value is None."""
        person = FormPersonRow(
            fields={"occupation": FieldValue(value=None)}
        )
        assert not person.has_field("occupation")


class TestFormPageData:
    """Tests for FormPageData dataclass."""

    def test_location_display_full(self):
        """Test location display with all parts."""
        page = FormPageData(
            township_city="San Diego",
            county="San Diego",
            state="California"
        )
        assert page.location_display == "San Diego, San Diego County, California"

    def test_location_display_partial(self):
        """Test location display with missing parts."""
        page = FormPageData(county="Noble", state="Ohio")
        assert page.location_display == "Noble County, Ohio"

    def test_sheet_or_page_display_1950_stamp(self):
        """Test sheet/page display for 1950 with stamp."""
        page = FormPageData(census_year=1950, stamp_number="10")
        assert page.sheet_or_page_display == "Stamp 10"

    def test_sheet_or_page_display_1950_page(self):
        """Test sheet/page display for 1950 with page number."""
        page = FormPageData(census_year=1950, page_number="5")
        assert page.sheet_or_page_display == "Page 5"

    def test_sheet_or_page_display_1940_sheet(self):
        """Test sheet/page display for 1940."""
        page = FormPageData(
            census_year=1940,
            sheet_number="3",
            sheet_letter="A"
        )
        assert page.sheet_or_page_display == "Sheet 3A"

    def test_ed_display_1950(self):
        """Test ED display for 1950 census."""
        page = FormPageData(census_year=1950, enumeration_district="72-91")
        assert page.ed_display == "E.D. 72-91"

    def test_ed_display_pre1880(self):
        """Test ED display for pre-1880 census (no ED)."""
        page = FormPageData(census_year=1870, enumeration_district="")
        assert page.ed_display == ""


class TestFormHousehold:
    """Tests for FormHousehold dataclass."""

    def test_head_returns_head_of_household(self):
        """Test head property returns head of household."""
        head = FormPersonRow(is_head_of_household=True)
        wife = FormPersonRow(is_head_of_household=False)
        household = FormHousehold(persons=[wife, head])
        assert household.head is head

    def test_head_returns_first_person_when_no_head(self):
        """Test head returns first person when no one marked as head."""
        person1 = FormPersonRow()
        person2 = FormPersonRow()
        household = FormHousehold(persons=[person1, person2])
        assert household.head is person1

    def test_head_returns_none_when_empty(self):
        """Test head returns None when no persons."""
        household = FormHousehold(persons=[])
        assert household.head is None


class TestCensusFormContext:
    """Tests for CensusFormContext dataclass."""

    def test_primary_page_returns_first_page(self):
        """Test primary_page returns first page."""
        page1 = FormPageData(page_id=1)
        page2 = FormPageData(page_id=2)
        ctx = CensusFormContext(pages=[page1, page2])
        assert ctx.primary_page is page1

    def test_primary_page_returns_none_when_empty(self):
        """Test primary_page returns None when no pages."""
        ctx = CensusFormContext(pages=[])
        assert ctx.primary_page is None

    def test_all_persons_collects_from_all_pages(self):
        """Test all_persons collects persons from all pages."""
        person1 = FormPersonRow(person_id=1)
        person2 = FormPersonRow(person_id=2)
        page1 = FormPageData(persons=[person1])
        page2 = FormPageData(persons=[person2])
        ctx = CensusFormContext(pages=[page1, page2])
        assert len(ctx.all_persons) == 2
        assert person1 in ctx.all_persons
        assert person2 in ctx.all_persons

    def test_target_person_returns_target(self):
        """Test target_person returns the target person."""
        target = FormPersonRow(is_target=True)
        other = FormPersonRow(is_target=False)
        page = FormPageData(persons=[other, target])
        ctx = CensusFormContext(pages=[page])
        assert ctx.target_person is target

    def test_target_person_returns_none_when_no_target(self):
        """Test target_person returns None when no target."""
        person = FormPersonRow(is_target=False)
        page = FormPageData(persons=[person])
        ctx = CensusFormContext(pages=[page])
        assert ctx.target_person is None

    def test_get_sample_columns(self):
        """Test get_sample_columns filters correctly."""
        col1 = FormColumnDef(name="age", is_sample_only=False)
        col2 = FormColumnDef(name="income", is_sample_only=True)
        ctx = CensusFormContext(columns=[col1, col2])
        sample_cols = ctx.get_sample_columns()
        assert len(sample_cols) == 1
        assert col2 in sample_cols

    def test_get_main_columns(self):
        """Test get_main_columns filters correctly."""
        col1 = FormColumnDef(name="age", is_sample_only=False)
        col2 = FormColumnDef(name="income", is_sample_only=True)
        ctx = CensusFormContext(columns=[col1, col2])
        main_cols = ctx.get_main_columns()
        assert len(main_cols) == 1
        assert col1 in main_cols


class TestFormColumnDef:
    """Tests for FormColumnDef dataclass."""

    def test_header_display_with_column_number(self):
        """Test header display includes column number."""
        col = FormColumnDef(
            name="age",
            column_number="11",
            label="Age",
            short_label="AGE"
        )
        assert col.header_display == "11. AGE"

    def test_header_display_without_column_number(self):
        """Test header display without column number."""
        col = FormColumnDef(name="line", label="Line Number", short_label="LINE")
        assert col.header_display == "LINE"

    def test_header_display_uses_label_when_no_short(self):
        """Test header display uses label when no short_label."""
        col = FormColumnDef(name="age", column_number="11", label="Age")
        assert col.header_display == "11. Age"


class TestGetColumnsForYear:
    """Tests for get_columns_for_year function."""

    def test_1950_returns_columns(self):
        """Test 1950 returns column definitions."""
        columns = get_columns_for_year(1950)
        assert len(columns) > 0
        assert columns == COLUMNS_1950

    def test_1950_includes_sample_columns(self):
        """Test 1950 columns include sample-only columns."""
        columns = get_columns_for_year(1950)
        sample_cols = [c for c in columns if c.is_sample_only]
        assert len(sample_cols) > 0

    def test_1950_has_required_columns(self):
        """Test 1950 has required core columns."""
        columns = get_columns_for_year(1950)
        column_names = [c.name for c in columns]
        assert "full_name" in column_names
        assert "age" in column_names
        assert "sex" in column_names
        assert "birthplace" in column_names

    def test_unsupported_year_returns_empty(self):
        """Test unsupported year returns empty list."""
        columns = get_columns_for_year(1800)
        assert columns == []
