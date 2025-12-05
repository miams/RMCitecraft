"""
Extraction Gap Analyzer Service.

Analyzes census extraction results to identify:
1. Missing persons - RM persons expected but not matched
2. Missing fields - Extracted persons with incomplete data
3. Match failures - Patterns in why matches failed

Provides prioritized gap reports for iterative improvement of extraction algorithms.
"""

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from rmcitecraft.database.census_extraction_db import (
    CensusExtractionRepository,
    ExtractionGap,
    GapPattern,
    MatchAttempt,
)
from rmcitecraft.database.connection import connect_rmtree


# =============================================================================
# Phonetic Matching Utilities
# =============================================================================

# Surname variants that should be treated as equivalent
SURNAME_PHONETIC_GROUPS = {
    "ijams_family": {
        "ijams", "iiams", "iams", "imes", "ijames", "iames", "ines", "iimes",
        "sjames", "james",  # OCR errors
    },
}


def get_surname_phonetic_group(surname: str) -> str | None:
    """Get the phonetic group for a surname, if any."""
    surname_lower = re.sub(r'[^a-z]', '', surname.lower())
    for group_name, variants in SURNAME_PHONETIC_GROUPS.items():
        if surname_lower in variants:
            return group_name
    return None


def surnames_phonetically_match(surname1: str, surname2: str) -> bool:
    """Check if two surnames are phonetically equivalent."""
    s1 = re.sub(r'[^a-z]', '', surname1.lower())
    s2 = re.sub(r'[^a-z]', '', surname2.lower())

    if s1 == s2:
        return True

    # Check if in same phonetic group
    group1 = get_surname_phonetic_group(s1)
    group2 = get_surname_phonetic_group(s2)

    if group1 and group1 == group2:
        return True

    # Check prefix match (for OCR variations)
    if len(s1) >= 3 and len(s2) >= 3:
        if s1[:3] == s2[:3] or s1[-3:] == s2[-3:]:
            return True

    return False


# =============================================================================
# Gap Categories
# =============================================================================

@dataclass
class GapCategory:
    """Definition of a gap category with detection rules."""
    name: str
    description: str
    detection_rules: dict[str, Any]
    suggested_fix: str
    fix_complexity: str


GAP_CATEGORIES = {
    "married_name_mismatch": GapCategory(
        name="married_name_mismatch",
        description="Woman's married name in FS doesn't match maiden name in RM",
        detection_rules={
            "skip_reason": "surname_mismatch",
            "fs_relationship": ["Wife", "wife"],
        },
        suggested_fix="Enhance married name matching to check spouse relationships in RM",
        fix_complexity="medium",
    ),
    "middle_name_as_first": GapCategory(
        name="middle_name_as_first",
        description="FS uses middle name as first name (e.g., 'Harvey' for 'Guy Harvey')",
        detection_rules={
            "skip_reason": "surname_mismatch",
            "first_name_in_middle": True,
        },
        suggested_fix="Add middle-name-as-first matching in _matches_any_rm_person",
        fix_complexity="easy",
    ),
    "surname_ocr_error": GapCategory(
        name="surname_ocr_error",
        description="OCR error in surname (e.g., 'Sjames' for 'Ijames')",
        detection_rules={
            "skip_reason": "surname_mismatch",
            "phonetic_match": True,
        },
        suggested_fix="Add phonetic surname matching for known family variants",
        fix_complexity="easy",
    ),
    "initial_vs_full_name": GapCategory(
        name="initial_vs_full_name",
        description="FS has initial where RM has full name (e.g., 'L' vs 'Lyndon')",
        detection_rules={
            "skip_reason": "below_threshold",
            "has_initial": True,
        },
        suggested_fix="Lower threshold for initial matches or implement smarter initial handling",
        fix_complexity="easy",
    ),
    "spelling_variation": GapCategory(
        name="spelling_variation",
        description="Name spelling differs (e.g., 'Katherine' vs 'Catherine')",
        detection_rules={
            "skip_reason": "below_threshold",
            "spelling_diff": True,
        },
        suggested_fix="Add common spelling variation mappings",
        fix_complexity="medium",
    ),
    "fs_data_missing": GapCategory(
        name="fs_data_missing",
        description="Data doesn't exist in FamilySearch (expected gap)",
        detection_rules={
            "fs_data_exists": False,
        },
        suggested_fix="No fix needed - data doesn't exist in source",
        fix_complexity="trivial",
    ),
    "unknown": GapCategory(
        name="unknown",
        description="Gap cause not yet categorized",
        detection_rules={},
        suggested_fix="Manual analysis required",
        fix_complexity="hard",
    ),
}


