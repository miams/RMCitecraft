"""
Tests for enhanced name matching algorithms.

Tests phonetic surname matching, spelling variations, middle name as first,
and married name matching enhancements.
"""

import pytest
from rmcitecraft.services.familysearch_census_extractor import (
    surnames_phonetically_match,
    first_names_spelling_match,
    names_match_score,
    get_name_variations,
    normalize_name,
)


class TestPhoneticSurnameMatching:
    """Tests for phonetic surname matching."""

    def test_exact_match(self):
        """Exact surnames should match."""
        assert surnames_phonetically_match("Ijams", "Ijams")
        assert surnames_phonetically_match("Smith", "Smith")

    def test_case_insensitive(self):
        """Matching should be case insensitive."""
        assert surnames_phonetically_match("IJAMS", "ijams")
        assert surnames_phonetically_match("Ijams", "IJAMS")

    def test_family_variants_ijams(self):
        """Ijams family variants should all match."""
        variants = ["Ijams", "Iiams", "Iams", "Imes", "Ijames", "Iames", "Ines", "Iimes"]
        for v1 in variants:
            for v2 in variants:
                assert surnames_phonetically_match(v1, v2), f"{v1} should match {v2}"

    def test_ocr_error_sjames(self):
        """OCR error 'Sjames' should match 'Ijames'."""
        assert surnames_phonetically_match("Sjames", "Ijames")
        assert surnames_phonetically_match("Sjames", "Ijams")

    def test_prefix_match(self):
        """Surnames with matching prefix should match."""
        assert surnames_phonetically_match("Johns", "Johnson")
        assert surnames_phonetically_match("Smit", "Smith")

    def test_suffix_match(self):
        """Surnames with matching suffix should match."""
        assert surnames_phonetically_match("Michaelson", "Johnson")  # -son suffix

    def test_unrelated_surnames_no_match(self):
        """Unrelated surnames should not match."""
        assert not surnames_phonetically_match("Smith", "Jones")
        assert not surnames_phonetically_match("Brown", "White")


class TestFirstNameSpellingVariants:
    """Tests for first name spelling variation matching."""

    def test_exact_match(self):
        """Exact first names should match."""
        assert first_names_spelling_match("Catherine", "Catherine")

    def test_katherine_catherine(self):
        """Katherine/Catherine variants should match."""
        assert first_names_spelling_match("Katherine", "Catherine")
        assert first_names_spelling_match("Kathryn", "Catherine")
        assert first_names_spelling_match("Catharine", "Katherine")

    def test_lyndon_lydon(self):
        """Lyndon/Lydon OCR variant should match."""
        assert first_names_spelling_match("Lyndon", "Lydon")
        assert first_names_spelling_match("Lydon", "Lyndon")

    def test_elisabeth_elizabeth(self):
        """Elisabeth/Elizabeth should match."""
        assert first_names_spelling_match("Elisabeth", "Elizabeth")

    def test_steven_stephen(self):
        """Steven/Stephen should match."""
        assert first_names_spelling_match("Steven", "Stephen")

    def test_unrelated_names_no_match(self):
        """Unrelated names should not match."""
        assert not first_names_spelling_match("John", "James")
        assert not first_names_spelling_match("Mary", "Martha")


