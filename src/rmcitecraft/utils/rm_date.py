"""RootsMagic date parsing and formatting utilities."""

import re
from datetime import date
from typing import Tuple


class RMDateParser:
    """Parser for RootsMagic date format.

    RootsMagic stores dates in a special format:
    - Format: D.+YYYYMMDD..+00000000..
    - Example: D.+19210209..+00000000.. = February 9, 1921

    Components:
    - D. = Date prefix
    - +YYYYMMDD = Date value (year, month, day)
    - .. = Separator
    - +00000000 = Time component (unused, always 00000000)
    - .. = Suffix
    """

    # Regex pattern for RootsMagic date format
    PATTERN = re.compile(r'D\.\+(\d{4})(\d{2})(\d{2})\.\.\+\d{8}\.\.')

    # Month names for formatting
    MONTHS = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    @classmethod
    def parse(cls, rm_date: str) -> date | None:
        """Parse RootsMagic date string to Python date object.

        Args:
            rm_date: RootsMagic date string (e.g., "D.+19210209..+00000000..")

        Returns:
            Python date object or None if parsing fails

        Example:
            >>> RMDateParser.parse("D.+19210209..+00000000..")
            datetime.date(1921, 2, 9)
        """
        if not rm_date or not isinstance(rm_date, str):
            return None

        match = cls.PATTERN.match(rm_date)
        if not match:
            return None

        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))

            # Validate date components
            if month == 0 or day == 0:
                # Partial date (e.g., year only, or year-month only)
                # Use 1 for missing components
                month = max(1, month)
                day = max(1, day)

            return date(year, month, day)

        except (ValueError, IndexError):
            return None

    @classmethod
    def format_display(cls, rm_date: str) -> str:
        """Format RootsMagic date string for human-readable display.

        Args:
            rm_date: RootsMagic date string

        Returns:
            Formatted date string (e.g., "9 February 1921")
            Returns original string if parsing fails

        Example:
            >>> RMDateParser.format_display("D.+19210209..+00000000..")
            "9 February 1921"
        """
        parsed = cls.parse(rm_date)
        if not parsed:
            return rm_date

        # Format: "D Month YYYY" (Evidence Explained style)
        return f"{parsed.day} {cls.MONTHS[parsed.month - 1]} {parsed.year}"

    @classmethod
    def format_short(cls, rm_date: str) -> str:
        """Format RootsMagic date string in short format.

        Args:
            rm_date: RootsMagic date string

        Returns:
            Short formatted date (e.g., "9 Feb 1921")
            Returns original string if parsing fails

        Example:
            >>> RMDateParser.format_short("D.+19210209..+00000000..")
            "9 Feb 1921"
        """
        parsed = cls.parse(rm_date)
        if not parsed:
            return rm_date

        # Get abbreviated month (first 3 letters)
        month_abbr = cls.MONTHS[parsed.month - 1][:3]
        return f"{parsed.day} {month_abbr} {parsed.year}"

    @classmethod
    def format_iso(cls, rm_date: str) -> str:
        """Format RootsMagic date string in ISO 8601 format.

        Args:
            rm_date: RootsMagic date string

        Returns:
            ISO formatted date (e.g., "1921-02-09")
            Returns original string if parsing fails

        Example:
            >>> RMDateParser.format_iso("D.+19210209..+00000000..")
            "1921-02-09"
        """
        parsed = cls.parse(rm_date)
        if not parsed:
            return rm_date

        return parsed.isoformat()

    @classmethod
    def extract_year(cls, rm_date: str) -> int | None:
        """Extract year from RootsMagic date string.

        Args:
            rm_date: RootsMagic date string

        Returns:
            Year as integer or None if parsing fails

        Example:
            >>> RMDateParser.extract_year("D.+19210209..+00000000..")
            1921
        """
        parsed = cls.parse(rm_date)
        return parsed.year if parsed else None

    @classmethod
    def encode(cls, year: int, month: int = 0, day: int = 0) -> str:
        """Encode date components into RootsMagic format.

        Args:
            year: Year (4 digits)
            month: Month (1-12, or 0 for unknown)
            day: Day (1-31, or 0 for unknown)

        Returns:
            RootsMagic formatted date string

        Example:
            >>> RMDateParser.encode(1921, 2, 9)
            "D.+19210209..+00000000.."
        """
        date_str = f"{year:04d}{month:02d}{day:02d}"
        return f"D.+{date_str}..+00000000.."


def parse_rm_date(rm_date: str) -> date | None:
    """Parse RootsMagic date string to Python date object.

    Convenience function for RMDateParser.parse().

    Args:
        rm_date: RootsMagic date string

    Returns:
        Python date object or None if parsing fails
    """
    return RMDateParser.parse(rm_date)


def format_rm_date_display(rm_date: str) -> str:
    """Format RootsMagic date string for human-readable display.

    Convenience function for RMDateParser.format_display().

    Args:
        rm_date: RootsMagic date string

    Returns:
        Formatted date string
    """
    return RMDateParser.format_display(rm_date)
