"""
Parse census details from RootsMagic SourceTable.Name field.

Fallback when FamilySearch extraction fails to get state/county.
"""
import re
from typing import Optional


class SourceNameParser:
    """Parse census details from SourceTable.Name field."""

    # SourceTable.Name format: "Fed Census: YYYY, State, County [details] Surname, GivenName"
    PATTERN = re.compile(
        r'Fed\s+Census:\s*(\d{4})\s*,\s*([^,]+?)\s*,\s*([^,\[\]]+?)\s*(?:\[([^\]]*)\])?\s*(.+)$',
        re.IGNORECASE
    )

    @classmethod
    def parse(cls, source_name: str) -> dict[str, str]:
        """
        Parse census details from source name.

        Args:
            source_name: RootsMagic source name
                Example: "Fed Census: 1950, Ohio, Stark [] Adams, Verne"

        Returns:
            Dictionary with parsed fields:
            {
                'year': '1950',
                'state': 'Ohio',
                'county': 'Stark',
                'bracket_content': '',  # Content between brackets
                'person_ref': 'Adams, Verne'
            }
        """
        # Simpler approach: split by known delimiters
        if 'Fed Census:' not in source_name:
            return {}

        try:
            # Remove "Fed Census: " prefix
            rest = source_name.split('Fed Census:', 1)[1].strip()

            # Split first part (before brackets) on commas
            if '[' in rest:
                before_bracket, after_bracket = rest.split('[', 1)
                bracket_content, person_ref = after_bracket.split(']', 1)
                bracket_content = bracket_content.strip()
                person_ref = person_ref.strip()
            else:
                before_bracket = rest
                bracket_content = ''
                person_ref = ''

            # Parse year, state, county from before_bracket
            parts = [p.strip() for p in before_bracket.split(',')]
            if len(parts) >= 3:
                year = parts[0]
                state = parts[1]
                county = parts[2]

                return {
                    'year': year,
                    'state': state,
                    'county': county,
                    'bracket_content': bracket_content,
                    'person_ref': person_ref
                }
        except (ValueError, IndexError):
            pass

        return {}

    @classmethod
    def extract_location(cls, source_name: str) -> tuple[str, str]:
        """
        Extract just state and county from source name.

        Args:
            source_name: RootsMagic source name

        Returns:
            Tuple of (state, county)
            Returns ('', '') if parsing fails
        """
        parsed = cls.parse(source_name)
        return parsed.get('state', ''), parsed.get('county', '')

    @classmethod
    def extract_year(cls, source_name: str) -> Optional[int]:
        """
        Extract census year from source name.

        Args:
            source_name: RootsMagic source name

        Returns:
            Census year as integer, or None if not found
        """
        parsed = cls.parse(source_name)
        year_str = parsed.get('year')
        if year_str:
            try:
                return int(year_str)
            except ValueError:
                pass
        return None


def augment_citation_data_from_source(
    citation_data: dict,
    source_name: str
) -> dict:
    """
    Augment incomplete citation data with info from SourceTable.Name.

    Used as fallback when FamilySearch extraction fails to get state/county.

    Args:
        citation_data: Extracted data (may be incomplete)
        source_name: RootsMagic SourceTable.Name field

    Returns:
        Augmented citation data with fallback values filled in

    Example:
        >>> data = {'state': '', 'county': ''}  # Extraction failed
        >>> source = "Fed Census: 1950, Ohio, Stark [] Adams, Verne"
        >>> augment_citation_data_from_source(data, source)
        {'state': 'Ohio', 'county': 'Stark', ...}
    """
    # Only use fallback for empty fields
    state = citation_data.get('state', '').strip()
    county = citation_data.get('county', '').strip()

    if not state or not county:
        parsed_state, parsed_county = SourceNameParser.extract_location(source_name)

        if not state and parsed_state:
            citation_data['state'] = parsed_state
            citation_data['_state_source'] = 'source_name_fallback'

        if not county and parsed_county:
            citation_data['county'] = parsed_county
            citation_data['_county_source'] = 'source_name_fallback'

    return citation_data
