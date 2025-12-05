---
priority: reference
topics: [database, citation, batch, findagrave, testing]
---

# Citation Matching Report Implementation

**Date**: 2025-11-17  
**Feature**: End-of-batch citation matching report with spouse and parent summaries

## Overview

After Find a Grave batch processing completes, the system now displays a comprehensive citation matching report showing:
1. **Spouse matches** - Which spouses were found and linked with match percentages
2. **Parent matches** - Summary of parent family citations with failure details

## Report Format

### Spouse Matching Table

| Column | Description |
|--------|-------------|
| **Target Name** | Subject person's name (from RootsMagic) |
| **Person ID** | Subject's PersonID |
| **RM Spouse Name** | Best matching variation from database |
| **Spouse ID** | Spouse's PersonID (if matched) |
| **Find a Grave Name** | Spouse name from Find a Grave |
| **Match %** | Similarity score (0-100%) |

**Color Coding**:
- **Green text** - Match ≥ 60% (citation successfully linked)
- **Red text** - Match < 60% (citation NOT linked)

**Filtering**:
- Only shows entries where Find a Grave specifies 1+ spouses
- Displays best match variation only (not all 7 variations tested)

### Parent Matching Summary

**Format**: `(X/Y) entries with parents successfully cited`

Where:
- Y = Total entries specifying parents in Find a Grave
- X = Successfully cited parent relationships

**Failure List** (red text):
- Shows only failed parent matches
- Format: `PersonName (Person ID) - Reason for failure`
- Example: `Thomas Iams (Person ID 1234) - No parent family found in database`

## Implementation Details

### Enhanced `link_citation_to_families()` Function

**File**: `src/rmcitecraft/database/findagrave_queries.py`

**Return Value Enhanced**:
```python
return {
    'parent_family_ids': [...],           # Original
    'spouse_family_ids': [...],           # Original
    'warnings': [...],                    # Original
    'spouse_matches': [                   # NEW - For reporting
        {
            'fg_name': str,               # Find a Grave spouse name
            'db_name': str | None,        # Best matching DB variation
            'db_person_id': int | None,   # Spouse PersonID
            'match_score': float,         # 0.0 - 1.0
            'matched': bool,              # True if >= 60%
        },
        ...
    ],
    'parent_match_info': {                # NEW - For reporting
        'parent_count': int,              # Should be 2
        'matched': bool,                  # True if linked
    } | None,
}
```

**Key Changes**:
1. **Lines 996-997**: Added `spouse_matches` and `parent_match_info` for reporting
2. **Line 1106**: Track `best_db_variation` during matching
3. **Lines 1189**: Store best matching DB variation name
4. **Lines 1024, 1061, 1064**: Set `parent_match_info['matched']` based on link success
5. **Lines 1241-1249**: Collect spouse match data for each spouse
6. **Lines 1268-1269**: Return new fields in result dictionary

### Batch Processing Data Collection

**File**: `src/rmcitecraft/ui/tabs/findagrave_batch.py`

**Lines 818-819**: Initialize report data collection
```python
citation_report_data = []  # Collect match data for report
```

**Lines 1070-1077**: Collect match data during processing
```python
if family_link_result.get('spouse_matches') or family_link_result.get('parent_match_info'):
    citation_report_data.append({
        'person_name': item.full_name,
        'person_id': item.person_id,
        'spouse_matches': family_link_result.get('spouse_matches', []),
        'parent_match_info': family_link_result.get('parent_match_info'),
    })
```

**Lines 1123-1125**: Display report after batch completes
```python
if citation_report_data:
    self._show_citation_matching_report(citation_report_data)
```

### Report Display Component

**File**: `src/rmcitecraft/ui/tabs/findagrave_batch.py`  
**Method**: `_show_citation_matching_report()` (Lines 778-859)

**Features**:
- Maximized dialog for full-screen display
- Separate sections for spouse and parent matches
- Color-coded text (green/red) based on match success
- Grid layout for spouse table (6 columns)
- Summary statistics for parent matches
- Shows only failures for parent section
- Close button to dismiss report

**Color Coding Logic**:
```python
matched = spouse_match['matched']  # True if >= 60%
text_color = 'text-green-700' if matched else 'text-red-700'
```

