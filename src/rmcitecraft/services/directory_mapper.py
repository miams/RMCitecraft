"""
Directory mapper for census images.

Maps census images to appropriate directories based on year and schedule type,
following RootsMagic's file organization conventions.
"""

from pathlib import Path

from loguru import logger


class DirectoryMapper:
    """
    Maps census images to appropriate directories.

    Directory structure:
        Records - Census/
        ├── 1790 Federal/
        ├── 1800 Federal/
        ├── ...
        ├── 1950 Federal/
        ├── 1850 Federal Slave Schedule/
        ├── 1860 Federal Slave Schedule/
        ├── 1890 Federal Veterans and Widows Schedule/
        └── Federal Mortality Schedule 1850-1885/
            ├── 1850 Mortality/
            ├── 1860 Mortality/
            ├── 1870 Mortality/
            └── 1880 Mortality/
    """

    BASE_DIR = "Records - Census"

    # Valid census years (federal decennial census)
    VALID_CENSUS_YEARS = list(range(1790, 1960, 10))

    # Special schedule types and their valid years
    SLAVE_SCHEDULE_YEARS = [1850, 1860]
    MORTALITY_SCHEDULE_YEARS = [1850, 1860, 1870, 1880]
    VETERANS_SCHEDULE_YEARS = [1890]

    def __init__(self, media_root: Path | str):
        """
        Initialize directory mapper.

        Args:
            media_root: Root directory for RootsMagic media files
                       (from .env: RM_MEDIA_ROOT_DIRECTORY)
        """
        self.media_root = Path(media_root)
        logger.debug(f"DirectoryMapper initialized with media_root: {self.media_root}")

    def get_directory(self, year: int, schedule_type: str = "population") -> tuple[Path, str]:
        """
        Get full directory path and relative path for census image.

        Args:
            year: Census year (1790-1950)
            schedule_type: Type of schedule (population, slave, mortality, veterans)

        Returns:
            Tuple of (absolute_path, relative_path)
            - absolute_path: Full filesystem path
            - relative_path: Path relative to media_root (for RootsMagic MediaPath)

        Raises:
            ValueError: If year or schedule type is invalid

        Examples:
            >>> mapper = DirectoryMapper("/path/to/media")
            >>> abs_path, rel_path = mapper.get_directory(1930, "population")
            >>> str(abs_path)
            '/path/to/media/Records - Census/1930 Federal'
            >>> rel_path
            'Records - Census/1930 Federal'
        """
        self._validate_year(year)
        self._validate_schedule_type(year, schedule_type)

        # Get relative path based on schedule type
        if schedule_type == "slave":
            rel_path = f"{self.BASE_DIR}/{year} Federal Slave Schedule"
        elif schedule_type == "mortality":
            rel_path = f"{self.BASE_DIR}/Federal Mortality Schedule 1850-1885/{year} Mortality"
        elif schedule_type == "veterans":
            rel_path = f"{self.BASE_DIR}/{year} Federal Veterans and Widows Schedule"
        else:  # population (default)
            rel_path = f"{self.BASE_DIR}/{year} Federal"

        # Build absolute path
        abs_path = self.media_root / rel_path

        return abs_path, rel_path

    def ensure_directory_exists(self, year: int, schedule_type: str = "population") -> Path:
        """
        Ensure directory exists, creating it if necessary.

        Args:
            year: Census year
            schedule_type: Type of schedule

        Returns:
            Absolute path to directory (guaranteed to exist)

        Raises:
            ValueError: If year or schedule type is invalid
            OSError: If directory cannot be created
        """
        abs_path, rel_path = self.get_directory(year, schedule_type)

        if not abs_path.exists():
            logger.info(f"Creating directory: {abs_path}")
            abs_path.mkdir(parents=True, exist_ok=True)

        return abs_path

    def get_relative_path(self, year: int, schedule_type: str = "population") -> str:
        """
        Get relative path for RootsMagic MediaPath field.

        Args:
            year: Census year
            schedule_type: Type of schedule

        Returns:
            Relative path from media root

        Example:
            >>> mapper = DirectoryMapper("/path/to/media")
            >>> mapper.get_relative_path(1930, "population")
            'Records - Census/1930 Federal'
        """
        _, rel_path = self.get_directory(year, schedule_type)
        return rel_path

    def get_symbolic_path(self, year: int, schedule_type: str = "population") -> str:
        """
        Get symbolic path for RootsMagic MediaPath field.

        RootsMagic uses '?' to represent the configured media root directory.

        Args:
            year: Census year
            schedule_type: Type of schedule

        Returns:
            Symbolic path using '?' prefix

        Example:
            >>> mapper = DirectoryMapper("/path/to/media")
            >>> mapper.get_symbolic_path(1930, "population")
            '?/Records - Census/1930 Federal'
        """
        rel_path = self.get_relative_path(year, schedule_type)
        return f"?/{rel_path}"

    def _validate_year(self, year: int) -> None:
        """
        Validate census year.

        Args:
            year: Census year to validate

        Raises:
            ValueError: If year is not a valid census year
        """
        if year not in self.VALID_CENSUS_YEARS:
            raise ValueError(
                f"Invalid census year: {year}. Must be in range 1790-1950 (decennial years)"
            )

    def _validate_schedule_type(self, year: int, schedule_type: str) -> None:
        """
        Validate schedule type for given year.

        Args:
            year: Census year
            schedule_type: Schedule type

        Raises:
            ValueError: If schedule type is invalid or not available for year
        """
        valid_types = ["population", "slave", "mortality", "veterans"]

        if schedule_type not in valid_types:
            raise ValueError(
                f"Invalid schedule type: {schedule_type}. Must be one of: {', '.join(valid_types)}"
            )

        # Check year-specific restrictions
        if schedule_type == "slave" and year not in self.SLAVE_SCHEDULE_YEARS:
            raise ValueError(
                f"Slave schedules only available for years: {self.SLAVE_SCHEDULE_YEARS}"
            )

        if schedule_type == "mortality" and year not in self.MORTALITY_SCHEDULE_YEARS:
            raise ValueError(
                f"Mortality schedules only available for years: {self.MORTALITY_SCHEDULE_YEARS}"
            )

        if schedule_type == "veterans" and year not in self.VETERANS_SCHEDULE_YEARS:
            raise ValueError(
                f"Veterans schedules only available for year: {self.VETERANS_SCHEDULE_YEARS}"
            )

    def list_all_directories(self) -> list[tuple[int, str, Path]]:
        """
        List all census directories.

        Returns:
            List of tuples (year, schedule_type, absolute_path)

        Example:
            >>> mapper = DirectoryMapper("/path/to/media")
            >>> dirs = mapper.list_all_directories()
            >>> len(dirs)
            166  # 1790-1950 population + special schedules
        """
        directories = []

        # Population schedules (all years)
        for year in self.VALID_CENSUS_YEARS:
            abs_path, _ = self.get_directory(year, "population")
            directories.append((year, "population", abs_path))

        # Slave schedules
        for year in self.SLAVE_SCHEDULE_YEARS:
            abs_path, _ = self.get_directory(year, "slave")
            directories.append((year, "slave", abs_path))

        # Mortality schedules
        for year in self.MORTALITY_SCHEDULE_YEARS:
            abs_path, _ = self.get_directory(year, "mortality")
            directories.append((year, "mortality", abs_path))

        # Veterans schedule
        for year in self.VETERANS_SCHEDULE_YEARS:
            abs_path, _ = self.get_directory(year, "veterans")
            directories.append((year, "veterans", abs_path))

        return directories

    def create_all_directories(self) -> int:
        """
        Create all census directories if they don't exist.

        Useful for initial setup or ensuring complete directory structure.

        Returns:
            Number of directories created

        Example:
            >>> mapper = DirectoryMapper("/path/to/media")
            >>> created = mapper.create_all_directories()
            >>> print(f"Created {created} directories")
        """
        created = 0

        for _year, _schedule_type, abs_path in self.list_all_directories():
            if not abs_path.exists():
                logger.info(f"Creating: {abs_path}")
                abs_path.mkdir(parents=True, exist_ok=True)
                created += 1

        logger.info(f"Created {created} census directories")
        return created
