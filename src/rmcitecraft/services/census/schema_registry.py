"""Census schema registry for loading and caching YAML schemas.

This module provides centralized access to census year schemas, loading them
from YAML files on demand and caching for performance.
"""

from pathlib import Path
from typing import ClassVar

import yaml
from loguru import logger

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema


class CensusSchemaRegistry:
    """Registry for loading and caching census year schemas from YAML files.

    Schemas are loaded lazily on first access and cached for subsequent requests.
    The registry supports all US Federal Census years from 1790 to 1950.

    Example:
        schema = CensusSchemaRegistry.get_schema(1940)
        era = CensusSchemaRegistry.get_era(1920)
        years = CensusSchemaRegistry.list_years()
    """

    # Valid census years (every 10 years from 1790 to 1950, excluding 1890)
    CENSUS_YEARS: ClassVar[list[int]] = [
        1790, 1800, 1810, 1820, 1830, 1840,
        1850, 1860, 1870, 1880,
        # 1890 - most records destroyed by fire
        1900, 1910, 1920, 1930, 1940, 1950
    ]

    # Schema cache
    _schemas: ClassVar[dict[int, CensusYearSchema]] = {}

    # Path to schema YAML files
    _schema_dir: ClassVar[Path | None] = None

    @classmethod
    def _get_schema_dir(cls) -> Path:
        """Get the directory containing schema YAML files."""
        if cls._schema_dir is None:
            # Default to schemas/census/ relative to this file's package
            cls._schema_dir = Path(__file__).parent.parent.parent / "schemas" / "census"
        return cls._schema_dir

    @classmethod
    def set_schema_dir(cls, path: Path | str) -> None:
        """Set custom schema directory (mainly for testing).

        Args:
            path: Path to directory containing census YAML files
        """
        cls._schema_dir = Path(path)
        cls._schemas.clear()  # Clear cache when directory changes

    @classmethod
    def get_schema(cls, year: int) -> CensusYearSchema:
        """Get schema for a census year, loading from YAML if needed.

        Args:
            year: Census year (1790-1950, excluding 1890)

        Returns:
            CensusYearSchema for the requested year

        Raises:
            ValueError: If year is not a valid census year
            FileNotFoundError: If schema file doesn't exist
        """
        if year not in cls.CENSUS_YEARS:
            raise ValueError(
                f"Invalid census year: {year}. "
                f"Valid years are: {cls.CENSUS_YEARS}"
            )

        if year not in cls._schemas:
            cls._schemas[year] = cls._load_schema(year)

        return cls._schemas[year]

    @classmethod
    def _load_schema(cls, year: int) -> CensusYearSchema:
        """Load schema from YAML file.

        Args:
            year: Census year

        Returns:
            Loaded CensusYearSchema

        Raises:
            FileNotFoundError: If schema file doesn't exist
        """
        schema_file = cls._get_schema_dir() / f"{year}.yaml"

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        logger.debug(f"Loading census schema from {schema_file}")

        with open(schema_file, "r") as f:
            data = yaml.safe_load(f)

        return CensusYearSchema.from_dict(data)

    @classmethod
    def get_era(cls, year: int) -> CensusEra:
        """Get the census era for a year.

        This method determines the era without loading the full schema,
        based on the well-known era boundaries.

        Args:
            year: Census year

        Returns:
            CensusEra for the year

        Raises:
            ValueError: If year is not a valid census year
        """
        if year not in cls.CENSUS_YEARS:
            raise ValueError(f"Invalid census year: {year}")

        if year <= 1840:
            return CensusEra.HOUSEHOLD_ONLY
        elif year <= 1870:
            return CensusEra.INDIVIDUAL_NO_ED
        elif year <= 1940:
            return CensusEra.INDIVIDUAL_WITH_ED_SHEET
        else:  # 1950
            return CensusEra.INDIVIDUAL_WITH_ED_PAGE

    @classmethod
    def list_years(cls) -> list[int]:
        """List all available census years.

        Returns:
            List of valid census years
        """
        return cls.CENSUS_YEARS.copy()

    @classmethod
    def is_valid_year(cls, year: int) -> bool:
        """Check if a year is a valid census year.

        Args:
            year: Year to check

        Returns:
            True if year is a valid census year
        """
        return year in cls.CENSUS_YEARS

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the schema cache (mainly for testing)."""
        cls._schemas.clear()

    @classmethod
    def preload_all(cls) -> None:
        """Preload all schemas into cache.

        Useful for startup or when you know you'll need multiple schemas.
        """
        for year in cls.CENSUS_YEARS:
            try:
                cls.get_schema(year)
            except FileNotFoundError:
                logger.warning(f"Schema file not found for year {year}")