## Example Report

### Spouse Matching

```
Spouse Citation Matches
3 entries with spouse data

Target Name          Person ID  RM Spouse Name        Spouse ID  Find a Grave Name              Match %
James Harvey Iams    1245       Frances Dora Iams     3337       Frances Davis Iams 1877–1945   87.8%   (GREEN)
Thomas Iams          1234       Mary Smith            2345       Mary Smith 1850-1920           100.0%  (GREEN)
Elizabeth Brown      5678       John Doe              NULL       Jonathan Doe Jr.               42.3%   (RED)
```

### Parent Matching

```
Parent Citation Matches
(14/15) entries with parents successfully cited

Failures:
  Thomas Iams (Person ID 1234) - No parent family found in database
```

## User Experience Flow

1. User starts batch processing (selects items and clicks "Process")
2. Progress dialog shows while processing (existing behavior)
3. **Progress dialog closes**
4. **NEW: Citation matching report displays** (maximized dialog)
5. User reviews match results
6. User clicks "Close" to dismiss report
7. Completion notification shows (existing behavior)
8. UI refreshes (existing behavior)

## Benefits

### For Users
- **Visibility** - See which spouses matched and which didn't
- **Quality assurance** - Verify match percentages before accepting
- **Debugging** - Identify mismatches quickly
- **Confidence** - Green/red colors provide instant feedback

### For Data Quality
- **Transparency** - All matches shown with scores
- **Auditability** - Can track which names matched which variations
- **Validation** - Can verify 60% threshold is appropriate
- **Learning** - Can identify name variations that need attention

## Technical Notes

### Match Score Calculation

Uses Python's `difflib.SequenceMatcher` for sequence-based similarity:
- **0%** - Completely different strings
- **60%** - Threshold for spouse matching
- **100%** - Exact match

Example:
- `"Frances Davis Iams"` vs `"Frances Dora Iams"` → 85.7%
- `"Frances Iams"` vs `"Frances Iams"` → 100%
- `"Mary Smith"` vs `"Jane Doe"` → ~20%

### Database Name Variations

The report shows the **best matching variation** from the 7 generated:
1. Full maiden: `"Frances Dora Davis"`
2. First + maiden: `"Frances Davis"`
3. First + MI + maiden: `"Frances D. Davis"`
4. Full married: `"Frances Dora Iams"`
5. Full + maiden + married: `"Frances Dora Davis Iams"`
6. First + married: `"Frances Iams"`
7. First + MI + married: `"Frances D. Iams"`

The variation with the highest match score is displayed in the report.

### Performance Impact

- **Data collection**: Negligible (~1ms per spouse)
- **Report display**: Only shown if there's data to report
- **UI rendering**: Maximized dialog, efficient grid layout
- **No database queries**: All data collected during processing

## Future Enhancements

### Potential Improvements
1. **Export to CSV** - Allow saving report for records
2. **Retry failed matches** - Button to manually review/edit failed matches
3. **Show all variations** - Expandable view showing all 7 variations tested
4. **Parent names** - Show actual parent names from Find a Grave and database
5. **Match threshold adjustment** - Allow user to adjust 60% threshold
6. **Filtering** - Filter by success/failure, match percentage range
7. **Sorting** - Sort by match percentage, person name, etc.

### Code Organization
- Consider extracting report component to separate file
- Add unit tests for report data transformation
- Document report data structure in type hints

## Testing

**Manual Testing Required**:
1. Process batch with varied spouse names
2. Verify green/red color coding
3. Check parent summary counts
4. Test with no spouses/parents
5. Verify report doesn't show for entries without family data

**Automated Testing**:
- Unit tests for `link_citation_to_families()` return format ✓
- Spouse matching tests (6 tests passing) ✓
- Integration tests for report display (future)

## References

- **Spouse matching enhancement**: `docs/ENHANCED_VARIATIONS_SUMMARY.md`
- **Original bug fix**: `docs/implementation/SPOUSE-NAME-MATCHING-FIX.md`
- **Code**: `src/rmcitecraft/database/findagrave_queries.py:996-1270`
- **UI**: `src/rmcitecraft/ui/tabs/findagrave_batch.py:778-859`
- **Tests**: `tests/unit/test_spouse_name_matching.py`
