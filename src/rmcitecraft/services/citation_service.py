"""Citation generation service orchestrating extraction and formatting.

This service coordinates the two-phase citation processing:
1. LLM extraction of structured data from FamilySearch citations
2. Template-based formatting into Evidence Explained format
"""

import sqlite3
from typing import Any

from loguru import logger

from rmcitecraft.models.census_citation import (
    CensusCitation,
    PlaceDetails,
)
from rmcitecraft.services.citation_formatter import format_census_citation
from rmcitecraft.services.llm_extractor import LLMCitationExtractor


class CitationGenerationService:
    """Service for generating Evidence Explained citations from RootsMagic data."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-3-5-sonnet-20250110",
        llm_api_key: str | None = None,
    ):
        """Initialize citation generation service.

        Args:
            db_connection: RootsMagic database connection (with ICU extension loaded)
            llm_provider: LLM provider for extraction
            llm_model: Model name
            llm_api_key: API key (optional if in environment)
        """
        self.conn = db_connection
        self.extractor = LLMCitationExtractor(llm_provider, llm_model, llm_api_key)

    def get_citation_data(self, citation_id: int) -> dict[str, Any]:
        """Fetch all data needed for citation generation from database.

        Args:
            citation_id: RootsMagic CitationID

        Returns:
            Dictionary with source_name, familysearch_entry, place_string,
            source_id, event_id, person_id

        Raises:
            ValueError: If citation not found or missing required data
        """
        cursor = self.conn.cursor()

        # Get citation and source data
        cursor.execute(
            """
            SELECT
                c.CitationID,
                c.SourceID,
                c.Fields as citation_fields,
                s.Name as source_name,
                s.Fields as source_fields
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE c.CitationID = ?
            """,
            (citation_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Citation {citation_id} not found")

        citation_id, source_id, citation_fields, source_name, source_fields = row

        # Parse FamilySearch entry from CitationTable.Fields BLOB (Page field)
        familysearch_entry = self._extract_field_from_blob(citation_fields, "Page")
        if not familysearch_entry:
            raise ValueError(
                f"Citation {citation_id} has no FamilySearch entry in Page field"
            )

        # Get event and place data
        cursor.execute(
            """
            SELECT
                e.EventID,
                e.OwnerID as person_id,
                p.Name as place_string
            FROM EventTable e
            JOIN PlaceTable p ON e.PlaceID = p.PlaceID
            WHERE e.EventID IN (
                SELECT LinkID FROM CitationLinkTable
                WHERE CitationID = ? AND OwnerType = 2
            )
            LIMIT 1
            """,
            (citation_id,),
        )

        event_row = cursor.fetchone()
        if not event_row:
            raise ValueError(f"No event linked to citation {citation_id}")

        event_id, person_id, place_string = event_row

        return {
            "citation_id": citation_id,
            "source_id": source_id,
            "source_name": source_name,
            "familysearch_entry": familysearch_entry,
            "place_string": place_string,
            "event_id": event_id,
            "person_id": person_id,
        }

    def generate_citation(
        self, citation_id: int, user_corrections: dict[str, str] | None = None
    ) -> CensusCitation:
        """Generate Evidence Explained citation for a census record.

        This is the main entry point for citation generation.

        Args:
            citation_id: RootsMagic CitationID
            user_corrections: Optional dict of field corrections for missing/incomplete data
                             (e.g., {"enumeration_district": "30-17"})

        Returns:
            CensusCitation with all three formatted citations

        Raises:
            ValueError: If extraction fails or required data is missing
        """
        logger.info(f"Generating citation for CitationID {citation_id}")

        # Phase 1: Fetch data from database
        data = self.get_citation_data(citation_id)

        # Phase 2: LLM extraction
        extraction = self.extractor.extract_citation(
            data["source_name"], data["familysearch_entry"]
        )

        # Phase 3: Apply user corrections for missing/incomplete fields
        if user_corrections:
            for field, value in user_corrections.items():
                if hasattr(extraction, field):
                    setattr(extraction, field, value)
                    logger.info(f"Applied user correction: {field} = {value}")

        # Phase 4: Parse place details
        place = PlaceDetails.from_place_string(data["place_string"])

        # Phase 5: Validate we have all required data
        if extraction.missing_fields and not user_corrections:
            missing = ", ".join(extraction.missing_fields)
            logger.warning(
                f"Citation has missing fields: {missing}. "
                f"Pass user_corrections to fill these fields."
            )
            # Continue anyway - formatter will handle missing optional fields

        # Phase 6: Generate all three citation formats
        citation = format_census_citation(
            extraction=extraction,
            place=place,
            citation_id=data["citation_id"],
            source_id=data["source_id"],
            event_id=data["event_id"],
            person_id=data["person_id"],
        )

        logger.info(
            f"Generated citation for {extraction.person_name}, "
            f"{extraction.year} census in {place.county}, {place.state}"
        )

        return citation

    def write_citation_to_database(self, citation: CensusCitation) -> None:
        """Write generated citation to SourceTable.Fields BLOB.

        For free-form sources (TemplateID=0), all three citation formats are
        stored in SourceTable.Fields BLOB as XML.

        Args:
            citation: Generated CensusCitation

        Raises:
            sqlite3.Error: If database write fails
        """
        cursor = self.conn.cursor()

        # Read existing Fields BLOB
        cursor.execute(
            "SELECT Fields FROM SourceTable WHERE SourceID = ?", (citation.source_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Source {citation.source_id} not found")

        existing_fields = row[0] if row[0] else b""

        # Build new Fields BLOB with all three citations
        new_fields = self._build_source_fields_blob(
            existing_fields,
            footnote=citation.footnote,
            short_footnote=citation.short_footnote,
            bibliography=citation.bibliography,
        )

        # Update SourceTable.Fields
        cursor.execute(
            "UPDATE SourceTable SET Fields = ? WHERE SourceID = ?",
            (new_fields, citation.source_id),
        )

        self.conn.commit()
        logger.info(f"Wrote citation to database for SourceID {citation.source_id}")

    @staticmethod
    def _extract_field_from_blob(blob: bytes | None, field_name: str) -> str | None:
        """Extract field value from XML BLOB.

        Args:
            blob: XML BLOB from Fields column
            field_name: Field name to extract (e.g., "Page")

        Returns:
            Field value or None if not found
        """
        if not blob:
            return None

        # Simple XML parsing (RootsMagic uses straightforward XML)
        xml_str = blob.decode("utf-8")
        start_tag = f"<{field_name}>"
        end_tag = f"</{field_name}>"

        start_idx = xml_str.find(start_tag)
        if start_idx == -1:
            return None

        start_idx += len(start_tag)
        end_idx = xml_str.find(end_tag, start_idx)

        if end_idx == -1:
            return None

        return xml_str[start_idx:end_idx].strip()

    @staticmethod
    def _build_source_fields_blob(
        existing_blob: bytes,
        footnote: str,
        short_footnote: str,
        bibliography: str,
    ) -> bytes:
        """Build SourceTable.Fields BLOB with all three citation formats.

        Args:
            existing_blob: Existing Fields BLOB (may be empty)
            footnote: Full Evidence Explained footnote
            short_footnote: Short footnote
            bibliography: Bibliography entry

        Returns:
            New Fields BLOB as bytes
        """
        # Build XML structure for free-form source (TemplateID=0)
        xml = f"""<Root>
<Fields>
<Field>
<Name>Footnote</Name>
<Value>{footnote}</Value>
</Field>
<Field>
<Name>ShortFootnote</Name>
<Value>{short_footnote}</Value>
</Field>
<Field>
<Name>Bibliography</Name>
<Value>{bibliography}</Value>
</Field>
</Fields>
</Root>"""

        return xml.encode("utf-8")
