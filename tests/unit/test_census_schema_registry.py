"""Unit tests for CensusSchemaRegistry."""

import pytest

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


class TestCensusSchemaRegistry:
    """Tests for the CensusSchemaRegistry class."""

    def setup_method(self):
        """Clear cache before each test."""
        CensusSchemaRegistry.clear_cache()

    def test_list_years_returns_valid_census_years(self):
        """Test that list_years returns all valid census years."""
        years = CensusSchemaRegistry.list_years()

        assert 1790 in years
        assert 1950 in years
        assert 1890 not in years  # 1890 census destroyed by fire
        assert len(years) == 16  # 17 decades minus 1890

    def test_is_valid_year_returns_true_for_valid_years(self):
        """Test is_valid_year for valid census years."""
        assert CensusSchemaRegistry.is_valid_year(1790)
        assert CensusSchemaRegistry.is_valid_year(1850)
        assert CensusSchemaRegistry.is_valid_year(1940)
        assert CensusSchemaRegistry.is_valid_year(1950)

    def test_is_valid_year_returns_false_for_invalid_years(self):
        """Test is_valid_year for invalid years."""
        assert not CensusSchemaRegistry.is_valid_year(1890)  # Destroyed
        assert not CensusSchemaRegistry.is_valid_year(1791)  # Not a census year
        assert not CensusSchemaRegistry.is_valid_year(2000)  # After 1950
        assert not CensusSchemaRegistry.is_valid_year(1780)  # Before first census

    def test_get_schema_returns_census_year_schema(self):
        """Test that get_schema returns a CensusYearSchema."""
        schema = CensusSchemaRegistry.get_schema(1940)

        assert isinstance(schema, CensusYearSchema)
        assert schema.year == 1940

    def test_get_schema_raises_for_invalid_year(self):
        """Test that get_schema raises ValueError for invalid year."""
        with pytest.raises(ValueError, match="Invalid census year"):
            CensusSchemaRegistry.get_schema(1890)

    def test_get_schema_caches_result(self):
        """Test that schemas are cached after first load."""
        schema1 = CensusSchemaRegistry.get_schema(1940)
        schema2 = CensusSchemaRegistry.get_schema(1940)

        # Should be same object (cached)
        assert schema1 is schema2

    def test_clear_cache_removes_cached_schemas(self):
        """Test that clear_cache removes all cached schemas."""
        schema1 = CensusSchemaRegistry.get_schema(1940)
        CensusSchemaRegistry.clear_cache()
        schema2 = CensusSchemaRegistry.get_schema(1940)

        # Should be different objects after cache clear
        assert schema1 is not schema2

    def test_get_era_for_household_only_years(self):
        """Test era detection for 1790-1840."""
        for year in [1790, 1800, 1810, 1820, 1830, 1840]:
            era = CensusSchemaRegistry.get_era(year)
            assert era == CensusEra.HOUSEHOLD_ONLY

    def test_get_era_for_individual_no_ed_years(self):
        """Test era detection for 1850-1870."""
        for year in [1850, 1860, 1870]:
            era = CensusSchemaRegistry.get_era(year)
            assert era == CensusEra.INDIVIDUAL_NO_ED

    def test_get_era_for_individual_with_ed_sheet_years(self):
        """Test era detection for 1880-1940."""
        for year in [1880, 1900, 1910, 1920, 1930, 1940]:
            era = CensusSchemaRegistry.get_era(year)
            assert era == CensusEra.INDIVIDUAL_WITH_ED_SHEET

    def test_get_era_for_1950(self):
        """Test era detection for 1950."""
        era = CensusSchemaRegistry.get_era(1950)
        assert era == CensusEra.INDIVIDUAL_WITH_ED_PAGE

    def test_get_era_raises_for_invalid_year(self):
        """Test that get_era raises for invalid year."""
        with pytest.raises(ValueError, match="Invalid census year"):
            CensusSchemaRegistry.get_era(1890)


class TestSchemaContent:
    """Tests for loaded schema content."""

    def test_1940_schema_has_required_columns(self):
        """Test that 1940 schema has key columns."""
        schema = CensusSchemaRegistry.get_schema(1940)

        column_names = schema.get_column_names()
        assert "name" in column_names
        assert "age" in column_names
        assert "sex" in column_names
        assert "relationship" in column_names
        assert "enumeration_district" in column_names
        assert "sheet" in column_names
        assert "line_number" in column_names

    def test_1950_schema_uses_page_not_sheet(self):
        """Test that 1950 schema uses page numbers."""
        schema = CensusSchemaRegistry.get_schema(1950)

        assert schema.form_structure.uses_page is True
        assert schema.form_structure.uses_sheet is False
        assert schema.form_structure.uses_stamp is True

    def test_1850_schema_has_no_ed(self):
        """Test that 1850 schema doesn't have enumeration district."""
        schema = CensusSchemaRegistry.get_schema(1850)

        column_names = schema.get_column_names()
        # 1850 predates enumeration districts
        assert "page_number" in column_names  # Uses page
        assert schema.era == CensusEra.INDIVIDUAL_NO_ED

    def test_1790_schema_is_household_only(self):
        """Test that 1790 schema is household-only."""
        schema = CensusSchemaRegistry.get_schema(1790)

        assert schema.era == CensusEra.HOUSEHOLD_ONLY
        column_names = schema.get_column_names()
        assert "head_of_household" in column_names

    def test_schema_has_instructions(self):
        """Test that schemas have instructions."""
        schema = CensusSchemaRegistry.get_schema(1940)

        assert schema.instructions
        assert len(schema.instructions) > 100
        assert "1940" in schema.instructions

    def test_schema_has_abbreviations(self):
        """Test that schemas have abbreviations."""
        schema = CensusSchemaRegistry.get_schema(1940)

        assert schema.abbreviations
        assert "do" in schema.abbreviations
        assert schema.abbreviations["do"] == "same as above"
