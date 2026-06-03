"""Service for building Evidence Explained formatted draft registration citations."""

import re
from datetime import datetime
from typing import Optional, Tuple
from loguru import logger
from playwright.async_api import Page

from rmcitecraft.models.draft_record import DraftRecord
from rmcitecraft.models.citation_data import (
    FamilySearchMetadata,
    SourceData,
    CitationData,
    get_state_abbreviation,
    get_state_full_name,
)


class DraftCitationBuilder:
    """Build Evidence Explained formatted citations for draft registrations.

    Supports WW1 and WW2 draft registration citations following Evidence Explained
    standards with proper formatting for footnotes, short footnotes, and bibliography.
    """

    # Pattern to extract FamilySearch ARK ID
    ARK_PATTERN = re.compile(r'ark:/(\d+/[^/\s\)"]+)')

    # Pattern to extract state from collection name
    STATE_PATTERN = re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)*),\s*World War', re.IGNORECASE)

    def __init__(self):
        """Initialize the citation builder."""
        pass

    def parse_familysearch_url(self, citation_text: str, state_hint: Optional[str] = None) -> FamilySearchMetadata:
        """Parse FamilySearch URL or citation text to extract metadata.

        Args:
            citation_text: FamilySearch URL or citation text
            state_hint: Optional state hint from record data

        Returns:
            FamilySearchMetadata with extracted information
        """
        metadata = FamilySearchMetadata()

        if not citation_text:
            return metadata

        # Extract ARK ID
        ark_match = self.ARK_PATTERN.search(citation_text)
        if ark_match:
            metadata.ark_id = ark_match.group(1)
            # Construct full URL if we have ARK
            if 'https://' not in citation_text.lower():
                metadata.url = f"https://familysearch.org/ark:/{metadata.ark_id}"
            else:
                # Extract full URL
                url_match = re.search(r'https?://[^\s\)"]+', citation_text)
                if url_match:
                    metadata.url = url_match.group(0)

        # Extract state from citation text
        state_match = self.STATE_PATTERN.search(citation_text)
        if state_match:
            state_name = state_match.group(1)
            metadata.state = state_name
            metadata.state_abbr = get_state_abbreviation(state_name)
        elif state_hint:
            # Use hint if provided
            if len(state_hint) == 2:
                metadata.state_abbr = state_hint.upper()
                metadata.state = get_state_full_name(state_hint)
            else:
                metadata.state = state_hint
                metadata.state_abbr = get_state_abbreviation(state_hint)

        # Determine registration type and year from citation text
        # Check explicit mentions first
        if 'world war ii' in citation_text.lower() or 'world war 2' in citation_text.lower():
            metadata.registration_type = "WW2"
            # WW2 was 1940-1947
            year_match = re.search(r'19[4-5]\d', citation_text)
            if year_match:
                metadata.year = int(year_match.group(0))
            else:
                metadata.year = 1940  # Default
        elif 'world war i' in citation_text.lower() or 'world war 1' in citation_text.lower():
            metadata.registration_type = "WW1"
            # WW1 was 1917-1918
            year_match = re.search(r'191[78]', citation_text)
            if year_match:
                metadata.year = int(year_match.group(0))
            else:
                metadata.year = 1917  # Default
        else:
            # Try to extract any 4-digit year and infer type
            year_match = re.search(r'\b(19\d{2})\b', citation_text)
            if year_match:
                year = int(year_match.group(1))
                metadata.year = year
                if 1917 <= year <= 1918:
                    metadata.registration_type = "WW1"
                elif 1940 <= year <= 1947:
                    metadata.registration_type = "WW2"

        # Extract collection name
        # Look for quoted collection name
        collection_match = re.search(r'[""""]([^"""]+Draft[^"""]+)[""""]', citation_text)
        if collection_match:
            metadata.collection_name = collection_match.group(1).strip()
        elif metadata.state and metadata.registration_type:
            # Generate standard collection name
            if metadata.registration_type == "WW1":
                metadata.collection_name = f"{metadata.state}, World War I Draft Registration Cards, 1917-1918"
            else:  # WW2
                metadata.collection_name = f"{metadata.state}, World War II Draft Registration Cards, 1940-1947"

        return metadata

    def build_source(self, metadata: FamilySearchMetadata) -> SourceData:
        """Build source data for RootsMagic SourceTable.

        Args:
            metadata: Parsed FamilySearch metadata

        Returns:
            SourceData with formatted citation components
        """
        # Source name is the collection name
        source_name = metadata.collection_name or f"{metadata.state} Draft Registration Cards"

        # Bibliography
        bibliography = self.format_bibliography(metadata)

        # For free-form citations (TemplateID=0), we'll store footnote/short footnote
        # in the Fields BLOB
        fields_blob = self._create_source_fields_blob(
            footnote="",  # Will be filled per-citation
            short_footnote="",
            bibliography=bibliography
        )

        return SourceData(
            name=source_name,
            ref_number="",
            comments=f"FamilySearch collection for {metadata.state} draft registrations",
            bibliography=bibliography,
            footnote_template="",
            short_footnote_template="",
            fields_blob=fields_blob,
            template_id=0  # Free-form citation
        )

    def build_citation(self, record: DraftRecord, metadata: FamilySearchMetadata,
                      source_id: int) -> CitationData:
        """Build citation data for RootsMagic CitationTable.

        Args:
            record: Draft record with person information
            metadata: Parsed FamilySearch metadata
            source_id: SourceID this citation belongs to

        Returns:
            CitationData with formatted citation fields
        """
        # Enrich metadata with county from record if available
        if record.county and not metadata.county:
            metadata.county = record.county

        footnote = self.format_footnote(record, metadata)
        short_footnote = self.format_short_footnote(record, metadata)
        bibliography = self.format_bibliography(metadata)

        # Create Fields BLOB with citation text
        fields_blob = self._create_citation_fields_blob(
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography
        )

        return CitationData(
            source_id=source_id,
            comments="",
            ref_number="",
            footnote=footnote,
            short_footnote=short_footnote,
            bibliography=bibliography,
            fields_blob=fields_blob,
            actual_text="",
            quality=0
        )

    def format_footnote(self, record: DraftRecord, metadata: FamilySearchMetadata) -> str:
        """Format full footnote in Evidence Explained style.

        Args:
            record: Draft record with person information
            metadata: Parsed FamilySearch metadata

        Returns:
            Formatted footnote text
        """
        # Extract year from registration_date if available, otherwise use metadata.year
        year = metadata.year
        if record.registration_date:
            year_match = re.search(r'19\d{2}', record.registration_date)
            if year_match:
                year = int(year_match.group(0))

        person_name = record.full_name

        if metadata.is_ww1:
            # WW1 format (simpler, no ED numbers)
            parts = [
                f"{year} U.S. draft registration",
            ]

            if metadata.county:
                parts.append(f"{metadata.county_citation_form}, {metadata.state_citation_form}")
            elif metadata.state:
                parts.append(metadata.state_citation_form)

            parts.append(person_name)

            footnote_base = ', '.join(parts)

        else:  # WW2
            # WW2 format
            parts = [
                f"{year} U.S. draft registration",
            ]

            if metadata.county:
                parts.append(f"{metadata.county_citation_form}, {metadata.state_citation_form}")
            elif metadata.state:
                parts.append(metadata.state_citation_form)

            parts.append(person_name)

            footnote_base = ', '.join(parts)

        # Add imaged citation
        if metadata.collection_name and metadata.url:
            citation_part = f'imaged, "{metadata.collection_name}," FamilySearch ({metadata.url})'
            footnote = f"{footnote_base}; {citation_part}."
        elif metadata.collection_name:
            footnote = f"{footnote_base}; \"{metadata.collection_name}.\""
        else:
            footnote = f"{footnote_base}."

        return footnote

    def format_short_footnote(self, record: DraftRecord, metadata: FamilySearchMetadata) -> str:
        """Format abbreviated short footnote.

        Args:
            record: Draft record with person information
            metadata: Parsed FamilySearch metadata

        Returns:
            Formatted short footnote text
        """
        year = metadata.year
        if record.registration_date:
            year_match = re.search(r'19\d{2}', record.registration_date)
            if year_match:
                year = int(year_match.group(0))

        person_name = record.full_name

        parts = [f"{year} U.S. draft reg."]

        if metadata.county and metadata.state_short_form:
            parts.append(f"{metadata.county_short_form}, {metadata.state_short_form}")
        elif metadata.state_short_form:
            parts.append(metadata.state_short_form)

        parts.append(person_name)

        return ', '.join(parts) + '.'

    def format_bibliography(self, metadata: FamilySearchMetadata) -> str:
        """Format bibliography entry.

        Args:
            metadata: Parsed FamilySearch metadata

        Returns:
            Formatted bibliography text
        """
        if metadata.collection_name:
            return f'"{metadata.collection_name}." Database with images. FamilySearch. http://FamilySearch.org.'
        elif metadata.state and metadata.registration_type:
            if metadata.registration_type == "WW1":
                collection = f"{metadata.state}, World War I Draft Registration Cards, 1917-1918"
            else:
                collection = f"{metadata.state}, World War II Draft Registration Cards, 1940-1947"
            return f'"{collection}." Database with images. FamilySearch. http://FamilySearch.org.'
        else:
            return "United States Draft Registration Cards. Database with images. FamilySearch. http://FamilySearch.org."

    def _create_source_fields_blob(self, footnote: str, short_footnote: str,
                                   bibliography: str) -> bytes:
        """Create XML BLOB for SourceTable.Fields.

        Args:
            footnote: Footnote template text
            short_footnote: Short footnote template text
            bibliography: Bibliography text

        Returns:
            UTF-8 encoded XML BLOB
        """
        # For free-form citations (TemplateID=0), the Fields BLOB contains
        # the three citation forms in XML format with HTML entities encoded

        # HTML entities that need to be XML-encoded
        def xml_escape(text: str) -> str:
            """Escape text for XML, preserving HTML tags as entities."""
            # First, replace any literal HTML tags with entity-encoded versions
            text = text.replace('<i>', '&lt;i&gt;')
            text = text.replace('</i>', '&lt;/i&gt;')
            text = text.replace('<b>', '&lt;b&gt;')
            text = text.replace('</b>', '&lt;/b&gt;')
            text = text.replace('<u>', '&lt;u&gt;')
            text = text.replace('</u>', '&lt;/u&gt;')
            # XML special characters
            text = text.replace('&', '&amp;')  # Must be first
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('"', '&quot;')
            text = text.replace("'", '&apos;')
            return text

        # Create XML structure
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<Root>\n'
        xml += f'  <Footnote>{xml_escape(footnote)}</Footnote>\n'
        xml += f'  <ShortFootnote>{xml_escape(short_footnote)}</ShortFootnote>\n'
        xml += f'  <Bibliography>{xml_escape(bibliography)}</Bibliography>\n'
        xml += '</Root>'

        # Encode as UTF-8 with BOM (EFBBBF)
        return b'\xef\xbb\xbf' + xml.encode('utf-8')

    def _create_citation_fields_blob(self, footnote: str, short_footnote: str,
                                     bibliography: str) -> bytes:
        """Create XML BLOB for CitationTable.Fields.

        Args:
            footnote: Footnote text for this citation
            short_footnote: Short footnote text
            bibliography: Bibliography text

        Returns:
            UTF-8 encoded XML BLOB
        """
        # Same structure as source fields for free-form citations
        return self._create_source_fields_blob(footnote, short_footnote, bibliography)

    # ==================== Ancestry Citation Building (Phase 1) ====================

    # NAID mappings for Collection 1002 (Fourth Registration, 1942)
    # "World War II Draft Cards (Fourth Registration) of [State]"
    # Source: https://www.ancestrylibrary.com/search/collections/1002/moreinfo
    # Note: Alabama, Florida, Georgia, Maine, Mississippi, New Mexico,
    #       North Carolina, South Carolina, and Tennessee are not in this collection.
    FOURTH_REGISTRATION_NAID_MAP = {
        "Alaska": "4504983",
        "Arizona": "7644722",
        "Arkansas": "576245",
        "California": "603155",
        "Colorado": "923647",
        "Connecticut": "2555449",
        "Delaware": "563726",
        "District of Columbia": "301658",
        "Hawaii": "78122510",
        "Idaho": "563870",
        "Illinois": "623284",
        "Indiana": "623285",
        "Iowa": "598910",
        "Kansas": "598909",
        "Kentucky": "7644731",
        "Louisiana": "576248",
        "Maryland": "563727",
        "Massachusetts": "78122507",
        "Michigan": "623283",
        "Minnesota": "598912",
        "Missouri": "598884",
        "Montana": "939368",
        "Nebraska": "598911",
        "Nevada": "78122509",
        "New Hampshire": "2555451",
        "New Jersey": "2555983",
        "New York City": "2555973",
        "New York State": "7644745",
        "North Dakota": "599221",
        "Ohio": "623234",
        "Oklahoma": "576250",
        "Oregon": "563991",
        "Pennsylvania": "563728",
        "Puerto Rico": "2555986",
        "Rhode Island": "2555453",
        "South Dakota": "599223",
        "Texas": "576252",
        "Utah": "939365",
        "Vermont": "2555452",
        "Virginia": "563732",
        "Washington": "563992",
        "West Virginia": "563733",
        "Wisconsin": "623273",
        "Wyoming": "939367",
    }

    # NAID (National Archives Identifier) mappings by state/territory
    # Collection 2238: "Draft Registration Cards for [State], 10/16/1940-03/31/1947"
    # Source: https://www.ancestrylibrary.com/search/collections/2238/moreinfo
    STATE_NAID_MAP = {
        "Alabama": "7644720",
        "Alaska": "2839217",
        "Arizona": "4684505",
        "Arkansas": "2169533",
        "California": "7644723",
        "Colorado": "5833895",
        "Connecticut": "7644724",
        "Delaware": "4656204",
        "Florida": "7644725",
        "Georgia": "78122503",
        "Hawaii": "7644726",
        "Idaho": "2838555",
        "Illinois": "7644727",
        "Indiana": "7644728",
        "Iowa": "7644729",
        "Kansas": "7644730",
        "Kentucky": "7644731",
        "Louisiana": "2169763",
        "Maryland": "2660907",
        "Massachusetts": "7644733",
        "Michigan": "7644734",
        "Minnesota": "7644735",
        "Mississippi": "7644736",
        "Missouri": "7644737",
        "Montana": "2838556",
        "Nebraska": "7644738",
        "Nevada": "7644739",
        "New Hampshire": "7644741",
        "New Jersey": "7644742",
        "New Mexico": "5721275",
        "New York State": "7644744",
        "New York City": "7644743",
        "North Carolina": "5557837",
        "North Dakota": "7644746",
        "Ohio": "7644747",
        "Oklahoma": "2169774",
        "Oregon": "2838557",
        "Pennsylvania": "5324575",
        "Rhode Island": "7644749",
        "South Carolina": "7644750",
        "South Dakota": "7644751",
        "Tennessee": "7644752",
        "Texas": "2169790",
        "Utah": "6002234",
        "Vermont": "7644753",
        "Virginia": "2645537",
        "Washington": "2838690",
        "West Virginia": "2658141",
        "Wisconsin": "7644756",
        "Wyoming": "4684507",
        "District of Columbia": "4693889",
        "Puerto Rico": "7644748",
        "Virgin Islands": "5752907",
    }

    # Collection title mapping for Ancestry collections
    ANCESTRY_COLLECTION_TITLES = {
        "2238": "U.S., World War II Draft Cards Young Men, 1940-1947",
        "1002": "U.S., World War II Draft Registration Cards, 1942",
    }

    @staticmethod
    def get_ancestry_collection_id(url: str) -> Optional[str]:
        """Extract collection ID from Ancestry URL."""
        match = re.search(r'/collections/(\d+)/', url)
        return match.group(1) if match else None

    @staticmethod
    def get_ancestry_collection_title(collection_id: str) -> Optional[str]:
        """Get collection title from collection ID."""
        return DraftCitationBuilder.ANCESTRY_COLLECTION_TITLES.get(collection_id)

    @staticmethod
    async def extract_source_citation_from_page(page: Page) -> Optional[str]:
        """
        Extract the "Source Citation" text from Ancestry record page.

        Args:
            page: Playwright Page object on Ancestry record page

        Returns:
            Source citation text or None if not found
        """
        try:
            # Look for "Source Citation" heading
            source_citation_heading = await page.query_selector("text=Source Citation")
            if not source_citation_heading:
                logger.warning("Source Citation heading not found on page")
                return None

            # Get parent element containing the citation text
            parent = await source_citation_heading.evaluate_handle("el => el.parentElement")
            citation_text = await parent.evaluate("el => el.textContent")

            # Clean up the text (remove heading and whitespace)
            citation_text = citation_text.replace("Source Citation", "").strip()

            logger.debug(f"Extracted Source Citation: {citation_text}")
            return citation_text

        except Exception as e:
            logger.error(f"Error extracting Source Citation: {e}")
            return None

    @staticmethod
    def parse_microfilm_title(source_citation: str) -> Optional[str]:
        """
        Extract series title from Ancestry Source Citation text.

        Handles two collection formats:
        - Collection 2238 (Young Men): "Draft Registration Cards For Ohio, 10/16/1940-03/31/1947"
        - Collection 1002 (Fourth Registration): "World War II Draft Cards (Fourth Registration) of Pennsylvania"

        Example input:
            "National Archives at St. Louis; St. Louis, Missouri; Draft Registration Cards For Ohio, 10/16/1940-03/31/1947; Record Group: Records of the Selective Service System, 147; Box: 686"

        Args:
            source_citation: Full source citation text from Ancestry record page

        Returns:
            Series title or None if not found
        """
        parts = [p.strip() for p in source_citation.split(';')]

        for part in parts:
            # Collection 2238: "Draft Registration Cards For/for [State], [dates]"
            if "Draft Registration Cards" in part:
                return part
            # Collection 1002: "World War II Draft Cards (Fourth Registration) of/For [State]"
            if "World War II Draft Cards" in part:
                return part
            # Collection 1002 variant: "Wwii Draft Cards (Fourth Registration) For the State of [State]"
            if "Wwii Draft Cards" in part:
                return part

        logger.warning(f"Could not find series title in: {source_citation}")
        return None

    @staticmethod
    def parse_state_from_microfilm_title(microfilm_title: str) -> Optional[str]:
        """
        Extract state/territory name from series title.

        Handles:
        - Collection 2238: "Draft Registration Cards For Ohio, 10/16/1940-03/31/1947"
        - Collection 2238 NYC: "Draft Registration Cards for New York City, 10/16/1940 - 03/31/1947"
        - Collection 1002: "World War II Draft Cards (Fourth Registration) of Pennsylvania"
        - Collection 1002 variant: "World War II Draft Cards (Fourth Registration) For the State of Maryland"

        Args:
            microfilm_title: Series title from Ancestry Source Citation

        Returns:
            State/territory name or None if not found
        """
        # Collection 2238: "Draft Registration Cards [For|for] [State], [dates]"
        match = re.search(r'Draft Registration Cards [Ff]or (.+?),\s*\d{2}/\d{2}/\d{4}', microfilm_title)
        if match:
            state = match.group(1).strip()
            logger.debug(f"Extracted state from collection 2238 title: {state}")
            return state

        # Collection 1002 variants: various "(Fourth Registration)" and "(4th Registration)" formats
        # Handles "of [State]", "For the State of [State]", and comma-separated ", For the State of [State]"
        match = re.search(
            r'(?:World War II|Wwii) Draft Cards \((?:Fourth|4th) Registration\)[,]?\s*(?:For the State of|of)\s+(.+)',
            microfilm_title,
            re.IGNORECASE,
        )
        if match:
            state = match.group(1).strip()
            logger.debug(f"Extracted state from collection 1002 title: {state}")
            return state

        logger.warning(f"Could not extract state from title: {microfilm_title}")
        return None

    @staticmethod
    def construct_series_title(state: str, collection_id: str) -> str:
        """
        Construct a standard series title from state and collection ID.

        Used as a fallback when the series title cannot be parsed from the
        Ancestry Source Citation (e.g. when the page returns an abbreviated
        citation without the series title).

        Args:
            state: State/territory name (e.g. "Ohio", "Pennsylvania")
            collection_id: Ancestry collection ID ("1002" or "2238")

        Returns:
            Standard series title string
        """
        if collection_id == "1002":
            return f"World War II Draft Cards (Fourth Registration) of {state}"
        else:  # 2238
            return f"Draft Registration Cards for {state}"

    @staticmethod
    def get_naid_for_state(state: str, collection_id: str = "2238") -> Optional[str]:
        """Lookup NAID for a state/territory by collection.

        Args:
            state: State/territory name (e.g., "Ohio", "Pennsylvania")
            collection_id: Ancestry collection ID ("2238" for Young Men, "1002" for Fourth Registration)

        Returns:
            NAID string or None if not found
        """
        if collection_id == "1002":
            # "New York" on its own maps to the statewide series (not NYC)
            normalized = "New York State" if state == "New York" else state
            return DraftCitationBuilder.FOURTH_REGISTRATION_NAID_MAP.get(normalized)
        return DraftCitationBuilder.STATE_NAID_MAP.get(state)

    @staticmethod
    def build_source_name(surname: str, given_name: str,
                          birth_year: Optional[int], death_year: Optional[int]) -> str:
        """Build a person-specific source name for WW2 draft records.

        Format: "Military Records: World War II, Draft - Surname, GivenName (birth-death)"

        Args:
            surname: Person's surname
            given_name: Person's given name(s)
            birth_year: Year of birth (or None)
            death_year: Year of death (or None)

        Returns:
            Formatted source name string
        """
        birth_str = str(birth_year) if birth_year else ""
        death_str = str(death_year) if death_year else ""
        years = f"({birth_str}-{death_str})" if (birth_str or death_str) else ""
        name_part = f"{surname}, {given_name}".strip(", ")
        parts = [f"Military Records: World War II, Draft - {name_part}"]
        if years:
            parts.append(years)
        return " ".join(parts)

    @staticmethod
    def normalize_height(raw: Optional[str]) -> str:
        """Normalize height to standard format: 5' 10" or 5' 8½" or n/a.

        Handles formats found on Ancestry and FamilySearch draft cards:
          "5 10", "5'10"", "5-11", "5ft 10", "5 Ft 9 in", "5 8½", "5'-8½""
        Text fractions (1/4, 1/2, 3/4) are converted to Unicode (¼, ½, ¾).
        Feet-only input (e.g. "5'") becomes 5' 0".
        None or unrecognizable input becomes n/a.
        """
        if not raw or not raw.strip():
            return "n/a"

        s = raw.strip()

        # Convert text fractions to unicode before any other processing
        for text, char in [("1/4", "¼"), ("1/2", "½"), ("3/4", "¾")]:
            s = s.replace(text, char)

        # Extract unicode fraction (¼ ½ ¾) — remove it from string for numeric parsing
        fraction = ""
        for ch in ("¼", "½", "¾"):
            if ch in s:
                fraction = ch
                s = s.replace(ch, "")
                break

        # Remove word markers (handles both attached "5ft" and spaced "5 Ft")
        s = re.sub(r"(?i)(feet|foot|ft)", " ", s)
        s = re.sub(r"(?i)(inches|inch)", " ", s)
        s = re.sub(r"(?i)\bin\b", " ", s)

        # Remove punctuation used as separators (apostrophe, quote, hyphen)
        s = re.sub(r"['\"\-]", " ", s)

        # Extract all integer tokens
        numbers = re.findall(r"\d+", s)

        if not numbers:
            return "n/a"

        try:
            feet = int(numbers[0])
            inches = int(numbers[1]) if len(numbers) > 1 else 0
        except (ValueError, IndexError):
            return "n/a"

        # Sanity-check: reasonable human height range
        if not (3 <= feet <= 7) or not (0 <= inches <= 11):
            return "n/a"

        return f"{feet}' {inches}{fraction}\""

    @staticmethod
    def format_access_date(iso_datetime: str) -> str:
        """
        Format ISO datetime to Evidence Explained access date format.

        Args:
            iso_datetime: ISO format datetime (e.g., "2026-02-12T14:23:45")

        Returns:
            Formatted date (e.g., "12 February 2026")
        """
        try:
            dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
            return dt.strftime("%-d %B %Y")
        except Exception as e:
            logger.error(f"Error formatting date {iso_datetime}: {e}")
            return iso_datetime

    def build_ancestry_footnote(
        self,
        collection_title: str,
        url: str,
        access_date: str,
        person_name: str,
        series_title: str,
        naid: str,
    ) -> str:
        """Build Evidence Explained footnote citation for Ancestry.

        Format:
            "[Collection Title]," database with images, <i>Ancestry</i> ([URL] : accessed [Date]),
            draft card for [Name]; citing Records of the Selective Service System
            (Record Group 147), <i>[Series Title]</i>, National Archives Identifier (NAID) [NAID]
            (St. Louis, Missouri: National Archives at St. Louis, n.d.).
        """
        return (
            f'"{collection_title}," database with images, <i>Ancestry</i> '
            f'({url} : accessed {access_date}), draft card for {person_name}; '
            f'citing Records of the Selective Service System (Record Group 147), '
            f'<i>{series_title}</i>, National Archives Identifier (NAID) {naid} '
            f'(St. Louis, Missouri: National Archives at St. Louis, n.d.).'
        )

    def build_ancestry_short_footnote(
        self,
        collection_title: str,
        person_name: str,
    ) -> str:
        """Build Evidence Explained short footnote citation for Ancestry."""
        return (
            f'"{collection_title}," database with images, <i>Ancestry</i>, '
            f'draft card for {person_name}.'
        )

    def build_ancestry_bibliography(
        self,
        collection_title: str,
        url: str,
        access_date: str,
        series_title: str,
        naid: str,
    ) -> str:
        """Build Evidence Explained bibliography citation for Ancestry.

        Format:
            "[Collection Title]." Database with images. Ancestry. [Collection URL].
            Accessed [Date]. Citing Records of the Selective Service System (Record Group 147),
            <i>[Series Title]</i>, National Archives Identifier (NAID) [NAID].
            St. Louis, Missouri: National Archives at St. Louis, n.d.
        """
        # Extract base URL (collection level, not record level)
        collection_url_match = re.search(r'(https://[^/]+/search/collections/\d+)', url)
        collection_url = collection_url_match.group(1) if collection_url_match else url

        return (
            f'"{collection_title}." Database with images. Ancestry. {collection_url}. '
            f'Accessed {access_date}. Citing Records of the Selective Service System '
            f'(Record Group 147), <i>{series_title}</i>, National Archives Identifier (NAID) '
            f'{naid}. St. Louis, Missouri: National Archives at St. Louis, n.d.'
        )

    async def build_ancestry_citations(
        self,
        page: Optional[Page],
        url: str,
        person_name: str,
        extracted_at: str,
        state_fallback: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], list[str]]:
        """
        Build all three citation formats for an Ancestry draft record.

        Args:
            page: Playwright Page object on Ancestry record page (may be None when
                  using state_fallback for offline/backfill citation building)
            url: Full Ancestry record URL
            person_name: Person's name as scraped from Ancestry
            extracted_at: ISO datetime when record was scraped
            state_fallback: State name to use when page-based extraction fails or
                            page is unavailable (e.g. "Ohio", "Pennsylvania")

        Returns:
            Tuple of (footnote, short_footnote, bibliography, warnings)
            Any field may be None if citation building failed
            warnings is a list of warning messages
        """
        warnings = []

        # Step 1: Get collection ID and title
        collection_id = self.get_ancestry_collection_id(url)
        if not collection_id:
            warnings.append("Could not extract collection ID from URL")
            return None, None, None, warnings

        collection_title = self.get_ancestry_collection_title(collection_id)
        if not collection_title:
            warnings.append(f"Unknown collection ID: {collection_id}")
            return None, None, None, warnings

        state = None
        microfilm_title = None

        # Step 2: Try page-based extraction when a page is available
        if page is not None:
            source_citation = await self.extract_source_citation_from_page(page)
            if not source_citation:
                warnings.append("Could not extract Source Citation from page")
            else:
                # Step 3: Parse microfilm title
                microfilm_title = self.parse_microfilm_title(source_citation)
                if not microfilm_title:
                    warnings.append("Could not parse microfilm title from Source Citation")
                else:
                    # Step 4: Parse state from microfilm title
                    state = self.parse_state_from_microfilm_title(microfilm_title)
                    if not state:
                        warnings.append("Could not extract state from microfilm title")

        # Fallback: use provided state when page extraction was unavailable or failed
        if state is None and state_fallback:
            state = state_fallback
            microfilm_title = self.construct_series_title(state, collection_id)
            warnings.append(f"Used residence-state fallback: {state}")
            logger.info(f"Citation state fallback applied: {state} (collection {collection_id})")

        if state is None:
            warnings.append("Citation incomplete: could not determine state")
            return None, None, None, warnings

        # Step 5: Lookup NAID (collection-specific)
        naid = self.get_naid_for_state(state, collection_id)
        if not naid:
            warnings.append(
                f"No NAID mapping found for state '{state}' in collection {collection_id}. "
                f"Add it to {'FOURTH_REGISTRATION_NAID_MAP' if collection_id == '1002' else 'STATE_NAID_MAP'}."
            )

        # If we don't have NAID, we can't build complete citations
        if not naid:
            warnings.append("Citation incomplete: missing NAID")
            return None, None, None, warnings

        # Step 6: Format access date
        access_date = self.format_access_date(extracted_at)

        # Step 7: Normalize series title
        # Ancestry capitalizes "For" in collection 2238 titles; citations use lowercase "for"
        series_title = microfilm_title.replace("For ", "for ", 1)

        # Step 8: Build citations
        try:
            footnote = self.build_ancestry_footnote(
                collection_title, url, access_date, person_name, series_title, naid
            )
            short_footnote = self.build_ancestry_short_footnote(collection_title, person_name)
            bibliography = self.build_ancestry_bibliography(
                collection_title, url, access_date, series_title, naid
            )

            return footnote, short_footnote, bibliography, warnings

        except Exception as e:
            logger.error(f"Error building citations: {e}")
            warnings.append(f"Error building citations: {e}")
            return None, None, None, warnings
