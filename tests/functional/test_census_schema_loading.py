"""Functional tests for census schema loading.

These tests verify that all YAML schema files are valid and loadable.
"""

import pytest

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


class TestAllSchemasLoadAndValidate:
    """Functional tests for loading all census schemas."""

    CENSUS_YEARS = [
        1790, 1800, 1810, 1820, 1830, 1840,
        1850, 1860, 1870, 1880,
        1900, 1910, 1920, 1930, 1940, 1950
    ]

    def setup_method(self):
        """Clear cache before each test."""
        CensusSchemaRegistry.clear_cache()

    def test_all_schemas_load_successfully(self):
        """Test that all 16 schema files load without error."""
        loaded_count = 0

        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)
            assert isinstance(schema, CensusYearSchema)
            assert schema.year == year
            loaded_count += 1

        assert loaded_count == 16

    def test_all_schemas_have_valid_structure(self):
        """Test that all schemas have required structure."""
        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)

            # Must have columns
            assert len(schema.columns) > 0, f"Year {year} has no columns"

            # Must have era
            assert isinstance(schema.era, CensusEra), f"Year {year} has invalid era"

            # Must have instructions
            assert schema.instructions, f"Year {year} has no instructions"

            # Must have form_structure
            assert schema.form_structure is not None, f"Year {year} has no form_structure"

    def test_era_assignment_is_correct(self):
        """Test that eras are assigned correctly to years."""
        era_mapping = {
            CensusEra.HOUSEHOLD_ONLY: [1790, 1800, 1810, 1820, 1830, 1840],
            CensusEra.INDIVIDUAL_NO_ED: [1850, 1860, 1870],
            CensusEra.INDIVIDUAL_WITH_ED_SHEET: [1880, 1900, 1910, 1920, 1930, 1940],
            CensusEra.INDIVIDUAL_WITH_ED_PAGE: [1950],
        }

        for expected_era, years in era_mapping.items():
            for year in years:
                schema = CensusSchemaRegistry.get_schema(year)
                assert schema.era == expected_era, (
                    f"Year {year} has era {schema.era}, expected {expected_era}"
                )

    def test_column_names_are_valid_identifiers(self):
        """Test that column names are valid Python identifiers."""
        import keyword

        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)

            for col in schema.columns:
                # Should be valid identifier
                assert col.name.isidentifier(), (
                    f"Year {year}: '{col.name}' is not a valid identifier"
                )

                # Should not be Python keyword
                assert not keyword.iskeyword(col.name), (
                    f"Year {year}: '{col.name}' is a Python keyword"
                )

    def test_no_empty_descriptions(self):
        """Test that all columns have descriptions."""
        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)

            for col in schema.columns:
                assert col.description, (
                    f"Year {year}: column '{col.name}' has no description"
                )

    def test_data_types_are_valid(self):
        """Test that column data_types are valid."""
        valid_types = {"string", "integer", "boolean"}

        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)

            for col in schema.columns:
                assert col.data_type in valid_types, (
                    f"Year {year}: column '{col.name}' has invalid data_type '{col.data_type}'"
                )

    def test_form_structure_consistency(self):
        """Test that form structure is consistent with era."""
        for year in self.CENSUS_YEARS:
            schema = CensusSchemaRegistry.get_schema(year)
            fs = schema.form_structure

            # Sheet-based censuses (1880-1940)
            if schema.era == CensusEra.INDIVIDUAL_WITH_ED_SHEET:
                assert fs.uses_sheet is True, f"Year {year} should use sheets"
                assert fs.uses_page is False, f"Year {year} should not use pages"

            # Page-based censuses (1850-1870)
            elif schema.era == CensusEra.INDIVIDUAL_NO_ED:
                assert fs.uses_page is True, f"Year {year} should use pages"
                assert fs.uses_sheet is False, f"Year {year} should not use sheets"

            # 1950 uses page (stamp)
            elif schema.era == CensusEra.INDIVIDUAL_WITH_ED_PAGE:
                assert fs.uses_page is True, f"Year 1950 should use pages"
                assert fs.uses_stamp is True, f"Year 1950 should use stamp"

    def test_nara_publication_numbers(self):
        """Test that appropriate years have NARA publication numbers."""
        # Years with known NARA microfilm publications
        nara_years = {
            1790: "M637",
            1800: "M32",
            1810: "M252",
            1820: "M33",
            1830: "M19",
            1840: "M704",
            1850: "M432",
            1860: "M653",
            1870: "M593",
            1880: "T9",
            1900: "T623",
            1910: "T624",
            1920: "T625",
            1930: "T626",
        }

        for year, expected_pub in nara_years.items():
            schema = CensusSchemaRegistry.get_schema(year)
            if schema.nara_publication:
                assert schema.nara_publication == expected_pub, (
                    f"Year {year}: expected NARA {expected_pub}, got {schema.nara_publication}"
                )


class TestSchemaJSONConversion:
    """Test schema to JSON schema conversion."""

    def test_to_json_schema_returns_dict(self):
        """Test that to_json_schema returns a dictionary."""
        schema = CensusSchemaRegistry.get_schema(1940)
        json_schema = schema.to_json_schema()

        assert isinstance(json_schema, dict)
        assert len(json_schema) > 0

    def test_to_json_schema_contains_all_columns(self):
        """Test that JSON schema contains all column names."""
        schema = CensusSchemaRegistry.get_schema(1940)
        json_schema = schema.to_json_schema()

        for col in schema.columns:
            assert col.name in json_schema


class TestSchemaCachingBehavior:
    """Test schema caching behavior."""

    def test_preload_all_populates_cache(self):
        """Test that preload_all loads all schemas."""
        CensusSchemaRegistry.clear_cache()
        CensusSchemaRegistry.preload_all()

        # All schemas should now be cached
        for year in CensusSchemaRegistry.list_years():
            # This should not hit disk
            schema = CensusSchemaRegistry.get_schema(year)
            assert schema is not None
