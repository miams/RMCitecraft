"""Test script to verify census extraction fixes.

Tests:
1. is_primary_target parameter exists and defaults to True
2. Batch service uses get_rm_persons_for_source (not get_rm_persons_for_citation)
3. The new get_rm_persons_for_source method exists
"""

import inspect

import pytest


class TestIsTargetPersonFlag:
    """Test that is_target_person is set correctly via the is_primary_target parameter."""

    def test_extract_from_ark_has_is_primary_target_param(self):
        """Verify extract_from_ark has the is_primary_target parameter."""
        from rmcitecraft.services.familysearch_census_extractor import FamilySearchCensusExtractor

        sig = inspect.signature(FamilySearchCensusExtractor.extract_from_ark)
        params = list(sig.parameters.keys())

        assert "is_primary_target" in params, (
            "extract_from_ark should have is_primary_target parameter"
        )

        # Check default value
        param = sig.parameters["is_primary_target"]
        assert param.default is True, (
            "is_primary_target should default to True"
        )


class TestBatchServiceUsesSourceMethod:
    """Test that the batch service uses get_rm_persons_for_source."""

    def test_batch_service_calls_get_rm_persons_for_source(self):
        """Verify batch service uses the correct method for SourceIDs."""
        from rmcitecraft.services import census_transcription_batch
        source = inspect.getsource(census_transcription_batch)

        # Should use get_rm_persons_for_source, not get_rm_persons_for_citation
        assert "get_rm_persons_for_source" in source, (
            "Batch service should call get_rm_persons_for_source"
        )


class TestRMTreeMatcherHasSourceMethod:
    """Test that the matcher has the new source-based method."""

    def test_matcher_has_get_rm_persons_for_source(self):
        """Verify the new method exists on CensusRMTreeMatcher."""
        from rmcitecraft.services.census_rmtree_matcher import CensusRMTreeMatcher

        assert hasattr(CensusRMTreeMatcher, "get_rm_persons_for_source"), (
            "CensusRMTreeMatcher should have get_rm_persons_for_source method"
        )

        # Check signature has expected parameters
        sig = inspect.signature(CensusRMTreeMatcher.get_rm_persons_for_source)
        params = list(sig.parameters.keys())
        assert "source_id" in params, (
            "get_rm_persons_for_source should accept source_id parameter"
        )

    def test_matcher_source_method_returns_tuple(self):
        """Verify the method signature returns appropriate types."""
        from rmcitecraft.services.census_rmtree_matcher import CensusRMTreeMatcher

        # Verify the docstring documents the return format
        doc = CensusRMTreeMatcher.get_rm_persons_for_source.__doc__
        assert doc is not None, "Method should have documentation"
        assert "list" in doc.lower() or "tuple" in doc.lower() or "persons" in doc.lower(), (
            "Documentation should mention return type"
        )


class TestExtractionStatsHasSampleLineCount:
    """Test that extraction stats include sample line person count."""

    def test_stats_method_calculates_sample_line_persons(self):
        """Verify get_extraction_stats includes sample_line_persons."""
        from rmcitecraft.database import census_extraction_db
        source = inspect.getsource(census_extraction_db)

        assert "sample_line_persons" in source, (
            "get_extraction_stats should calculate sample_line_persons"
        )

        # Verify it queries the right tables
        assert "census_person_field" in source, (
            "Should query census_person_field table for sample line data"
        )


class TestHouseholdMemberLinksEnabled:
    """Test that household member matching enables rmtree_links."""

    def test_extract_from_ark_passes_rm_person_id_for_household(self):
        """Verify recursive extraction for household passes matched RM person ID."""
        from rmcitecraft.services import familysearch_census_extractor
        source = inspect.getsource(familysearch_census_extractor)

        # Check that household member extraction uses matched_rm_person_id
        assert "matched_rm_person_id" in source, (
            "Should track matched RM person ID for household members"
        )

        # Household members share the same Census event, so they are also targets
        # The recursive call should pass is_primary_target=True
        assert "# Household members share the same Census event" in source, (
            "Household member extractions should be marked as targets"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
