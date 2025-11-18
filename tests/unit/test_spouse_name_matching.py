"""
Test for enhanced spouse name matching (PersonID 1245 bug fix).

This test validates the fix for the spouse matching bug where:
- Find a Grave spouse: "Frances Davis Iams 1877–1945 (m. 1898)"
- Database spouse: "Frances Dora Davis" (maiden name)
- Bug: Only 56.52% similarity (below 60% threshold) - NO MATCH
- Fix: 72.22% similarity - MATCH!

The fix implements robust matching by:
1. Fully normalizing the FG name (remove dates, parens, etc.)
2. Generating DB name variations (maiden + married names)
3. Comparing FG name against all DB variations, taking best match
"""

import pytest
from difflib import SequenceMatcher
import re


def normalize_fg_spouse_name(fg_spouse_name: str) -> str:
    """
    Fully normalize Find a Grave spouse name.
    
    Removes:
    - Parenthetical text: (m. 1898), (married 1900)
    - Date ranges: 1877–1945, 1877-1945
    - Extra whitespace
    
    Args:
        fg_spouse_name: Raw Find a Grave spouse name
        
    Returns:
        Normalized name (e.g., "Frances Davis Iams")
    """
    # Remove parenthetical text
    normalized = re.sub(r'\([^)]*\)', '', fg_spouse_name).strip()
    
    # Remove date ranges (YYYY–YYYY or YYYY-YYYY)
    normalized = re.sub(r'\d{4}\s*[–-]\s*\d{4}', '', normalized).strip()
    
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized


def build_db_spouse_variations(
    given: str,
    surname: str,
    subject_surname: str | None,
    prefix: str | None = None,
    suffix: str | None = None
) -> list[str]:
    """
    Build database spouse name variations.
    
    Includes:
    - Maiden name variations (Given Surname, Prefix Given Surname, etc.)
    - Married name variations (Given SubjectSurname, Given Maiden SubjectSurname)
    
    Args:
        given: Given name from database
        surname: Maiden surname from database
        subject_surname: Subject's surname (married name)
        prefix: Optional prefix (Dr., Mrs., etc.)
        suffix: Optional suffix (Jr., III, etc.)
        
    Returns:
        List of name variations to try matching
    """
    variations = []
    
    # Maiden name variations
    if given and surname:
        variations.append(f"{given} {surname}")
    
    if prefix and given and surname:
        variations.append(f"{prefix} {given} {surname}")
    
    if given and surname and suffix:
        variations.append(f"{given} {surname} {suffix}")
    
    if prefix and given and surname and suffix:
        variations.append(f"{prefix} {given} {surname} {suffix}")
    
    # Married name variations
    if subject_surname and given:
        # Married name: Given + Subject Surname
        variations.append(f"{given} {subject_surname}")
        
        # Married with maiden as middle: Given + Maiden + Subject Surname
        if surname:
            variations.append(f"{given} {surname} {subject_surname}")
        
        # With prefix: Prefix + Given + Subject Surname
        if prefix:
            variations.append(f"{prefix} {given} {subject_surname}")
    
    return variations


def find_best_match(fg_name: str, db_variations: list[str]) -> tuple[float, str]:
    """Find best match score between FG name and DB variations."""
    best_score = 0.0
    best_db = ""
    
    for db_var in db_variations:
        similarity = SequenceMatcher(None, fg_name.lower(), db_var.lower()).ratio()
        if similarity > best_score:
            best_score = similarity
            best_db = db_var
    
    return best_score, best_db


class TestSpouseNameMatching:
    """Test enhanced spouse name matching."""
    
    def test_personid_1245_bug_fix(self):
        """Test the specific bug case: PersonID 1245 spouse matching."""
        subject_surname = "Iams"
        fg_spouse_name = "Frances Davis Iams 1877–1945 (m. 1898)"
        db_given = "Frances Dora"
        db_surname = "Davis"
        
        # Normalize FG name
        fg_normalized = normalize_fg_spouse_name(fg_spouse_name)
        
        # Generate DB variations
        db_vars = build_db_spouse_variations(db_given, db_surname, subject_surname)
        
        # Find best match
        score, best_db = find_best_match(fg_normalized, db_vars)
        
        # Assertions
        assert fg_normalized == "Frances Davis Iams", f"Normalization failed: '{fg_normalized}'"
        assert score >= 0.60, f"Match score {score:.1%} below 60% threshold"
        assert "Frances Dora" in best_db
    
    def test_normalization_removes_dates(self):
        """Test that date removal works correctly."""
        test_cases = [
            ("Frances Davis 1877–1945", "Frances Davis"),  # en-dash
            ("Frances Davis 1877-1945", "Frances Davis"),  # hyphen
            ("Frances Davis Iams 1877–1945 (m. 1898)", "Frances Davis Iams"),  # both
        ]
        
        for input_name, expected in test_cases:
            normalized = normalize_fg_spouse_name(input_name)
            assert normalized == expected, f"Expected '{expected}', got '{normalized}'"
    
    def test_married_name_variations(self):
        """Test that married name variations are generated."""
        subject_surname = "Smith"
        given = "Jane"
        surname = "Doe"
        
        variations = build_db_spouse_variations(given, surname, subject_surname)
        
        # Should include both maiden and married variations
        assert "Jane Doe" in variations, "Missing maiden name"
        assert "Jane Smith" in variations, "Missing married name"
        assert "Jane Doe Smith" in variations, "Missing married with maiden middle"
    
    def test_match_with_married_name(self):
        """Test matching FG married name against DB maiden name."""
        subject_surname = "Smith"
        fg_name = "Jane Smith 1880-1950"
        db_given = "Jane"
        db_surname = "Doe"
        
        fg_normalized = normalize_fg_spouse_name(fg_name)
        db_vars = build_db_spouse_variations(db_given, db_surname, subject_surname)
        score, best_db = find_best_match(fg_normalized, db_vars)
        
        assert score >= 0.60, f"Married name match failed: {score:.1%}"
        assert best_db == "Jane Smith", f"Should match married name, got '{best_db}'"
    
    def test_match_with_maiden_name(self):
        """Test matching FG maiden name against DB maiden name."""
        subject_surname = "Smith"
        fg_name = "Jane Doe"
        db_given = "Jane"
        db_surname = "Doe"
        
        fg_normalized = normalize_fg_spouse_name(fg_name)
        db_vars = build_db_spouse_variations(db_given, db_surname, subject_surname)
        score, best_db = find_best_match(fg_normalized, db_vars)
        
        assert score >= 0.60, f"Maiden name match failed: {score:.1%}"
        assert score > 0.99, f"Exact match should be near 100%, got {score:.1%}"
    
    def test_with_middle_name_difference(self):
        """Test matching when FG uses middle initial and DB has full middle name."""
        subject_surname = "Johnson"
        fg_name = "Mary A. Johnson (1880-1950)"
        db_given = "Mary Anne"
        db_surname = "Williams"
        
        fg_normalized = normalize_fg_spouse_name(fg_name)
        db_vars = build_db_spouse_variations(db_given, db_surname, subject_surname)
        score, _ = find_best_match(fg_normalized, db_vars)
        
        # Should still match reasonably well
        assert score >= 0.60, f"Middle name variation match failed: {score:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
