"""Census Form Data Service.

Loads census data from census.db and converts it to form rendering models.
This service bridges the database layer (census_extraction_db.py) with the
presentation layer (Jinja2 templates).

Architecture:
- Loads raw data from CensusExtractionRepository
- Transforms to CensusFormContext for template rendering
- Applies schema-driven column definitions
- Groups persons into households
- Attaches quality metadata from field_quality table
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from rmcitecraft.database.census_extraction_db import (
    CENSUS_DB_PATH,
    CensusExtractionRepository,
    CensusPage,
    CensusPerson,
    FieldQuality,
)
from rmcitecraft.models.census_form_data import (
    CensusFormContext,
    FieldQualityLevel,
    FieldValue,
    FormColumnDef,
    FormHousehold,
    FormPageData,
    FormPersonRow,
    get_columns_for_year,
)


# Sample line numbers for 1950 census (lines 1, 6, 11, 16, 21, 26)
SAMPLE_LINES_1950 = {1, 6, 11, 16, 21, 26}


class CensusFormDataService:
    """Service for loading and transforming census data for form rendering."""

    def __init__(self, db_path: Path | None = None):
        """Initialize service with database path.

        Args:
            db_path: Path to census.db, defaults to ~/.rmcitecraft/census.db
        """
        self.db_path = db_path or CENSUS_DB_PATH
        self.repo = CensusExtractionRepository(self.db_path)

    def load_form_context(
        self,
        page_id: int,
        include_quality: bool = True,
        include_sample_columns: bool = True,
    ) -> CensusFormContext | None:
        """Load form context for a single census page.

        Args:
            page_id: Database page_id
            include_quality: Whether to load quality metadata
            include_sample_columns: Whether to include sample line columns

        Returns:
            CensusFormContext ready for template rendering, or None if not found
        """
        # Load page data
        page_data = self._load_page(page_id)
        if not page_data:
            logger.warning(f"Page not found: {page_id}")
            return None

        # Load persons for this page
        persons = self._load_persons_for_page(page_id, include_quality)

        # Attach persons to page
        page_data.persons = persons

        # Get column definitions
        columns = get_columns_for_year(page_data.census_year)

        # Group into households
        households = self._group_into_households(persons)

        # Find target person for title
        target_name = ""
        for person in persons:
            if person.is_target:
                target_name = person.get_field("full_name")
                break

        # Build title
        title = self._build_title(page_data, target_name)

        # Get FamilySearch URL from first person or page
        fs_url = page_data.familysearch_image_url
        if not fs_url and persons:
            fs_url = persons[0].familysearch_ark

        return CensusFormContext(
            census_year=page_data.census_year,
            pages=[page_data],
            columns=columns,
            households=households,
            title=title,
            target_person_name=target_name,
            show_quality_indicators=include_quality,
            show_sample_columns=include_sample_columns,
            extracted_at=datetime.now(),  # TODO: Get from batch
            familysearch_url=fs_url,
        )

    def load_form_context_for_person(
        self,
        person_id: int,
        include_household: bool = True,
        include_quality: bool = True,
    ) -> CensusFormContext | None:
        """Load form context centered on a specific person.

        Loads the page containing the person, with the person marked as target.

        Args:
            person_id: Database person_id
            include_household: Whether to include full household
            include_quality: Whether to load quality metadata

        Returns:
            CensusFormContext or None if not found
        """
        # Get page_id for this person
        page_id = self._get_page_for_person(person_id)
        if not page_id:
            logger.warning(f"Page not found for person: {person_id}")
            return None

        # Load context
        context = self.load_form_context(
            page_id=page_id,
            include_quality=include_quality,
        )

        if context:
            # Mark target person
            for page in context.pages:
                for person in page.persons:
                    if person.person_id == person_id:
                        person.is_target = True
                        context.target_person_name = person.get_field("full_name")
                        break

        return context

    def load_multi_page_context(
        self,
        page_ids: list[int],
        include_quality: bool = True,
    ) -> CensusFormContext | None:
        """Load form context spanning multiple pages.

        Used for families that span page boundaries.

        Args:
            page_ids: List of page_ids to include
            include_quality: Whether to load quality metadata

        Returns:
            CensusFormContext with multiple pages
        """
        if not page_ids:
            return None

        pages = []
        all_persons = []
        census_year = 0

        for page_id in page_ids:
            page_data = self._load_page(page_id)
            if page_data:
                persons = self._load_persons_for_page(page_id, include_quality)
                page_data.persons = persons
                pages.append(page_data)
                all_persons.extend(persons)
                census_year = page_data.census_year

        if not pages:
            return None

        columns = get_columns_for_year(census_year)
        households = self._group_into_households(all_persons)

        return CensusFormContext(
            census_year=census_year,
            pages=pages,
            columns=columns,
            households=households,
            title=self._build_multi_page_title(pages),
            show_quality_indicators=include_quality,
            extracted_at=datetime.now(),
        )

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _load_page(self, page_id: int) -> FormPageData | None:
        """Load page from database and convert to FormPageData."""
        with self.repo._connect() as conn:
            row = conn.execute(
                "SELECT * FROM census_page WHERE page_id = ?", (page_id,)
            ).fetchone()

            if not row:
                return None

            page = FormPageData(
                page_id=row["page_id"],
                census_year=row["census_year"],
                state=row["state"],
                county=row["county"],
                township_city=row["township_city"],
                enumeration_district=row["enumeration_district"] or "",
                sheet_number=row["sheet_number"] or "",
                sheet_letter=row["sheet_letter"] or "",
                page_number=row["page_number"] or "",
                stamp_number=row["stamp_number"] or "",
                enumeration_date=row["enumeration_date"] or "",
                enumerator_name=row["enumerator_name"] or "",
                familysearch_image_url=row["familysearch_image_url"] or "",
            )

            # Try to get page-level fields from first person's extended fields
            # (enumerator_name, checked_by, enumeration_district are often stored per-person)
            first_person = conn.execute("""
                SELECT person_id FROM census_person
                WHERE page_id = ?
                ORDER BY line_number
                LIMIT 1
            """, (page_id,)).fetchone()

            if first_person:
                person_id = first_person["person_id"]
                page_fields = conn.execute("""
                    SELECT field_name, field_value
                    FROM census_person_field
                    WHERE person_id = ?
                    AND field_name IN ('enumerator_name', 'checked_by', 'enumeration_district')
                """, (person_id,)).fetchall()

                for pf in page_fields:
                    if pf["field_name"] == "enumerator_name" and not page.enumerator_name:
                        page.enumerator_name = pf["field_value"] or ""
                    elif pf["field_name"] == "enumeration_district" and not page.enumeration_district:
                        page.enumeration_district = pf["field_value"] or ""
                    # Store checked_by in page_notes for template access
                    elif pf["field_name"] == "checked_by":
                        page.checked_by = pf["field_value"] or ""

            return page

    def _load_persons_for_page(
        self, page_id: int, include_quality: bool
    ) -> list[FormPersonRow]:
        """Load all persons for a page and convert to FormPersonRow."""
        persons = self.repo.get_persons_on_page(page_id)
        form_persons = []

        for person in persons:
            form_person = self._convert_person(person)

            # Load extended fields (EAV)
            extended_fields = self.repo.get_person_fields(person.person_id)
            for field_name, field_value in extended_fields.items():
                if field_value is not None:
                    form_person.fields[field_name] = FieldValue(
                        value=field_value,
                        is_sample_line_field=self._is_sample_field(field_name),
                    )

            # Load quality metadata
            if include_quality and person.person_id:
                self._attach_quality(form_person, person.person_id)

            # Determine if sample person (1950)
            if person.line_number and person.line_number in SAMPLE_LINES_1950:
                form_person.is_sample_person = True

            form_persons.append(form_person)

        return form_persons

    def _convert_person(self, person: CensusPerson) -> FormPersonRow:
        """Convert CensusPerson to FormPersonRow with core fields."""
        form_person = FormPersonRow(
            person_id=person.person_id,
            line_number=person.line_number,
            is_target=person.is_target_person,
            familysearch_ark=person.familysearch_ark,
        )

        # Add core fields
        core_fields = {
            "full_name": person.full_name,
            "given_name": person.given_name,
            "surname": person.surname,
            "name_suffix": person.name_suffix,
            "relationship_to_head": person.relationship_to_head,
            "sex": person.sex,
            "race": person.race,
            "age": person.age,
            "age_months": person.age_months,
            "marital_status": person.marital_status,
            "birthplace": person.birthplace,
            "birthplace_father": person.birthplace_father,
            "birthplace_mother": person.birthplace_mother,
            "occupation": person.occupation,
            "industry": person.industry,
            "worker_class": person.worker_class,
            "dwelling_number": person.dwelling_number,
            "family_number": person.family_number,
            "household_id": person.household_id,
        }

        for field_name, value in core_fields.items():
            if value is not None and str(value).strip():
                form_person.fields[field_name] = FieldValue(value=value)

        # Check if head of household
        rel = person.relationship_to_head.lower() if person.relationship_to_head else ""
        form_person.is_head_of_household = rel in ("head", "h", "self")

        return form_person

    def _attach_quality(self, form_person: FormPersonRow, person_id: int) -> None:
        """Attach quality metadata to form person fields."""
        quality_records = self.repo.get_field_quality(person_id)

        for quality in quality_records:
            field_name = quality.field_name
            if field_name in form_person.fields:
                fv = form_person.fields[field_name]
                fv.quality = self._map_quality_level(quality.source_legibility)
                fv.confidence = quality.confidence_score
                fv.note = quality.transcription_note

    def _map_quality_level(self, legibility: str) -> FieldQualityLevel:
        """Map database legibility string to FieldQualityLevel."""
        mapping = {
            "clear": FieldQualityLevel.CLEAR,
            "verified": FieldQualityLevel.VERIFIED,
            "uncertain": FieldQualityLevel.UNCERTAIN,
            "faded": FieldQualityLevel.DAMAGED,
            "damaged": FieldQualityLevel.DAMAGED,
            "illegible": FieldQualityLevel.ILLEGIBLE,
        }
        return mapping.get(legibility.lower(), FieldQualityLevel.CLEAR)

    def _is_sample_field(self, field_name: str) -> bool:
        """Check if field is a sample-line-only field (1950)."""
        sample_fields = {
            "residence_1949_same_house",
            "residence_1949_on_farm",
            "residence_1949_same_county",
            "residence_1949_different_location",
            "highest_grade_attended",
            "completed_grade",
            "school_attendance",
            "weeks_looking_for_work",
            "weeks_worked_1949",
            "income_wages_1949",
            "income_self_employment_1949",
            "income_other_1949",
            "veteran_status",
            "veteran_ww1",
            "veteran_ww2",
        }
        return field_name in sample_fields

    def _group_into_households(
        self, persons: list[FormPersonRow]
    ) -> list[FormHousehold]:
        """Group persons into households by dwelling/family number."""
        households_map: dict[tuple, FormHousehold] = {}

        for person in persons:
            dwelling = person.fields.get("dwelling_number")
            family = person.fields.get("family_number")

            dwell_num = int(dwelling.value) if dwelling and dwelling.value else 0
            fam_num = int(family.value) if family and family.value else 0

            key = (dwell_num, fam_num)

            if key not in households_map:
                households_map[key] = FormHousehold(
                    dwelling_number=dwell_num if dwell_num else None,
                    family_number=fam_num if fam_num else None,
                )

            households_map[key].persons.append(person)

        # Sort by dwelling/family number
        sorted_households = sorted(
            households_map.values(),
            key=lambda h: (h.dwelling_number or 0, h.family_number or 0),
        )

        return sorted_households

    def _get_page_for_person(self, person_id: int) -> int | None:
        """Get page_id for a person."""
        with self.repo._connect() as conn:
            row = conn.execute(
                "SELECT page_id FROM census_person WHERE person_id = ?", (person_id,)
            ).fetchone()
            return row["page_id"] if row else None

    def _build_title(self, page: FormPageData, target_name: str = "") -> str:
        """Build form title from page data."""
        parts = [f"{page.census_year} U.S. Census"]
        if page.county:
            parts.append(f"{page.county} County")
        if page.state:
            parts.append(page.state)
        if target_name:
            parts.append(f"- {target_name}")
        return " - ".join(parts[:-1]) + (f" {parts[-1]}" if target_name else "")

    def _build_multi_page_title(self, pages: list[FormPageData]) -> str:
        """Build title for multi-page context."""
        if not pages:
            return "Census Form"

        first_page = pages[0]
        title = self._build_title(first_page)

        if len(pages) > 1:
            title += f" (Pages {pages[0].page_number}-{pages[-1].page_number})"

        return title


# =============================================================================
# Convenience Functions
# =============================================================================


def get_form_service(db_path: Path | None = None) -> CensusFormDataService:
    """Get a CensusFormDataService instance.

    Args:
        db_path: Optional path to census.db

    Returns:
        CensusFormDataService instance
    """
    return CensusFormDataService(db_path)


def load_census_form(page_id: int) -> CensusFormContext | None:
    """Load census form context by page ID.

    Convenience function for quick access.

    Args:
        page_id: Database page_id

    Returns:
        CensusFormContext or None
    """
    service = get_form_service()
    return service.load_form_context(page_id)
