"""Unit tests for census year schema files (YAML validation)."""

import pytest

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


class TestAllSchemasLoad:
    """Test that all schema YAML files load correctly."""

    @pytest.mark.parametrize(
        "year",
        [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950],
    )
    def test_schema_loads_successfully(self, year):
        """Test that schema loads without error."""
        CensusSchemaRegistry.clear_cache()
        schema = CensusSchemaRegistry.get_schema(year)

        assert isinstance(schema, CensusYearSchema)
        assert schema.year == year

    @pytest.mark.parametrize(
        "year",
        [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950],
    )
    def test_schema_has_columns(self, year):
        """Test that schema has at least one column."""
        schema = CensusSchemaRegistry.get_schema(year)

        assert len(schema.columns) > 0

    @pytest.mark.parametrize(
        "year",
        [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950],
    )
    def test_schema_has_era(self, year):
        """Test that schema has a valid era."""
        schema = CensusSchemaRegistry.get_schema(year)

        assert isinstance(schema.era, CensusEra)


class TestSchemaEraConsistency:
    """Test that schemas have correct eras."""

    @pytest.mark.parametrize("year", [1790, 1800, 1810, 1820, 1830, 1840])
    def test_household_only_era(self, year):
        """Test that 1790-1840 censuses are household-only."""
        schema = CensusSchemaRegistry.get_schema(year)
        assert schema.era == CensusEra.HOUSEHOLD_ONLY

    @pytest.mark.parametrize("year", [1850, 1860, 1870])
    def test_individual_no_ed_era(self, year):
        """Test that 1850-1870 censuses are individual without ED."""
        schema = CensusSchemaRegistry.get_schema(year)
        assert schema.era == CensusEra.INDIVIDUAL_NO_ED

    @pytest.mark.parametrize("year", [1880, 1900, 1910, 1920, 1930, 1940])
    def test_individual_with_ed_sheet_era(self, year):
        """Test that 1880-1940 censuses use ED and sheet."""
        schema = CensusSchemaRegistry.get_schema(year)
        assert schema.era == CensusEra.INDIVIDUAL_WITH_ED_SHEET

    def test_1950_era(self):
        """Test that 1950 census uses ED and page."""
        schema = CensusSchemaRegistry.get_schema(1950)
        assert schema.era == CensusEra.INDIVIDUAL_WITH_ED_PAGE


class TestSchemaRequiredFields:
    """Test that schemas have appropriate required fields."""

    @pytest.mark.parametrize("year", [1790, 1800, 1810, 1820, 1830, 1840])
    def test_household_census_has_head_field(self, year):
        """Test that household-only censuses have head_of_household field."""
        schema = CensusSchemaRegistry.get_schema(year)
        column_names = schema.get_column_names()

        assert "head_of_household" in column_names

    @pytest.mark.parametrize("year", [1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950])
    def test_individual_census_has_name_field(self, year):
        """Test that individual censuses have name field."""
        schema = CensusSchemaRegistry.get_schema(year)
        column_names = schema.get_column_names()

        assert "name" in column_names

    @pytest.mark.parametrize("year", [1880, 1900, 1910, 1920, 1930, 1940, 1950])
    def test_ed_census_has_enumeration_district(self, year):
        """Test that ED-era censuses have enumeration_district field."""
        schema = CensusSchemaRegistry.get_schema(year)
        column_names = schema.get_column_names()

        assert "enumeration_district" in column_names


class TestSchemaFormStructure:
    """Test form structure metadata."""

    @pytest.mark.parametrize("year", [1880, 1900, 1910, 1920, 1930, 1940])
    def test_sheet_census_form_structure(self, year):
        """Test that sheet-based censuses have correct form structure."""
        schema = CensusSchemaRegistry.get_schema(year)

        assert schema.form_structure.uses_sheet is True
        assert schema.form_structure.uses_page is False

    @pytest.mark.parametrize("year", [1850, 1860, 1870])
    def test_page_census_form_structure(self, year):
        """Test that page-based censuses have correct form structure."""
        schema = CensusSchemaRegistry.get_schema(year)

        assert schema.form_structure.uses_page is True
        assert schema.form_structure.uses_sheet is False

    def test_1950_uses_stamp(self):
        """Test that 1950 census uses stamp in citations."""
        schema = CensusSchemaRegistry.get_schema(1950)

        assert schema.form_structure.uses_stamp is True


class TestSchemaInstructions:
    """Test that schemas have meaningful instructions."""

    @pytest.mark.parametrize(
        "year",
        [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950],
    )
    def test_schema_has_instructions(self, year):
        """Test that schema has non-empty instructions."""
        schema = CensusSchemaRegistry.get_schema(year)

        assert schema.instructions
        assert len(schema.instructions) > 50

    def test_1940_has_detailed_instructions(self):
        """Test that 1940 has detailed column-by-column instructions."""
        schema = CensusSchemaRegistry.get_schema(1940)

        # 1940 should have very detailed instructions
        assert len(schema.instructions) > 500
        assert "column" in schema.instructions.lower() or "col" in schema.instructions.lower()


class TestSchemaAbbreviations:
    """Test abbreviation definitions."""

    @pytest.mark.parametrize("year", [1900, 1910, 1920, 1930, 1940, 1950])
    def test_modern_census_has_ditto(self, year):
        """Test that modern censuses have ditto mark abbreviation."""
        schema = CensusSchemaRegistry.get_schema(year)

        # Should have ditto/do abbreviation
        assert "do" in schema.abbreviations or '"' in schema.abbreviations


class TestSchemaNoDuplicateColumns:
    """Test that schemas don't have duplicate column names."""

    @pytest.mark.parametrize(
        "year",
        [1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950],
    )
    def test_no_duplicate_column_names(self, year):
        """Test that schema has no duplicate column names."""
        schema = CensusSchemaRegistry.get_schema(year)

        column_names = schema.get_column_names()
        unique_names = set(column_names)

        assert len(column_names) == len(unique_names), f"Duplicate columns in {year}: {column_names}"
