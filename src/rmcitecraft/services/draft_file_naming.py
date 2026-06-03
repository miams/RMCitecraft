"""
Draft Registration File Naming Service.

Generates standardized filenames for draft registration card images based on
RootsMagic person data.

Format: "surname, givenname (birth-death).jpg"
Example: "Iams, Alexander Murdoch (1917-1984).jpg"
"""

from pathlib import Path
from typing import Optional

from loguru import logger

from rmcitecraft.database.connection import connect_rmtree


def get_filename_from_rin(
    rin: int, rmtree_path: str | Path, extension: str = ".jpg"
) -> str:
    """
    Generate filename for draft registration image from RIN.

    Queries RootsMagic database to get person's name and vital dates.

    Args:
        rin: RootsMagic person ID (RIN)
        rmtree_path: Path to .rmtree database file
        extension: File extension (default: .jpg)

    Returns:
        Formatted filename: "surname, givenname (birth-death).jpg"
        If name not found: "Draft_RIN_{rin}.jpg"
        If birth/death missing: "surname, givenname.jpg" or partial format

    Examples:
        >>> get_filename_from_rin(527, "data/Iiams.rmtree")
        "Iams, Alexander Murdoch (1917-1984).jpg"

        >>> get_filename_from_rin(999, "data/Iiams.rmtree")  # Birth year missing
        "Smith, John (-1950).jpg"

        >>> get_filename_from_rin(1000, "data/Iiams.rmtree")  # Both missing
        "Doe, Jane.jpg"
    """
    rmtree_path = Path(rmtree_path)

    if not rmtree_path.exists():
        logger.error(f"RootsMagic database not found: {rmtree_path}")
        return f"Draft_RIN_{rin}{extension}"

    try:
        conn = connect_rmtree(str(rmtree_path), read_only=True)
        cursor = conn.cursor()

        # Get primary name
        cursor.execute(
            """
            SELECT Surname, Given
            FROM NameTable
            WHERE OwnerID = ? AND IsPrimary = 1
            """,
            (rin,),
        )

        name_row = cursor.fetchone()

        if not name_row:
            logger.warning(f"Person RIN {rin} not found in database")
            conn.close()
            return f"Draft_RIN_{rin}{extension}"

        surname, given_name = name_row

        # Get birth year
        cursor.execute(
            """
            SELECT Date
            FROM EventTable
            WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 1
            ORDER BY SortDate
            LIMIT 1
            """,
            (rin,),
        )

        birth_row = cursor.fetchone()
        birth_year = _extract_year_from_rm_date(birth_row[0]) if birth_row else None

        # Get death year
        cursor.execute(
            """
            SELECT Date
            FROM EventTable
            WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 2
            ORDER BY SortDate
            LIMIT 1
            """,
            (rin,),
        )

        death_row = cursor.fetchone()
        death_year = _extract_year_from_rm_date(death_row[0]) if death_row else None

        conn.close()

        # Build filename
        base_name = f"{surname}, {given_name}"

        if birth_year and death_year:
            filename = f"{base_name} ({birth_year}-{death_year}){extension}"
        elif birth_year:
            filename = f"{base_name} ({birth_year}-){extension}"
        elif death_year:
            filename = f"{base_name} (-{death_year}){extension}"
        else:
            filename = f"{base_name}{extension}"

        logger.debug(f"Generated filename for RIN {rin}: {filename}")
        return filename

    except Exception as e:
        logger.error(f"Error generating filename for RIN {rin}: {e}")
        return f"Draft_RIN_{rin}{extension}"


def get_unique_filename(
    base_filename: str, directory: Path, max_attempts: int = 100
) -> str:
    """
    Get unique filename by appending counter if file exists.

    Args:
        base_filename: Base filename (e.g., "Iams, Alexander (1917-1984).jpg")
        directory: Directory to check for existing files
        max_attempts: Maximum number of attempts (default: 100)

    Returns:
        Unique filename with counter if needed
        (e.g., "Iams, Alexander (1917-1984)_2.jpg")

    Raises:
        RuntimeError: If max_attempts exceeded
    """
    target_path = directory / base_filename

    if not target_path.exists():
        return base_filename

    # File exists, try with counter
    stem = target_path.stem
    extension = target_path.suffix

    for i in range(2, max_attempts + 2):
        new_filename = f"{stem}_{i}{extension}"
        new_path = directory / new_filename

        if not new_path.exists():
            logger.debug(f"File exists, using: {new_filename}")
            return new_filename

    raise RuntimeError(
        f"Could not find unique filename after {max_attempts} attempts: {base_filename}"
    )


def _extract_year_from_rm_date(rm_date: str) -> Optional[int]:
    """
    Extract year from RootsMagic date string.

    RootsMagic stores dates in packed format:
    - "D.+19170429..+00000000.." (exact date: April 29, 1917)
    - "D.+19170000..+00000000.." (year only: 1917)
    - "A.+19170429..+00000000.." (about)
    - "C.+19170429..+00000000.." (calculated)
    - "E.+19170429..+00000000.." (estimated)

    Format: <modifier>.<+/-><YYYYMMDD>..<+/-><YYYYMMDD>..
    - modifier: D (exact), A (about), C (calculated), E (estimated), B (before), T (after)
    - +/- : date sign
    - YYYYMMDD: packed date (year, month, day)
    - Second date is for ranges

    Args:
        rm_date: RootsMagic date string

    Returns:
        Year as integer, or None if not found
    """
    if not rm_date:
        return None

    try:
        # Parse packed date format: "D.+19170429..+00000000.."
        # Extract the YYYYMMDD portion after the first +/- sign
        parts = rm_date.split(".")

        if len(parts) < 2:
            logger.debug(f"Could not parse date format: {rm_date}")
            return None

        # Second part should be like "+19170429" or "-19170429"
        date_part = parts[1]

        # Remove leading +/- sign
        if date_part.startswith(("+", "-")):
            date_part = date_part[1:]

        # Extract year (first 4 digits of YYYYMMDD)
        if len(date_part) >= 4:
            year_str = date_part[:4]
            year = int(year_str)

            # Sanity check (1700-2100)
            if 1700 <= year <= 2100:
                return year
            else:
                logger.warning(f"Year {year} outside valid range (1700-2100)")
                return None
        else:
            logger.debug(f"Date part too short: {date_part}")
            return None

    except ValueError as e:
        logger.debug(f"Could not extract year from date: {rm_date} - {e}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing RootsMagic date '{rm_date}': {e}")
        return None


def main():
    """Test file naming with real database."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python draft_file_naming.py <rmtree_path> <rin>")
        sys.exit(1)

    rmtree_path = sys.argv[1]
    rin = int(sys.argv[2])

    filename = get_filename_from_rin(rin, rmtree_path)
    print(f"RIN {rin}: {filename}")

    # Test unique filename generation
    directory = Path("/tmp")
    test_file = directory / filename

    # Create the file to test uniqueness
    test_file.touch()

    unique_filename = get_unique_filename(filename, directory)
    print(f"Unique filename: {unique_filename}")

    # Cleanup
    test_file.unlink()


if __name__ == "__main__":
    main()