class TestNamesMatchScore:
    """Tests for the enhanced names_match_score function."""

    def test_exact_match_full_name(self):
        """Exact full name match should score 1.0."""
        score, reason = names_match_score("John Smith", "John Smith")
        assert score == 1.0
        assert reason == "exact"

    def test_surname_mismatch_unrelated(self):
        """Completely different surnames should return 0."""
        score, reason = names_match_score("John Smith", "John Jones")
        assert score == 0.0
        assert reason == "surname_mismatch"

    def test_phonetic_surname_match(self):
        """Phonetic surname match should allow matching."""
        score, reason = names_match_score("John Ijams", "John Iiams")
        assert score >= 0.9
        assert "first_name_exact" in reason

    def test_phonetic_surname_with_ocr_error(self):
        """OCR error in surname should still match."""
        score, reason = names_match_score("John Sjames", "John Ijames")
        assert score >= 0.9

    def test_initial_match(self):
        """Initial matching (J matches John)."""
        score, reason = names_match_score("J Smith", "John Smith")
        assert score >= 0.85
        assert reason == "initial_match"

    def test_nickname_match(self):
        """Nickname matching (Bill matches William)."""
        score, reason = names_match_score("Bill Smith", "William Smith")
        assert score >= 0.75
        assert reason == "nickname_match"

    def test_spelling_variant_match(self):
        """Spelling variant (Katherine/Catherine)."""
        score, reason = names_match_score("Katherine Smith", "Catherine Smith")
        assert score >= 0.85
        assert reason == "spelling_variant"

    def test_middle_name_as_first(self):
        """Middle name used as first (Harvey matches Guy Harvey)."""
        score, reason = names_match_score("Harvey Ijams", "Guy Harvey Ijams")
        assert score >= 0.75
        assert "middle_as_first" in reason

    def test_prefix_match(self):
        """Prefix matching (Mel matches Melbourne)."""
        score, reason = names_match_score("Mel Smith", "Melbourne Smith")
        assert score >= 0.7
        # "Mel" is also a known nickname for Melbourne, so nickname_match is valid
        assert reason in ("prefix_match", "nickname_match")


class TestNicknameVariations:
    """Tests for get_name_variations."""

    def test_formal_to_nickname(self):
        """Formal name should include nicknames."""
        variations = get_name_variations("William")
        assert "bill" in variations
        assert "will" in variations
        assert "william" in variations

    def test_nickname_to_formal(self):
        """Nickname should include formal name."""
        variations = get_name_variations("Bill")
        assert "william" in variations
        assert "bill" in variations

    def test_elizabeth_variations(self):
        """Elizabeth should have many variations."""
        variations = get_name_variations("Elizabeth")
        assert "liz" in variations
        assert "beth" in variations
        assert "betty" in variations

    def test_margaret_variations(self):
        """Margaret should have variations."""
        variations = get_name_variations("Margaret")
        assert "meg" in variations
        assert "peggy" in variations
        assert "maggie" in variations


class TestIntegrationScenarios:
    """Integration tests for real-world matching scenarios from 100-entry test."""

    def test_lydon_lyndon_match(self):
        """'Lydon Ijams' should match 'Lyndon Hatfield Ijams'."""
        score, reason = names_match_score("Lydon Ijams", "Lyndon Hatfield Ijams")
        assert score >= 0.75, f"Expected match, got score={score}, reason={reason}"

    def test_chatharine_catherine_match(self):
        """'Chatharine L Ines' should match 'Catherine Harriet Ijams'."""
        # This is a challenging case: Chatharine/Catherine + Ines/Ijams
        score, reason = names_match_score("Chatharine L Ines", "Catherine Harriet Ijams")
        # Should match on phonetic surname + spelling variant
        assert score >= 0.75, f"Expected match, got score={score}, reason={reason}"

    def test_harvey_guy_harvey_middle_name(self):
        """'Harvey Ijams' should match 'Guy Harvey Ijams' (middle name as first)."""
        score, reason = names_match_score("Harvey Ijams", "Guy Harvey Ijams")
        assert score >= 0.75
        assert "middle_as_first" in reason

    def test_beth_elizabeth_nickname(self):
        """'Beth Ijams' should match 'Elizabeth Ijams' via nickname."""
        score, reason = names_match_score("Beth Ijams", "Elizabeth Ijams")
        assert score >= 0.75
        assert reason == "nickname_match"

    def test_vernell_sjames_ocr_error(self):
        """'Vernell V Sjames' should match 'Vernell Verna Ijames' despite OCR error."""
        score, reason = names_match_score("Vernell V Sjames", "Vernell Verna Ijames")
        assert score >= 0.9, f"Expected high match, got score={score}, reason={reason}"


class TestNormalization:
    """Tests for name normalization."""

    def test_lowercase(self):
        """Names should be lowercased."""
        assert normalize_name("JOHN SMITH") == "john smith"

    def test_extra_spaces(self):
        """Extra spaces should be removed."""
        assert normalize_name("John  Smith") == "john smith"

    def test_punctuation(self):
        """Punctuation should be handled."""
        result = normalize_name("John, Smith Jr.")
        assert "john" in result
        assert "smith" in result
