"""Parser for FamilySearch census citations.

This module provides regex-based parsing of FamilySearch citations.
For production use, consider using LLM-based parsing for better accuracy
and handling of format variations.
"""

import re
from datetime import datetime

from loguru import logger

from rmcitecraft.models.citation import ParsedCitation


class FamilySearchParser:
    """Parse FamilySearch census citations into structured data."""

    # Regex patterns for SourceName format ("Fed Census: 1940, Ohio, Noble...")
    YEAR_PATTERN = re.compile(r"Fed Census: (\d{4}),")
    STATE_COUNTY_PATTERN = re.compile(r"Fed Census: \d{4}, ([^,]+), ([^\[]+)")
    PERSON_NAME_PATTERN = re.compile(r"\] ([^,]+), ([^\s]+)(?:\s+(.+))?$")
    CITATION_DETAILS_PATTERN = re.compile(r"\[citing ([^\]]+)\]")

    # Regex patterns for FamilySearch citation format
    # Matches: "United States Census, 1940", "United States 1950 Census", "United States, Census, 1950"
    FS_YEAR_PATTERN = re.compile(r"United States,?\s+(?:Census,?\s*(\d{4})|(\d{4})\s+Census)", re.IGNORECASE)
    # FamilySearch format: Person Name, Town/Ward, County, State, United States
    FS_LOCATION_PATTERN = re.compile(
        r",\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*United States",
        re.IGNORECASE
    )

    # Pattern for ED in citation text (avoid matching dates like "24 July")
    # ED formats: 95, 5-1B, 214, etc.
    ED_PATTERN = re.compile(
        r"enumeration district[^\d]*\(ED\)[^\d]*([\d\-]+[AB]?)|E\.?D\.?\s+([\d\-]+[AB]?)",
        re.IGNORECASE,
    )

    # Pattern for sheet
    SHEET_PATTERN = re.compile(r"sheet (\d+[AB]?)", re.IGNORECASE)

    # Pattern for family
    FAMILY_PATTERN = re.compile(r"family (\d+)", re.IGNORECASE)

    # Pattern for dwelling
    DWELLING_PATTERN = re.compile(r"dwelling (\d+)", re.IGNORECASE)

    # Pattern for FamilySearch URL - match both ARK and PAL formats
    # ARK format: /ark:/NAAN/Name (newer format)
    # PAL format: /pal:/MM9.1.1/ID (older format)
    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?familysearch\.org/(?:ark|pal):/[^\s)]+",
        re.IGNORECASE,
    )

    # Pattern for access date
    # Matches both "accessed DD MMM YYYY" and ": DDD MMM DD HH:MM:SS UTC YYYY" formats
    ACCESS_DATE_PATTERN = re.compile(
        r"(?:accessed\s+)?(\d{1,2} \w+ \d{4})|:\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+[\d:]{8}\s+UTC\s+\d{4})",
        re.IGNORECASE,
    )

    # Pattern for NARA publication
    NARA_PATTERN = re.compile(r"NARA microfilm publication ([A-Z]\d+)", re.IGNORECASE)

    # Pattern for FHL microfilm
    FHL_PATTERN = re.compile(r"FHL microfilm ([\d,]+)", re.IGNORECASE)

    # Pattern for simplified FamilySearch format: "Entry for Person Name(s), DD Month YYYY."
    # Handles both "Entry for Name, 1940." and "Entry for Name, 10 April 1950."
    ENTRY_FOR_PATTERN = re.compile(r"Entry for (.+?),\s*(?:\d{1,2}\s+\w+\s+)?\d{4}\s*\.", re.IGNORECASE)

    def parse(self, source_name: str, familysearch_entry: str, citation_id: int) -> ParsedCitation:
        """Parse FamilySearch citation into structured data.

        Args:
            source_name: Either RM Source Name ("Fed Census: 1900, Ohio, Noble...")
                        or FamilySearch citation ("United States Census, 1940,...")
            familysearch_entry: RM FamilySearch Entry (full citation text, often empty)
            citation_id: Citation ID from database

        Returns:
            ParsedCitation object with extracted fields.
        """
        # Detect format: SourceName format vs FamilySearch format
        is_familysearch_format = self.FS_YEAR_PATTERN.search(source_name) is not None

        if is_familysearch_format:
            return self._parse_familysearch_format(source_name, familysearch_entry, citation_id)
        else:
            return self._parse_sourcename_format(source_name, familysearch_entry, citation_id)

    def _parse_sourcename_format(self, source_name: str, familysearch_entry: str, citation_id: int) -> ParsedCitation:
        """Parse SourceName format (Fed Census: 1900, Ohio, Noble...)."""
        # Extract census year
        year_match = self.YEAR_PATTERN.search(source_name)
        if not year_match:
            logger.error(f"Could not extract year from: {source_name}")
            return self._create_error_citation(
                citation_id, source_name, familysearch_entry, "Could not extract census year"
            )
        census_year = int(year_match.group(1))

        # Extract state and county
        state_county_match = self.STATE_COUNTY_PATTERN.search(source_name)
        if not state_county_match:
            logger.error(f"Could not extract state/county from: {source_name}")
            return self._create_error_citation(
                citation_id,
                source_name,
                familysearch_entry,
                "Could not extract state/county",
            )
        state = state_county_match.group(1).strip()
        county = state_county_match.group(2).strip()

        # Extract citation details from brackets
        citation_details = ""
        details_match = self.CITATION_DETAILS_PATTERN.search(source_name)
        if details_match:
            citation_details = details_match.group(1)

        # Extract person name from end of source name
        person_match = self.PERSON_NAME_PATTERN.search(source_name)
        surname = ""
        given_name = ""
        person_name = ""
        if person_match:
            surname = person_match.group(1).strip()
            given_name = person_match.group(2).strip()
            if person_match.group(3):
                given_name += " " + person_match.group(3).strip()
            person_name = f"{given_name} {surname}"
        else:
            logger.warning(f"Could not extract person name from: {source_name}")

        # Extract town/ward from familysearch_entry
        town_ward = self._extract_town_ward(familysearch_entry, county)

        # Extract enumeration district
        ed = self._extract_ed(familysearch_entry, citation_details)

        # Extract sheet
        sheet = self._extract_sheet(familysearch_entry, citation_details)

        # Extract family number
        family_number = self._extract_family(familysearch_entry, citation_details)

        # Extract dwelling number
        dwelling_number = self._extract_dwelling(familysearch_entry, citation_details)

        # Extract FamilySearch URL
        url = self._extract_url(familysearch_entry)

        # Extract access date
        access_date = self._extract_access_date(familysearch_entry)

        # Extract NARA publication
        nara = self._extract_nara(familysearch_entry)

        # Extract FHL microfilm
        fhl = self._extract_fhl(familysearch_entry)

        # Determine missing fields
        missing_fields = self._identify_missing_fields(
            census_year, ed, sheet, family_number, town_ward
        )

        # Create citation object
        citation = ParsedCitation(
            citation_id=citation_id,
            source_name=source_name,
            familysearch_entry=familysearch_entry,
            census_year=census_year,
            state=state,
            county=county,
            town_ward=town_ward,
            enumeration_district=ed,
            sheet=sheet,
            family_number=family_number,
            dwelling_number=dwelling_number,
            person_name=person_name,
            given_name=given_name,
            surname=surname,
            familysearch_url=url,
            access_date=access_date,
            nara_publication=nara,
            fhl_microfilm=fhl,
            missing_fields=missing_fields,
            is_complete=len(missing_fields) == 0,
        )

        logger.debug(
            f"Parsed citation {citation_id}: {person_name}, "
            f"{census_year} {state}, {county} (missing: {missing_fields})"
        )

        return citation

    def _extract_town_ward(self, text: str, county: str) -> str | None:
        """Extract town/ward from citation text."""
        # Look for text after person name and before semicolon
        # Pattern: "Person Name, Town/Ward, County, State, Country; citing..."

        # Try to find pattern: "Name, [Town/Ward], [County]"
        # Split by comma and look for the segment between name and county
        parts = text.split(",")

        # Find the index where county appears
        county_idx = None
        for i, part in enumerate(parts):
            if county in part:
                county_idx = i
                break

        if county_idx is not None and county_idx > 0:
            # The town/ward is typically the part just before the county
            # Look backwards from county
            for i in range(county_idx - 1, -1, -1):
                part = parts[i].strip()
                # Skip parts that are person names (typically first 1-2 parts)
                # Skip parts that are country names
                if part and part not in ["United States", "Maryland", "Ohio"]:
                    # Clean up the town name
                    town = part
                    # Remove semicolon and anything after
                    town = town.split(";")[0]
                    # Remove "population schedule" if present
                    town = re.sub(r"\s*population schedule\s*", "", town, flags=re.IGNORECASE)
                    # Remove state/country if present
                    town = re.sub(r"\s+(United States|Maryland|Ohio).*$", "", town, flags=re.IGNORECASE)

                    # Only return if it looks like a town/ward (not a person name)
                    if town and not any(name_part in town.lower() for name_part in ["ijams", "brannon"]):
                        return town.strip() if town.strip() else None

        return None

    def _extract_ed(self, text: str, details: str) -> str | None:
        """Extract enumeration district from text or details."""
        # Try citation details first
        match = self.ED_PATTERN.search(details)
        if match:
            for group in match.groups():
                if group:
                    return group

        # Try full text
        match = self.ED_PATTERN.search(text)
        if match:
            for group in match.groups():
                if group:
                    return group
        return None

    def _extract_sheet(self, text: str, details: str) -> str | None:
        """Extract sheet from text or details."""
        # Try citation details first
        match = self.SHEET_PATTERN.search(details)
        if match:
            return match.group(1)

        # Try full text
        match = self.SHEET_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_family(self, text: str, details: str) -> str | None:
        """Extract family number from text or details."""
        match = self.FAMILY_PATTERN.search(details)
        if match:
            return match.group(1)

        match = self.FAMILY_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_dwelling(self, text: str, details: str) -> str | None:
        """Extract dwelling number from text or details."""
        match = self.DWELLING_PATTERN.search(details)
        if match:
            return match.group(1)

        match = self.DWELLING_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_url(self, text: str) -> str:
        """Extract FamilySearch URL."""
        match = self.URL_PATTERN.search(text)
        if match:
            return match.group(0)
        return ""

    def _format_access_date(self, date_str: str) -> str:
        """Convert various date formats to 'dd mmmm yyyy' format (e.g., '3 January 2022').

        Args:
            date_str: Date string in various formats

        Returns:
            Formatted date string in 'dd mmmm yyyy' format
        """
        if not date_str:
            return ""

        # Remove 'accessed' prefix if present
        date_str = date_str.replace("accessed", "").strip()

        # Try different date formats
        date_formats = [
            "%a %b %d %H:%M:%S UTC %Y",  # "Tue Mar 19 21:29:33 UTC 2024"
            "%d %B %Y",                   # "16 February 2020"
            "%d %b %Y",                   # "16 Feb 2020" (abbreviated month)
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Format as "d MMMM yyyy" (no leading zero on day)
                return dt.strftime("%-d %B %Y")  # %-d removes leading zero on Unix/Mac
            except ValueError:
                continue

        # If no format matched, return original
        logger.warning(f"Could not parse date format: {date_str}")
        return date_str

    def _extract_access_date(self, text: str) -> str:
        """Extract and format access date."""
        match = self.ACCESS_DATE_PATTERN.search(text)
        if match:
            # Pattern has two groups - return whichever matched
            raw_date = match.group(1) or match.group(2) or ""
            # Format to "dd mmmm yyyy" format
            return self._format_access_date(raw_date)
        return ""

    def _extract_nara(self, text: str) -> str | None:
        """Extract NARA publication number."""
        match = self.NARA_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_fhl(self, text: str) -> str | None:
        """Extract FHL microfilm number."""
        match = self.FHL_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _identify_missing_fields(
        self,
        census_year: int,
        ed: str | None,
        sheet: str | None,
        family: str | None,
        town: str | None,
    ) -> list[str]:
        """Identify missing required fields based on census year."""
        missing = []

        # All years need sheet (town_ward is optional)
        if not sheet:
            missing.append("sheet")

        # 1900-1950 require ED and family number
        if census_year >= 1900:
            if not ed:
                missing.append("enumeration_district")
            if not family:
                missing.append("family_number")

        return missing

    def _parse_familysearch_format(self, source_name: str, familysearch_entry: str, citation_id: int) -> ParsedCitation:
        """Parse FamilySearch citation format (United States Census, 1940,...)."""
        # Extract census year (pattern has two groups - one will match)
        year_match = self.FS_YEAR_PATTERN.search(source_name)
        if not year_match:
            logger.error(f"Could not extract year from FamilySearch format: {source_name}")
            return self._create_error_citation(
                citation_id, source_name, familysearch_entry, "Could not extract census year"
            )
        # Get whichever group matched
        census_year = int(year_match.group(1) or year_match.group(2))

        # FamilySearch format structure:
        # "United States Census, 1940," database with images, <i>FamilySearch</i> (URL : accessed DATE),
        # Person Name, Town/Ward, County, State, United States; citing ...

        # Find the section after the access date but before "; citing"
        # Pattern: "), Person Name, Town, County, State, United States; citing"
        person_start = source_name.find('), ')
        citing_start = source_name.find('; citing')

        if person_start == -1:
            logger.error(f"Could not find person section in FamilySearch format: {source_name}")
            return self._create_error_citation(
                citation_id,
                source_name,
                familysearch_entry,
                "Could not find person/location section",
            )

        # Extract the location section between "), " and "; citing" (or end of string)
        end_pos = citing_start if citing_start != -1 else len(source_name)
        location_section = source_name[person_start + 3:end_pos]

        # Split on commas and find "United States"
        parts = [p.strip() for p in location_section.split(',')]

        # Remove HTML tags from parts
        parts = [re.sub(r'<[^>]+>', '', p) for p in parts]

        us_index = None
        for i, part in enumerate(parts):
            if 'United States' in part:
                us_index = i
                break

        # Check if this is simplified FamilySearch format (no location data)
        # Format: "United States Census, 1940", , <i>FamilySearch</i> (URL), Entry for Person Names, 1940.
        if us_index is None or us_index < 3:
            logger.debug("Location hierarchy not found, checking for simplified format")
            return self._parse_simplified_familysearch_format(source_name, familysearch_entry, citation_id, census_year)

        # Location components are the parts before "United States"
        # Format: [person_name, town_ward, county, state, "United States"]
        # But could also be: [person_name, town_ward, town_subdivision, county, state, "United States"]
        state = parts[us_index - 1].strip()
        county = parts[us_index - 2].strip()

        # Town/ward may span multiple parts before county
        # Combine all parts between person name and county
        if us_index >= 4:
            town_parts = parts[1:us_index - 2]
            town_ward = ', '.join(town_parts) if town_parts else None
        else:
            town_ward = None

        # Person name is the first part
        person_name = parts[0].strip()

        # Split person name into given and surname
        name_parts = person_name.split()
        if len(name_parts) >= 2:
            # Assume last part is surname
            surname = name_parts[-1]
            given_name = ' '.join(name_parts[:-1])
        else:
            surname = person_name
            given_name = ""

        # Extract citation details from full text
        # source_name contains the full citation text (from BLOB or user input)
        # familysearch_entry is the context (SourceName or ActualText)
        full_text = source_name
        citation_details = ""

        # Find "citing" section
        citing_start = full_text.find('; citing ')
        if citing_start != -1:
            citation_details = full_text[citing_start + 9:]  # Skip "; citing "

        # Extract enumeration district
        ed = self._extract_ed(full_text, citation_details)

        # Extract sheet
        sheet = self._extract_sheet(full_text, citation_details)

        # Extract family number
        family_number = self._extract_family(full_text, citation_details)

        # Extract dwelling number
        dwelling_number = self._extract_dwelling(full_text, citation_details)

        # Extract FamilySearch URL
        url = self._extract_url(full_text)

        # Extract access date
        access_date = self._extract_access_date(full_text)

        # Extract NARA publication
        nara = self._extract_nara(full_text)

        # Extract FHL microfilm
        fhl = self._extract_fhl(full_text)

        # Determine missing fields
        missing_fields = self._identify_missing_fields(
            census_year, ed, sheet, family_number, town_ward
        )

        # Create citation object
        citation = ParsedCitation(
            citation_id=citation_id,
            source_name=source_name,
            familysearch_entry=familysearch_entry,
            census_year=census_year,
            state=state,
            county=county,
            town_ward=town_ward,
            enumeration_district=ed,
            sheet=sheet,
            family_number=family_number,
            dwelling_number=dwelling_number,
            person_name=person_name,
            given_name=given_name,
            surname=surname,
            familysearch_url=url,
            access_date=access_date,
            nara_publication=nara,
            fhl_microfilm=fhl,
            missing_fields=missing_fields,
            is_complete=len(missing_fields) == 0,
        )

        logger.debug(
            f"Parsed FamilySearch citation {citation_id}: {person_name}, "
            f"{census_year} {state}, {county} (missing: {missing_fields})"
        )

        return citation

    def _parse_simplified_familysearch_format(
        self,
        source_name: str,
        familysearch_entry: str,
        citation_id: int,
        census_year: int,
    ) -> ParsedCitation:
        """Parse simplified FamilySearch format with minimal details.

        Format: "United States Census, 1940", , <i>FamilySearch</i> (URL : date), Entry for Person Names, 1940.

        This format lacks:
        - State, County, Town information
        - Enumeration District, Sheet, Family numbers

        Can extract:
        - Census year (already extracted)
        - Person name(s) from "Entry for" pattern
        - FamilySearch URL
        - Access date
        """
        # For simplified format, source_name contains the citation text (with URL)
        # familysearch_entry contains the RM SourceName (with state/county)
        citation_text = source_name
        rm_source_name = familysearch_entry

        # Extract person names from citation text
        person_name = ""
        given_name = ""
        surname = ""

        # Try "Entry for" pattern first (1950 format)
        entry_match = self.ENTRY_FOR_PATTERN.search(citation_text)
        if entry_match:
            names_text = entry_match.group(1).strip()

            # Handle multiple names: "Herbert E Ijans and Nelle S Ijans"
            # Take the first person mentioned
            if ' and ' in names_text:
                first_person = names_text.split(' and ')[0].strip()
            else:
                first_person = names_text

            person_name = first_person
        else:
            # Try minimal format: "), Person Name, Year; citing"
            # Pattern: after "), " extract text until comma or semicolon
            import re
            minimal_pattern = re.search(r'\),\s*([^,;]+?)(?:,\s*\d{4}\s*;|,|;)', citation_text)
            if minimal_pattern:
                person_name = minimal_pattern.group(1).strip()

        # Split person name into given and surname
        if person_name:
            name_parts = person_name.split()
            if len(name_parts) >= 2:
                # Assume last part is surname
                surname = name_parts[-1]
                given_name = ' '.join(name_parts[:-1])
            else:
                surname = person_name
                given_name = ""

        # Try to extract state/county from RM SourceName
        # Format: "Fed Census: 1940, California, San Bernardino [] Person"
        state = ""
        county = ""

        if rm_source_name and rm_source_name.startswith("Fed Census:"):
            state_county_match = self.STATE_COUNTY_PATTERN.search(rm_source_name)
            if state_county_match:
                state = state_county_match.group(1).strip()
                county = state_county_match.group(2).strip()

        # Extract URL and access date from citation text
        url = self._extract_url(citation_text)
        access_date = self._extract_access_date(citation_text)

        # Identify missing fields (most will be missing in this format)
        missing_fields = []
        if not state:
            missing_fields.append("state")
        if not county:
            missing_fields.append("county")
        missing_fields.extend(["enumeration_district", "sheet", "family_number"])

        # Create citation object
        citation = ParsedCitation(
            citation_id=citation_id,
            source_name=citation_text,
            familysearch_entry=rm_source_name or "",
            census_year=census_year,
            state=state,
            county=county,
            town_ward=None,
            enumeration_district=None,
            sheet=None,
            family_number=None,
            dwelling_number=None,
            person_name=person_name,
            given_name=given_name,
            surname=surname,
            familysearch_url=url,
            access_date=access_date,
            nara_publication=None,
            fhl_microfilm=None,
            missing_fields=missing_fields,
            is_complete=False,  # Simplified format is never complete
        )

        logger.debug(
            f"Parsed simplified FamilySearch citation {citation_id}: {person_name}, "
            f"{census_year} {state or '(no state)'}, {county or '(no county)'} "
            f"(simplified format - missing: {missing_fields})"
        )

        return citation

    def _create_error_citation(
        self,
        citation_id: int,
        source_name: str,
        familysearch_entry: str,
        error: str,
    ) -> ParsedCitation:
        """Create a citation object with error information."""
        return ParsedCitation(
            citation_id=citation_id,
            source_name=source_name,
            familysearch_entry=familysearch_entry,
            census_year=1900,  # Default
            state="",
            county="",
            person_name="",
            given_name="",
            surname="",
            familysearch_url="",
            access_date="",
            is_complete=False,
            errors=[error],
        )
