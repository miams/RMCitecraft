"""
Filename generator for census images.

Generates standardized filenames following the RMCitecraft convention:
YYYY, State, County - Surname, GivenName.ext
"""

import re
from pathlib import Path

from loguru import logger


class FilenameGenerator:
    """
    Generates standardized filenames for census images.

    Handles:
    - Character sanitization (illegal filename characters)
    - Length limits (255 chars for most filesystems)
    - Multi-part surnames (preserve hyphens, spaces)
    - Name suffixes (Jr., Sr., III)
    - File extension preservation
    """

    # Characters illegal in filenames on macOS/Windows
    ILLEGAL_CHARS = r'[/\\:*?"<>|]'

    # Maximum filename length (conservative for cross-platform)
    MAX_FILENAME_LENGTH = 255

    def generate_filename(
        self,
        year: int,
        state: str,
        county: str,
        surname: str,
        given_name: str,
        extension: str = "jpg",
    ) -> str:
        """
        Generate standardized census image filename.

        Args:
            year: Census year (1790-1950)
            state: State name
            county: County name
            surname: Person's surname
            given_name: Person's given name
            extension: File extension (without dot)

        Returns:
            Standardized filename

        Example:
            >>> gen = FilenameGenerator()
            >>> gen.generate_filename(
            ...     1930, "Oklahoma", "Tulsa", "Iams", "Jesse Dorsey"
            ... )
            '1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg'
        """
        # Sanitize all components
        state_clean = self._sanitize(state)
        county_clean = self._sanitize(county)
        surname_clean = self._sanitize(surname)
        given_clean = self._sanitize(given_name)

        # Ensure extension doesn't have leading dot
        ext_clean = extension.lstrip(".")

        # Build filename
        filename = (
            f"{year}, {state_clean}, {county_clean} - {surname_clean}, {given_clean}.{ext_clean}"
        )

        # Check length and truncate if needed
        if len(filename) > self.MAX_FILENAME_LENGTH:
            filename = self._truncate_filename(
                year, state_clean, county_clean, surname_clean, given_clean, ext_clean
            )
            logger.warning(f"Filename truncated to {self.MAX_FILENAME_LENGTH} chars: {filename}")

        return filename

    def _sanitize(self, text: str) -> str:
        """
        Remove illegal filename characters while preserving readability.

        Args:
            text: Raw text

        Returns:
            Sanitized text safe for filenames

        Examples:
            >>> gen = FilenameGenerator()
            >>> gen._sanitize("Greene/Washington")
            'Greene-Washington'
            >>> gen._sanitize('Name "with" quotes')
            'Name with quotes'
        """
        # Replace illegal characters with safe alternatives
        sanitized = re.sub(self.ILLEGAL_CHARS, "-", text)

        # Remove any double spaces created by replacements
        sanitized = re.sub(r"\s+", " ", sanitized)

        # Trim leading/trailing spaces and hyphens
        sanitized = sanitized.strip(" -")

        return sanitized

    def _truncate_filename(
        self,
        year: int,
        state: str,
        county: str,
        surname: str,
        given_name: str,
        extension: str,
    ) -> str:
        """
        Truncate filename to fit within length limits.

        Strategy:
        1. Shorten given name first (most variable part)
        2. Shorten county if needed
        3. Use initials if still too long

        Args:
            year: Census year
            state: State name (sanitized)
            county: County name (sanitized)
            surname: Surname (sanitized)
            given_name: Given name (sanitized)
            extension: File extension

        Returns:
            Truncated filename within length limits
        """
        # Fixed parts that don't change
        fixed = f"{year}, {state}, {county} - {surname}, .{extension}"
        fixed_len = len(fixed)

        # Available space for given name
        available = self.MAX_FILENAME_LENGTH - fixed_len

        if available >= len(given_name):
            # Should not happen, but handle gracefully
            return f"{year}, {state}, {county} - {surname}, {given_name}.{extension}"

        if available >= 10:
            # Truncate given name to fit
            truncated_given = given_name[: available - 3] + "..."
            return f"{year}, {state}, {county} - {surname}, {truncated_given}.{extension}"

        # Extreme case: use initials only
        initials = self._get_initials(given_name)
        return f"{year}, {state}, {county} - {surname}, {initials}.{extension}"

    def _get_initials(self, name: str) -> str:
        """
        Extract initials from a name.

        Args:
            name: Full name

        Returns:
            Initials with periods

        Examples:
            >>> gen = FilenameGenerator()
            >>> gen._get_initials("Jesse Dorsey")
            'J.D.'
            >>> gen._get_initials("William H")
            'W.H.'
        """
        parts = name.split()
        initials = "".join(part[0].upper() + "." for part in parts if part)
        return initials

    def extract_extension(self, filepath: Path | str) -> str:
        """
        Extract file extension from a path.

        Args:
            filepath: Path to file

        Returns:
            Extension without leading dot (lowercase)

        Examples:
            >>> gen = FilenameGenerator()
            >>> gen.extract_extension("image.JPG")
            'jpg'
            >>> gen.extract_extension(Path("/path/to/file.png"))
            'png'
        """
        path = Path(filepath)
        ext = path.suffix.lstrip(".").lower()
        return ext if ext else "jpg"  # Default to jpg

    def parse_filename(self, filename: str) -> dict[str, str] | None:
        """
        Parse a standardized filename back into components.

        Args:
            filename: Filename to parse

        Returns:
            Dictionary with components or None if format doesn't match

        Example:
            >>> gen = FilenameGenerator()
            >>> gen.parse_filename("1930, Oklahoma, Tulsa - Iams, Jesse.jpg")
            {
                'year': '1930',
                'state': 'Oklahoma',
                'county': 'Tulsa',
                'surname': 'Iams',
                'given_name': 'Jesse',
                'extension': 'jpg'
            }
        """
        # Pattern: YYYY, State, County - Surname, GivenName.ext
        pattern = r"^(\d{4}),\s*([^,]+),\s*([^-]+)\s*-\s*([^,]+),\s*([^.]+)\.(\w+)$"
        match = re.match(pattern, filename)

        if not match:
            return None

        return {
            "year": match.group(1).strip(),
            "state": match.group(2).strip(),
            "county": match.group(3).strip(),
            "surname": match.group(4).strip(),
            "given_name": match.group(5).strip(),
            "extension": match.group(6).strip(),
        }

    def is_standardized_filename(self, filename: str) -> bool:
        """
        Check if filename follows standardized format.

        Args:
            filename: Filename to check

        Returns:
            True if filename matches standard format
        """
        return self.parse_filename(filename) is not None
