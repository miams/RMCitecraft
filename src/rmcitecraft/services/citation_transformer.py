"""Citation transformer for Evidence Explained compliance.

This module transforms footnotes into short footnotes and bibliographies
following Evidence Explained citation style guidelines.

Transformation rules:
- Short footnote: Abbreviate state names, locality types, omit source/access info
- Bibliography: Reorder to Location. Collection. Title. Publisher. URL : year.
"""

import re
from dataclasses import dataclass
from typing import Optional

from rmcitecraft.config.constants import (
    LOCALITY_TYPE_ABBREVIATIONS,
    STATE_ABBREVIATIONS,
)


@dataclass
class TransformationResult:
    """Result of a citation transformation."""
    original: str
    transformed: str
    confidence: float  # 0.0 to 1.0
    source_type: str
    transformation_type: str  # 'fn_to_sf' or 'fn_to_bib'
    notes: list[str]  # Transformation notes/warnings

    @property
    def success(self) -> bool:
        return self.confidence >= 0.5


# Common abbreviations for short footnotes (Evidence Explained style)
SHORT_FOOTNOTE_ABBREVIATIONS = {
    # Schedule types
    'population schedule': 'pop. sch.',
    'Population Schedule': 'pop. sch.',
    'slave schedule': 'slave sch.',
    'Slave Schedule': 'slave sch.',
    'mortality schedule': 'mort. sch.',
    'Mortality Schedule': 'mort. sch.',
    # Location elements
    'County': 'Co.',
    'enumeration district (ED)': 'E.D.',
    'enumeration district': 'E.D.',
    # Common terms
    'page': 'p.',
    'line': 'line',  # Keep 'line' as is
    'sheet': 'sheet',  # Keep 'sheet' as is
    'stamp': 'stamp',  # Keep 'stamp' as is
}