# =============================================================================
# Gap Analyzer Service
# =============================================================================

class ExtractionGapAnalyzer:
    """Analyzes extraction results to identify and categorize gaps."""

    def __init__(
        self,
        census_db_path: Path | None = None,
        rmtree_path: Path | None = None,
    ):
        """Initialize analyzer with database paths."""
        self.census_repo = CensusExtractionRepository(census_db_path)
        self.rmtree_path = rmtree_path or Path("data/Iiams.rmtree")

    def analyze_batch(
        self,
        batch_id: int,
        source_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Analyze a batch for extraction gaps.

        Args:
            batch_id: The extraction batch to analyze
            source_ids: Optional list of source IDs to analyze (default: all in batch)

        Returns:
            Analysis results with gap counts, categories, and prioritized patterns
        """
        logger.info(f"Analyzing batch {batch_id} for extraction gaps...")

        results = {
            "batch_id": batch_id,
            "gaps_detected": 0,
            "gaps_by_type": {},
            "gaps_by_category": {},
            "patterns": [],
            "priority_fixes": [],
        }

        # Get match attempts for this batch
        with self.census_repo._connect() as conn:
            if source_ids:
                placeholders = ",".join("?" * len(source_ids))
                attempts = conn.execute(
                    f"""SELECT * FROM match_attempt
                        WHERE batch_id = ? AND source_id IN ({placeholders})""",
                    [batch_id] + source_ids,
                ).fetchall()
            else:
                attempts = conn.execute(
                    "SELECT * FROM match_attempt WHERE batch_id = ?",
                    (batch_id,),
                ).fetchall()

        # Analyze failed matches
        skipped_attempts = [a for a in attempts if a["match_status"] == "skipped"]
        logger.info(f"Found {len(skipped_attempts)} skipped match attempts to analyze")

        # Get expected RM persons for comparison
        if source_ids:
            expected_rm = self._get_expected_rm_persons(source_ids)
        else:
            # Get all source IDs from batch
            with self.census_repo._connect() as conn:
                batch_sources = conn.execute(
                    "SELECT DISTINCT source_id FROM match_attempt WHERE batch_id = ?",
                    (batch_id,),
                ).fetchall()
                source_ids = [r["source_id"] for r in batch_sources if r["source_id"]]
                expected_rm = self._get_expected_rm_persons(source_ids) if source_ids else {}

        # Detect gaps from skipped attempts
        for attempt in skipped_attempts:
            gap = self._categorize_gap(attempt, expected_rm)
            if gap:
                self.census_repo.insert_extraction_gap(gap)
                results["gaps_detected"] += 1

                # Count by type
                results["gaps_by_type"][gap.gap_type] = \
                    results["gaps_by_type"].get(gap.gap_type, 0) + 1

                # Count by category
                results["gaps_by_category"][gap.gap_category] = \
                    results["gaps_by_category"].get(gap.gap_category, 0) + 1

        # Detect missing persons (expected but not in match_attempts at all)
        matched_rm_ids = set()
        with self.census_repo._connect() as conn:
            rows = conn.execute(
                """SELECT DISTINCT matched_rm_person_id FROM match_attempt
                   WHERE batch_id = ? AND matched_rm_person_id IS NOT NULL""",
                (batch_id,),
            ).fetchall()
            matched_rm_ids = {r["matched_rm_person_id"] for r in rows}

        for rm_id, rm_data in expected_rm.items():
            if rm_id not in matched_rm_ids:
                # Check if there's a skipped attempt that might be this person
                likely_attempt = self._find_likely_skipped_attempt(
                    rm_data, skipped_attempts
                )

                gap = ExtractionGap(
                    batch_id=batch_id,
                    source_id=list(rm_data["sources"])[0] if rm_data["sources"] else None,
                    gap_type="missing_person",
                    gap_category="unknown",
                    severity="high",
                    expected_rm_person_id=rm_id,
                    expected_rm_name=f"{rm_data['given']} {rm_data['surname']}",
                    actual_fs_name=likely_attempt["fs_full_name"] if likely_attempt else "",
                    actual_fs_ark=likely_attempt["fs_ark"] if likely_attempt else "",
                )

                # Try to categorize the gap
                if likely_attempt:
                    gap = self._categorize_missing_person_gap(gap, rm_data, likely_attempt)

                self.census_repo.insert_extraction_gap(gap)
                results["gaps_detected"] += 1
                results["gaps_by_type"]["missing_person"] = \
                    results["gaps_by_type"].get("missing_person", 0) + 1
                results["gaps_by_category"][gap.gap_category] = \
                    results["gaps_by_category"].get(gap.gap_category, 0) + 1

        # Identify patterns and prioritize
        results["patterns"] = self._identify_patterns(batch_id)
        results["priority_fixes"] = self._prioritize_fixes(results["patterns"])

        logger.info(
            f"Analysis complete: {results['gaps_detected']} gaps detected, "
            f"{len(results['patterns'])} patterns identified"
        )

        return results

    def _get_expected_rm_persons(self, source_ids: list[int]) -> dict[int, dict]:
        """Get expected RM persons from RootsMagic for given sources."""
        if not source_ids:
            return {}

        conn = connect_rmtree(str(self.rmtree_path))
        placeholders = ",".join("?" * len(source_ids))

        query = f"""
        SELECT DISTINCT e.OwnerID as person_id, n.Given, n.Surname, s.SourceID
        FROM SourceTable s
        JOIN CitationTable c ON s.SourceID = c.SourceID
        JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID AND cl.OwnerType = 2
        JOIN EventTable e ON cl.OwnerID = e.EventID AND e.OwnerType = 0
        JOIN NameTable n ON e.OwnerID = n.OwnerID AND n.IsPrimary = 1
        WHERE s.SourceID IN ({placeholders})
        UNION
        SELECT DISTINCT w.PersonID, n.Given, n.Surname, s.SourceID
        FROM SourceTable s
        JOIN CitationTable c ON s.SourceID = c.SourceID
        JOIN CitationLinkTable cl ON c.CitationID = cl.CitationID AND cl.OwnerType = 2
        JOIN EventTable e ON cl.OwnerID = e.EventID AND e.OwnerType = 0
        JOIN WitnessTable w ON e.EventID = w.EventID
        JOIN NameTable n ON w.PersonID = n.OwnerID AND n.IsPrimary = 1
        WHERE s.SourceID IN ({placeholders})
        """

        cursor = conn.cursor()
        cursor.execute(query, source_ids + source_ids)

        expected = {}
        for person_id, given, surname, source_id in cursor.fetchall():
            if person_id not in expected:
                expected[person_id] = {
                    "given": given or "",
                    "surname": surname or "",
                    "sources": set(),
                }
            expected[person_id]["sources"].add(source_id)

        conn.close()
        return expected

    def _categorize_gap(
        self,
        attempt: sqlite3.Row,
        expected_rm: dict[int, dict],
    ) -> ExtractionGap | None:
        """Categorize a skipped match attempt into a gap."""
        fs_surname = attempt["fs_surname"] or ""
        fs_given = attempt["fs_given_name"] or ""
        fs_relationship = attempt["fs_relationship"] or ""
        skip_reason = attempt["skip_reason"] or ""

        # Determine gap category
        category = "unknown"

        # Check for married name mismatch
        if skip_reason == "surname_mismatch" and fs_relationship.lower() in ["wife", "spouse"]:
            category = "married_name_mismatch"

        # Check for OCR surname error
        elif skip_reason == "surname_mismatch":
            # Check if surname is phonetically similar to any expected RM surname
            for rm_data in expected_rm.values():
                if surnames_phonetically_match(fs_surname, rm_data["surname"]):
                    category = "surname_ocr_error"
                    break

        # Check for initial vs full name
        elif skip_reason == "below_threshold":
            if len(fs_given.split()) > 0:
                first_name = fs_given.split()[0]
                if len(first_name) == 1:
                    category = "initial_vs_full_name"

        return ExtractionGap(
            batch_id=attempt["batch_id"],
            page_id=attempt["page_id"],
            source_id=attempt["source_id"],
            gap_type="match_failure",
            gap_category=category,
            severity="medium" if category != "unknown" else "low",
            actual_fs_name=attempt["fs_full_name"],
            actual_fs_ark=attempt["fs_ark"],
            root_cause=skip_reason,
        )

    def _find_likely_skipped_attempt(
        self,
        rm_data: dict,
        skipped_attempts: list[sqlite3.Row],
    ) -> sqlite3.Row | None:
        """Find a skipped attempt that likely matches an expected RM person."""
        rm_given = rm_data["given"].lower().split()[0] if rm_data["given"] else ""
        rm_surname = rm_data["surname"].lower() if rm_data["surname"] else ""

        best_match = None
        best_score = 0

        for attempt in skipped_attempts:
            fs_given = (attempt["fs_given_name"] or "").lower().split()[0] if attempt["fs_given_name"] else ""
            fs_surname = (attempt["fs_surname"] or "").lower()

            score = 0

            # Surname match (phonetic)
            if surnames_phonetically_match(fs_surname, rm_surname):
                score += 2

            # First name match
            if rm_given and fs_given:
                if rm_given == fs_given:
                    score += 2
                elif rm_given[0] == fs_given[0]:  # Initial match
                    score += 1
                # Check if FS name is in RM middle names
                rm_middle = " ".join(rm_data["given"].lower().split()[1:])
                if fs_given in rm_middle:
                    score += 1.5  # Middle name used as first

            if score > best_score:
                best_score = score
                best_match = attempt

        return best_match if best_score >= 2 else None

    def _categorize_missing_person_gap(
        self,
        gap: ExtractionGap,
        rm_data: dict,
        likely_attempt: sqlite3.Row,
    ) -> ExtractionGap:
        """Categorize a missing person gap based on RM data and likely FS match."""
        fs_surname = (likely_attempt["fs_surname"] or "").lower()
        rm_surname = (rm_data["surname"] or "").lower()
        fs_given = (likely_attempt["fs_given_name"] or "").lower()
        rm_given = (rm_data["given"] or "").lower()
        fs_relationship = (likely_attempt["fs_relationship"] or "").lower()

        # Check for married name
        if fs_relationship in ["wife", "spouse"] and fs_surname != rm_surname:
            gap.gap_category = "married_name_mismatch"
            gap.severity = "high"
            return gap

        # Check for middle name as first
        rm_parts = rm_given.split()
        if len(rm_parts) > 1:
            rm_middle = " ".join(rm_parts[1:])
            fs_first = fs_given.split()[0] if fs_given else ""
            if fs_first and fs_first in rm_middle:
                gap.gap_category = "middle_name_as_first"
                gap.severity = "high"
                return gap

        # Check for OCR error
        if surnames_phonetically_match(fs_surname, rm_surname) and fs_surname != rm_surname:
            gap.gap_category = "surname_ocr_error"
            gap.severity = "medium"
            return gap

        # Check for spelling variation
        if fs_surname[:3] == rm_surname[:3] or fs_surname[-3:] == rm_surname[-3:]:
            gap.gap_category = "spelling_variation"
            gap.severity = "medium"
            return gap

        return gap

    def _identify_patterns(self, batch_id: int) -> list[dict[str, Any]]:
        """Identify patterns in gaps for this batch."""
        summary = self.census_repo.get_gap_summary_by_category(batch_id)

        patterns = []
        for item in summary:
            category = item["gap_category"]
            if category in GAP_CATEGORIES:
                cat_def = GAP_CATEGORIES[category]
                pattern = GapPattern(
                    pattern_name=category,
                    pattern_description=cat_def.description,
                    match_criteria_json=json.dumps({"gap_category": category}),
                    affected_count=item["count"],
                    affected_sources=item["affected_sources"],
                    affected_batches=1,
                    suggested_fix=cat_def.suggested_fix,
                    fix_complexity=cat_def.fix_complexity,
                )
                self.census_repo.upsert_gap_pattern(pattern)
                patterns.append({
                    "name": category,
                    "description": cat_def.description,
                    "count": item["count"],
                    "affected_sources": item["affected_sources"],
                    "suggested_fix": cat_def.suggested_fix,
                    "complexity": cat_def.fix_complexity,
                    "priority_score": item["priority_score"],
                })

        return sorted(patterns, key=lambda p: -p["priority_score"])

    def _prioritize_fixes(self, patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prioritize fixes by impact and complexity."""
        # Score: high count + easy fix = higher priority
        complexity_factor = {
            "trivial": 4,
            "easy": 3,
            "medium": 2,
            "hard": 1,
            "complex": 0.5,
        }

        for pattern in patterns:
            complexity = pattern.get("complexity", "medium")
            factor = complexity_factor.get(complexity, 1)
            pattern["fix_priority"] = pattern["count"] * factor

        return sorted(patterns, key=lambda p: -p["fix_priority"])

    def generate_report(self, batch_id: int) -> str:
        """Generate a human-readable gap analysis report."""
        stats = self.census_repo.get_match_attempt_stats(batch_id)
        gaps = self.census_repo.get_gap_summary_by_category(batch_id)
        patterns = self.census_repo.get_gap_patterns_prioritized()

        report = []
        report.append("=" * 80)
        report.append("EXTRACTION GAP ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")

        # Match statistics
        report.append("MATCH STATISTICS")
        report.append("-" * 40)
        report.append(f"Total attempts: {stats.get('total_attempts', 0)}")
        report.append(f"Match rate: {stats.get('match_rate', 0):.1%}")
        report.append("")
        report.append("By status:")
        for status, count in stats.get("by_status", {}).items():
            report.append(f"  {status}: {count}")
        report.append("")
        report.append("By skip reason:")
        for reason, count in stats.get("by_skip_reason", {}).items():
            report.append(f"  {reason}: {count}")
        report.append("")

        # Gap summary
        report.append("GAP SUMMARY BY CATEGORY")
        report.append("-" * 40)
        for gap in gaps:
            report.append(
                f"  {gap['gap_category']}: {gap['count']} gaps "
                f"({gap['affected_sources']} sources, {gap['open_count']} open)"
            )
        report.append("")

        # Priority fixes
        report.append("PRIORITY FIXES")
        report.append("-" * 40)
        for i, pattern in enumerate(patterns[:5], 1):
            report.append(f"{i}. {pattern.pattern_name}")
            report.append(f"   Impact: {pattern.affected_count} records")
            report.append(f"   Complexity: {pattern.fix_complexity}")
            report.append(f"   Fix: {pattern.suggested_fix}")
            report.append("")

        return "\n".join(report)


# =============================================================================
# Convenience Functions
# =============================================================================

def analyze_extraction_batch(
    batch_id: int,
    source_ids: list[int] | None = None,
    census_db_path: Path | None = None,
    rmtree_path: Path | None = None,
) -> dict[str, Any]:
    """Convenience function to analyze a batch."""
    analyzer = ExtractionGapAnalyzer(census_db_path, rmtree_path)
    return analyzer.analyze_batch(batch_id, source_ids)


def generate_gap_report(
    batch_id: int,
    census_db_path: Path | None = None,
    rmtree_path: Path | None = None,
) -> str:
    """Convenience function to generate a gap report."""
    analyzer = ExtractionGapAnalyzer(census_db_path, rmtree_path)
    return analyzer.generate_report(batch_id)
