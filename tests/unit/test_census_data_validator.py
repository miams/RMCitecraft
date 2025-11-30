"""Unit tests for CensusDataValidator."""

import pytest

from rmcitecraft.models.census_schema import CensusEra
from rmcitecraft.services.census.data_validator import CensusDataValidator
from rmcitecraft.services.census.schema_registry import CensusSchemaRegistry


class TestCensusDataValidator:
    """Tests for the CensusDataValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return CensusDataValidator()

    @pytest.fixture
    def schema_1940(self):
        """Get 1940 schema."""
        return CensusSchemaRegistry.get_schema(1940)

    @pytest.fixture
    def schema_1950(self):
        """Get 1950 schema."""
        return CensusSchemaRegistry.get_schema(1950)

    @pytest.fixture
    def schema_1850(self):
        """Get 1850 schema."""
        return CensusSchemaRegistry.get_schema(1850)

    @pytest.fixture
    def valid_1940_data(self):
        """Valid 1940 census data."""
        return {
            "metadata": {
                "enumeration_district": "93-76",
                "sheet": "9A",
            },
            "persons": [
                {
                    "name": "Smith, John",
                    "relationship": "Head",
                    "sex": "M",
                    "race": "W",
                    "age": 35,
                    "marital_status": "M",
                    "birthplace": "Ohio",
                    "line_number": 24,
                },
                {
                    "name": "Smith, Mary",
                    "relationship": "Wife",
                    "sex": "F",
                    "race": "W",
                    "age": 32,
                    "marital_status": "M",
                    "birthplace": "Indiana",
                    "line_number": 25,
                },
            ],
        }

    def test_valid_data_returns_no_warnings(self, validator, schema_1940, valid_1940_data):
        """Test that valid data returns no warnings."""
        warnings = validator.validate(valid_1940_data, schema_1940)

        # May have some warnings for optional fields, but check no critical ones
        critical_warnings = [w for w in warnings if "required" in w.lower()]
        assert len(critical_warnings) == 0

    def test_missing_ed_for_1940_warns(self, validator, schema_1940):
        """Test that missing ED for 1940 produces warning."""
        data = {
            "metadata": {"sheet": "9A"},  # Missing enumeration_district
            "persons": [{"name": "John Smith", "age": 35}],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("enumeration_district" in w for w in warnings)

    def test_missing_sheet_for_1940_warns(self, validator, schema_1940):
        """Test that missing sheet for 1940 produces warning."""
        data = {
            "metadata": {"enumeration_district": "93-76"},  # Missing sheet
            "persons": [{"name": "John Smith", "age": 35}],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("sheet" in w for w in warnings)

    def test_missing_page_for_1950_warns(self, validator, schema_1950):
        """Test that missing page for 1950 produces warning."""
        data = {
            "metadata": {"enumeration_district": "22-27"},  # Missing page_number
            "persons": [{"name": "John Smith", "age": 35}],
        }

        warnings = validator.validate(data, schema_1950)

        assert any("page" in w.lower() for w in warnings)

    def test_negative_age_warns(self, validator, schema_1940):
        """Test that negative age produces warning."""
        data = {
            "metadata": {"enumeration_district": "93-76", "sheet": "9A"},
            "persons": [{"name": "John Smith", "age": -5}],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("negative" in w.lower() or "age" in w.lower() for w in warnings)

    def test_unusually_high_age_warns(self, validator, schema_1940):
        """Test that age over 120 produces warning."""
        data = {
            "metadata": {"enumeration_district": "93-76", "sheet": "9A"},
            "persons": [{"name": "John Smith", "age": 150}],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("age" in w.lower() and "150" in w for w in warnings)

    def test_invalid_sex_value_warns(self, validator, schema_1940):
        """Test that invalid sex value produces warning."""
        data = {
            "metadata": {"enumeration_district": "93-76", "sheet": "9A"},
            "persons": [{"name": "John Smith", "age": 35, "sex": "X"}],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("sex" in w.lower() and "X" in w for w in warnings)

    def test_empty_persons_warns(self, validator, schema_1940):
        """Test that empty persons list produces warning for individual census."""
        data = {
            "metadata": {"enumeration_district": "93-76", "sheet": "9A"},
            "persons": [],
        }

        warnings = validator.validate(data, schema_1940)

        assert any("no persons" in w.lower() for w in warnings)


class TestHouseholdValidation:
    """Tests for household-level validation."""

    @pytest.fixture
    def validator(self):
        return CensusDataValidator()

    @pytest.fixture
    def schema_1940(self):
        return CensusSchemaRegistry.get_schema(1940)

    def test_validate_household_first_person_not_head(self, validator, schema_1940):
        """Test warning when first person is not head."""
        persons = [
            {"name": "Mary Smith", "relationship": "Wife", "line_number": 24},
            {"name": "John Smith", "relationship": "Head", "line_number": 25},
        ]

        warnings = validator.validate_household(persons, schema_1940)

        assert any("not head" in w.lower() for w in warnings)

    def test_validate_household_first_person_is_head(self, validator, schema_1940):
        """Test no warning when first person is head."""
        persons = [
            {"name": "John Smith", "relationship": "Head", "line_number": 24},
            {"name": "Mary Smith", "relationship": "Wife", "line_number": 25},
        ]

        warnings = validator.validate_household(persons, schema_1940)

        head_warnings = [w for w in warnings if "head" in w.lower()]
        assert len(head_warnings) == 0

    def test_validate_household_duplicate_line_numbers(self, validator, schema_1940):
        """Test warning for duplicate line numbers."""
        persons = [
            {"name": "John Smith", "relationship": "Head", "line_number": 24},
            {"name": "Mary Smith", "relationship": "Wife", "line_number": 24},  # Duplicate
        ]

        warnings = validator.validate_household(persons, schema_1940)

        assert any("duplicate" in w.lower() for w in warnings)

    def test_validate_household_non_consecutive_lines(self, validator, schema_1940):
        """Test warning for non-consecutive line numbers."""
        persons = [
            {"name": "John Smith", "line_number": 24},
            {"name": "Mary Smith", "line_number": 26},  # Gap (missing 25)
        ]

        warnings = validator.validate_household(persons, schema_1940)

        assert any("consecutive" in w.lower() for w in warnings)

    def test_validate_household_empty(self, validator, schema_1940):
        """Test warning for empty household."""
        warnings = validator.validate_household([], schema_1940)

        assert any("empty" in w.lower() for w in warnings)


class TestEraSpecificValidation:
    """Tests for era-specific validation rules."""

    @pytest.fixture
    def validator(self):
        return CensusDataValidator()

    def test_1850_no_ed_allowed(self, validator):
        """Test that ED in 1850 data is flagged (shouldn't exist)."""
        schema = CensusSchemaRegistry.get_schema(1850)
        data = {
            "metadata": {},
            "persons": [{"name": "John Smith", "enumeration_district": "123"}],
        }

        warnings = validator.validate(data, schema)

        # Should warn about ED in pre-ED census
        assert any("enumeration" in w.lower() for w in warnings)