class CitationTransformer:
    """Transform footnotes to short footnotes and bibliographies.

    This class applies Evidence Explained transformation rules to convert
    full footnotes into abbreviated short footnotes and restructured
    bibliographies.
    """

    def __init__(self):
        """Initialize the transformer."""
        self.state_abbrevs = STATE_ABBREVIATIONS
        self.locality_abbrevs = LOCALITY_TYPE_ABBREVIATIONS
        self.sf_abbrevs = SHORT_FOOTNOTE_ABBREVIATIONS

    def detect_source_type(self, text: str) -> str:
        """Detect the source type from citation text.

        Args:
            text: The footnote or citation text

        Returns:
            Source type string (e.g., 'census', 'findagrave', 'military', 'book')
        """
        text_lower = text.lower()

        # Census patterns
        if re.search(r'\d{4}\s+u\.?s\.?\s+census', text_lower):
            return 'census'

        # Find a Grave
        if 'find a grave' in text_lower or 'findagrave' in text_lower:
            return 'findagrave'

        # Military records
        if any(kw in text_lower for kw in ['draft registration', 'military', 'war department',
                                            'national archives', 'nara', 'wwi', 'wwii', 'civil war']):
            return 'military'

        # Death records
        if any(kw in text_lower for kw in ['death certificate', 'death record', 'vital records',
                                            'certificate of death']):
            return 'death_record'

        # Marriage records
        if any(kw in text_lower for kw in ['marriage', 'married', 'wedding']):
            return 'marriage'

        # Books/publications
        if re.search(r'\([^)]+:\s*[^,]+,\s*\d{4}\)', text):  # (Place: Publisher, Year) pattern
            return 'book'

        # Website/online
        if 'http' in text_lower or 'accessed' in text_lower:
            return 'website'

        return 'unknown'

    def extract_census_year(self, text: str) -> Optional[int]:
        """Extract census year from footnote text.

        Args:
            text: The footnote text

        Returns:
            Census year as integer, or None if not found
        """
        match = re.search(r'(\d{4})\s+U\.?S\.?\s+census', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def extract_person_name(self, text: str) -> Optional[str]:
        """Extract the person name from a footnote.

        Person name typically appears before the semicolon in census footnotes:
        "..., line 15, John Smith; imaged, ..."

        Args:
            text: The footnote text

        Returns:
            Person name, or None if not found
        """
        # Pattern: ", NAME; imaged" or ", NAME; digital"
        match = re.search(r',\s+([A-Z][^;,]+?)\s*;\s*(?:imaged|digital)', text)
        if match:
            return match.group(1).strip()

        # Alternative pattern: at end before period
        match = re.search(r',\s+([A-Z][^;,]+?)\s*\.\s*$', text)
        if match:
            return match.group(1).strip()

        return None

    def abbreviate_state(self, state: str) -> str:
        """Abbreviate a state name for short footnotes.

        Args:
            state: Full state name (e.g., "Pennsylvania")

        Returns:
            Abbreviated state name (e.g., "Pa.")
        """
        return self.state_abbrevs.get(state, state)

    def abbreviate_locality_type(self, locality: str) -> str:
        """Abbreviate locality type suffix.

        Args:
            locality: Locality name with type (e.g., "Southampton Township")

        Returns:
            Locality with abbreviated type (e.g., "Southampton Twp.")
        """
        for locality_type, abbrev in self.locality_abbrevs.items():
            if locality.endswith(f" {locality_type}"):
                return locality[:-len(locality_type)] + abbrev
        return locality

    def generate_short_footnote(self, footnote: str, source_type: str = 'auto') -> TransformationResult:
        """Transform a full footnote into a short footnote.

        Short footnotes use abbreviations and omit source/access information.

        Args:
            footnote: The full footnote text
            source_type: Source type or 'auto' to detect

        Returns:
            TransformationResult with the short footnote
        """
        if source_type == 'auto':
            source_type = self.detect_source_type(footnote)

        notes: list[str] = []
        confidence = 1.0

        if source_type == 'census':
            result = self._transform_census_to_short_footnote(footnote)
            return TransformationResult(
                original=footnote,
                transformed=result['text'],
                confidence=result['confidence'],
                source_type=source_type,
                transformation_type='fn_to_sf',
                notes=result['notes']
            )

        elif source_type == 'findagrave':
            # Find a Grave short footnotes are typically similar to full
            # Just abbreviate state names
            short_fn = self._abbreviate_states_in_text(footnote)
            # Remove "digital images" portion after semicolon
            if ';' in short_fn:
                short_fn = short_fn.split(';')[0].strip()
                if not short_fn.endswith('.'):
                    short_fn += '.'

            return TransformationResult(
                original=footnote,
                transformed=short_fn,
                confidence=0.8,
                source_type=source_type,
                transformation_type='fn_to_sf',
                notes=['Removed digital images portion']
            )

        else:
            # Generic transformation: abbreviate states, remove after semicolon
            short_fn = self._abbreviate_states_in_text(footnote)

            # Try to remove source information after semicolon
            if ';' in short_fn:
                short_fn = short_fn.split(';')[0].strip()
                if not short_fn.endswith('.'):
                    short_fn += '.'
                notes.append('Removed source info after semicolon')
            else:
                notes.append('No semicolon found, minimal transformation')
                confidence = 0.5

            return TransformationResult(
                original=footnote,
                transformed=short_fn,
                confidence=confidence,
                source_type=source_type,
                transformation_type='fn_to_sf',
                notes=notes
            )

    def _transform_census_to_short_footnote(self, footnote: str) -> dict:
        """Transform a census footnote to short footnote.

        Args:
            footnote: Full census footnote

        Returns:
            Dict with 'text', 'confidence', and 'notes'
        """
        notes: list[str] = []
        confidence = 1.0

        # Extract census year
        year = self.extract_census_year(footnote)
        if not year:
            return {
                'text': footnote,
                'confidence': 0.3,
                'notes': ['Could not extract census year']
            }

        # Extract person name
        person_name = self.extract_person_name(footnote)
        if not person_name:
            notes.append('Could not extract person name')
            confidence -= 0.2

        # Start with text before semicolon
        if ';' in footnote:
            core_text = footnote.split(';')[0].strip()
        else:
            core_text = footnote.strip()
            notes.append('No semicolon delimiter found')
            confidence -= 0.1

        # Apply abbreviations
        short_fn = core_text

        # State abbreviations
        for state, abbrev in self.state_abbrevs.items():
            short_fn = short_fn.replace(f", {state}", f", {abbrev}")
            short_fn = short_fn.replace(f" {state},", f" {abbrev},")

        # County abbreviation
        short_fn = re.sub(r'(\w+)\s+County', r'\1 Co.', short_fn)

        # Locality type abbreviations
        for locality_type, abbrev in self.locality_abbrevs.items():
            short_fn = re.sub(rf'\b{locality_type}\b', abbrev, short_fn)

        # Schedule type abbreviations
        # Rules: 1910-1940 omit "pop. sch." (only population schedules survived)
        if 1910 <= year <= 1940:
            short_fn = re.sub(r',?\s*population schedule\s*,?', ', ', short_fn, flags=re.IGNORECASE)
        else:
            short_fn = re.sub(r'population schedule', 'pop. sch.', short_fn, flags=re.IGNORECASE)

        short_fn = re.sub(r'slave schedule', 'slave sch.', short_fn, flags=re.IGNORECASE)
        short_fn = re.sub(r'mortality schedule', 'mort. sch.', short_fn, flags=re.IGNORECASE)

        # ED abbreviation
        short_fn = re.sub(r'enumeration district \(ED\)', 'E.D.', short_fn)
        short_fn = re.sub(r'enumeration district', 'E.D.', short_fn)

        # Page abbreviation for pre-1880
        if year < 1880:
            short_fn = re.sub(r'\bpage\b', 'p.', short_fn)

        # Clean up multiple commas/spaces
        short_fn = re.sub(r',\s*,', ',', short_fn)
        short_fn = re.sub(r'\s+', ' ', short_fn)

        # Ensure ends with period
        short_fn = short_fn.rstrip()
        if not short_fn.endswith('.'):
            short_fn += '.'

        return {
            'text': short_fn,
            'confidence': confidence,
            'notes': notes
        }

    def _abbreviate_states_in_text(self, text: str) -> str:
        """Abbreviate all state names in text.

        Args:
            text: Text containing state names

        Returns:
            Text with abbreviated state names
        """
        result = text
        for state, abbrev in self.state_abbrevs.items():
            result = result.replace(f", {state},", f", {abbrev},")
            result = result.replace(f", {state} ", f", {abbrev} ")
            result = result.replace(f" {state},", f" {abbrev},")
        return result

    def generate_bibliography(self, footnote: str, source_type: str = 'auto') -> TransformationResult:
        """Transform a footnote into a bibliography entry.

        Bibliography entries restructure the citation to:
        Location. Collection. "Title." Publisher. URL : year.

        Args:
            footnote: The full footnote text
            source_type: Source type or 'auto' to detect

        Returns:
            TransformationResult with the bibliography entry
        """
        if source_type == 'auto':
            source_type = self.detect_source_type(footnote)

        if source_type == 'census':
            return self._transform_census_to_bibliography(footnote)

        elif source_type == 'findagrave':
            return self._transform_findagrave_to_bibliography(footnote)

        else:
            # Generic bibliography: keep most info but remove person-specific details
            notes: list[str] = ['Generic transformation applied']
            bib = footnote

            # Remove person name (typically after last comma before semicolon)
            if ';' in bib:
                parts = bib.split(';')
                first_part = parts[0]
                rest = ';'.join(parts[1:])

                # Try to remove person name from first part
                if ',' in first_part:
                    segments = first_part.rsplit(',', 1)
                    # Check if last segment looks like a name
                    last_segment = segments[1].strip()
                    if re.match(r'^[A-Z][a-z]+\s+[A-Z]', last_segment):
                        first_part = segments[0]
                        notes.append('Removed person name')

                bib = first_part + ';' + rest

            return TransformationResult(
                original=footnote,
                transformed=bib,
                confidence=0.5,
                source_type=source_type,
                transformation_type='fn_to_bib',
                notes=notes
            )

    def _transform_census_to_bibliography(self, footnote: str) -> TransformationResult:
        """Transform a census footnote to bibliography.

        Args:
            footnote: Full census footnote

        Returns:
            TransformationResult with bibliography entry
        """
        notes: list[str] = []
        confidence = 0.9

        year = self.extract_census_year(footnote)
        if not year:
            return TransformationResult(
                original=footnote,
                transformed=footnote,
                confidence=0.3,
                source_type='census',
                transformation_type='fn_to_bib',
                notes=['Could not extract census year']
            )

        # Try to extract state and county
        state_match = re.search(
            r'census,\s+([A-Za-z\s]+)\s+County,\s+([A-Za-z\s]+)',
            footnote,
            re.IGNORECASE
        )

        if not state_match:
            # Try alternative pattern
            state_match = re.search(
                r'census,\s+([A-Za-z\s]+),\s+([A-Za-z\s]+)',
                footnote,
                re.IGNORECASE
            )

        county = state_match.group(1).strip() if state_match else '[County]'
        state = state_match.group(2).strip() if state_match else '[State]'

        # Clean up county name (remove "County" suffix if present)
        county = re.sub(r'\s+County$', '', county, flags=re.IGNORECASE)

        # Determine schedule type inclusion
        # 1910-1940: omit "Population Schedule" (only type that survived)
        # Other years: include it
        if 1910 <= year <= 1940:
            schedule_str = ""
        else:
            schedule_str = "Population Schedule. "

        # Extract URL
        url_match = re.search(r'(https?://[^\s)]+)', footnote)
        url = url_match.group(1) if url_match else '[URL]'

        # Clean URL (remove query params)
        if '?' in url:
            url = url.split('?')[0]

        # Extract access year
        access_match = re.search(r'accessed\s+\d+\s+\w+\s+(\d{4})', footnote)
        access_year = access_match.group(1) if access_match else str(year)

        # Build bibliography
        bibliography = (
            f"U.S. {state}. {county} County. "
            f"{year} U.S Census. {schedule_str}"
            f"Imaged. \"United States, Census, {year}.\" <i>FamilySearch</i>. "
            f"{url} : {access_year}."
        )

        return TransformationResult(
            original=footnote,
            transformed=bibliography,
            confidence=confidence,
            source_type='census',
            transformation_type='fn_to_bib',
            notes=notes
        )

    def _transform_findagrave_to_bibliography(self, footnote: str) -> TransformationResult:
        """Transform a Find a Grave footnote to bibliography.

        Args:
            footnote: Find a Grave footnote

        Returns:
            TransformationResult with bibliography entry
        """
        # Find a Grave bibliographies are typically:
        # "Find A Grave." Database with images. https://www.findagrave.com : accessed YEAR.

        url_match = re.search(r'(https?://[^\s)]+findagrave[^\s)]*)', footnote)
        url = url_match.group(1) if url_match else 'https://www.findagrave.com'

        access_match = re.search(r'accessed\s+\d+\s+\w+\s+(\d{4})', footnote)
        if not access_match:
            access_match = re.search(r'(\d{4})', footnote)
        access_year = access_match.group(1) if access_match else '[year]'

        bibliography = (
            '"Find A Grave." Database with images. '
            f'{url.split("?")[0]} : {access_year}.'
        )

        return TransformationResult(
            original=footnote,
            transformed=bibliography,
            confidence=0.85,
            source_type='findagrave',
            transformation_type='fn_to_bib',
            notes=['Standard Find a Grave bibliography format']
        )

    def transform_all(self, footnote: str, source_type: str = 'auto') -> dict:
        """Generate both short footnote and bibliography from a footnote.

        Args:
            footnote: The full footnote text
            source_type: Source type or 'auto' to detect

        Returns:
            Dictionary with 'short_footnote' and 'bibliography' TransformationResults
        """
        if source_type == 'auto':
            source_type = self.detect_source_type(footnote)

        return {
            'source_type': source_type,
            'short_footnote': self.generate_short_footnote(footnote, source_type),
            'bibliography': self.generate_bibliography(footnote, source_type),
        }


def transform_citation(
    footnote: str,
    transformation_type: str = 'both',
    source_type: str = 'auto'
) -> dict:
    """Convenience function to transform a citation.

    Args:
        footnote: The full footnote text
        transformation_type: 'short_footnote', 'bibliography', or 'both'
        source_type: Source type or 'auto' to detect

    Returns:
        Dictionary with transformation results
    """
    transformer = CitationTransformer()

    if transformation_type == 'short_footnote':
        result = transformer.generate_short_footnote(footnote, source_type)
        return {'short_footnote': result}

    elif transformation_type == 'bibliography':
        result = transformer.generate_bibliography(footnote, source_type)
        return {'bibliography': result}

    else:  # 'both'
        return transformer.transform_all(footnote, source_type)
