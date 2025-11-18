# Spouse Name Matching Enhancement

**Date**: 2025-11-17  
**Issue**: PersonID 1245 spouse family not receiving citation link  
**Root Cause**: Inadequate name normalization in `link_citation_to_families()`  

## Problem Description

### The Bug

When processing Find a Grave citations for PersonID 1245 (James Harvey Iams), the citation was correctly linked to the parent family (FamilyID 441) but **failed to link** to the spouse family (FamilyID 1149).

**Database State**:
- Subject: James Harvey Iams (PersonID 1245, surname "Iams")
- Spouse: Frances Dora Davis (PersonID 3337, maiden name in database)
- Spouse Family: FamilyID 1149 (James + Frances)

**Find a Grave Data**:
- Spouse listed as: `"Frances Davis Iams 1877–1945 (m. 1898)"`

**Original Code Behavior**:
```python
# Line 1113 - BUGGY LOGIC
fg_name_clean = re.sub(r'\([^)]*\)', '', fg_spouse_name).strip()
fg_name_clean = ' '.join(fg_name_clean.split())

# Result: "Frances Davis Iams 1877–1945"  (dates NOT removed!)
# vs DB: "Frances Dora Davis"
# Similarity: 56.52% ✗ BELOW 60% threshold
```

### Why It Failed

The original regex only removed **parenthetical text** `(m. 1898)` but left the **date range** `1877–1945` in the name, causing:
1. Low similarity score (56.52% < 60% threshold)
2. No recognition that "Iams" is the married name (subject's surname)
3. No attempt to match maiden name variations

## Solution: Comprehensive Name Matching

### Enhanced Strategy

The fix implements a **multi-variation matching approach**:

1. **Generate Find a Grave name variations** (4 variations):
   - Original with whitespace normalized
   - Remove parenthetical text `(m. 1898)`
   - Remove parenthetical + date ranges `1877–1945`
   - Remove dates + subject's surname (extract maiden name)

2. **Generate database name variations** (includes married names):
   - Maiden name: `"Frances Dora Davis"`
   - Married name: `"Frances Dora Iams"` (with subject's surname)
   - Full name: `"Frances Dora Davis Iams"`

3. **Compare all combinations** (4 FG × 3 DB = 12 comparisons)
4. **Select highest match score**

### Code Changes

**File**: `src/rmcitecraft/database/findagrave_queries.py`

**Lines 998-1006**: Added subject surname lookup
```python
# Get subject's surname for spouse name matching
cursor.execute("""
    SELECT Surname
    FROM NameTable
    WHERE OwnerID = ? AND IsPrimary = 1
""", (person_id,))
subject_surname_row = cursor.fetchone()
subject_surname = subject_surname_row[0] if subject_surname_row else None
```

**Lines 1122-1169**: Enhanced name variation generation
```python
# Generate multiple normalized variations of Find a Grave name
fg_name_variations = []

# Variation 1: Original (just remove extra whitespace)
fg_name_variations.append(' '.join(fg_spouse_name.split()))

# Variation 2: Remove parenthetical text (m. YYYY)
v2 = re.sub(r'\([^)]*\)', '', fg_spouse_name).strip()
fg_name_variations.append(' '.join(v2.split()))

# Variation 3: Remove parenthetical + date ranges (YYYY–YYYY or YYYY-YYYY)
v3 = re.sub(r'\([^)]*\)', '', fg_spouse_name).strip()
v3 = re.sub(r'\d{4}\s*[–-]\s*\d{4}', '', v3).strip()
fg_name_variations.append(' '.join(v3.split()))

# Variation 4: Remove dates + subject surname at end (to get maiden name)
v4 = re.sub(r'\([^)]*\)', '', fg_spouse_name).strip()
v4 = re.sub(r'\d{4}\s*[–-]\s*\d{4}', '', v4).strip()
if subject_surname and v4.lower().endswith(subject_surname.lower()):
    v4 = v4[:-(len(subject_surname))].strip()
fg_name_variations.append(' '.join(v4.split()))

# Build database name variations (including married name)
db_name_variations = db_names.copy()

if subject_surname and given:
    # Given + Subject Surname (married name)
    db_name_variations.append(f"{given} {subject_surname}")
    
    # Given + Middle + Subject Surname (married name with middle)
    if surname:  # Use maiden surname as middle name
        db_name_variations.append(f"{given} {surname} {subject_surname}")

# Compare each Find a Grave variation against each database variation
for fg_var in fg_name_variations:
    for db_var in db_name_variations:
        similarity = SequenceMatcher(None, fg_var.lower(), db_var.lower()).ratio()
        if similarity > best_match_score:
            best_match_score = similarity
```

## Results

### PersonID 1245 Test Case

**Before Fix**:
- FG: `"Frances Davis Iams 1877–1945 (m. 1898)"`
- DB: `"Frances Dora Davis"`
- Best match: `"Frances Davis Iams 1877–1945"` vs `"Frances Dora Davis"`
- Similarity: **56.52%** ✗ NO MATCH

**After Fix**:
- FG: `"Frances Davis Iams 1877–1945 (m. 1898)"`
- DB: `"Frances Dora Davis"`
- Best match: `"Frances Davis Iams"` vs `"Frances Dora Davis Iams"`
- Similarity: **87.8%** ✓ MATCH

### Supported Variations

The enhanced matching now handles:

| Find a Grave Format | Database Format | Match Score |
|---------------------|-----------------|-------------|
| "Frances Davis Iams 1877–1945 (m. 1898)" | "Frances Dora Davis" (maiden) | 87.8% ✓ |
| "Frances Davis" (maiden only) | "Frances Dora Davis" | 83.9% ✓ |
| "Frances Iams" (married only) | "Frances Dora Davis" | 82.8% ✓ |
| "Frances D. Iams (1877-1945)" | "Frances Dora Davis" | 87.5% ✓ |

### Date Format Handling

- En-dash: `1877–1945`
- Hyphen: `1877-1945`  
- In parentheses: `(1877-1945)`
- Marriage dates: `(m. 1898)`, `(married 1898)`

## Testing

**Test File**: `tests/unit/test_spouse_name_matching.py`

**Test Coverage**:
1. `test_personid_1245_bug_fix` - Validates the specific bug case
2. `test_maiden_name_only` - FG has maiden name only
3. `test_married_name_only` - FG has married name only
4. `test_with_middle_initial` - Handles middle initials
5. `test_different_date_formats` - Various date formats

**All 5 tests pass** ✓

## Performance Impact

- **Comparisons**: 12 per spouse (4 FG variations × 3 DB variations)
- **Overhead**: Minimal (~1ms per spouse)
- **Benefit**: Significantly improved match rate for real-world name variations

## Migration Notes

**No database migration required** - this is a pure code fix.

Existing citations can be re-processed using the batch tool to link any previously unmatched spouse families.

## Related Issues

- Parent family matching already worked correctly (exactly 2 parents check)
- Only spouse matching was affected by inadequate name normalization
- Fix improves robustness for all Find a Grave batch processing

## References

- **Code**: `src/rmcitecraft/database/findagrave_queries.py:996-1169`
- **Tests**: `tests/unit/test_spouse_name_matching.py`
- **Commit**: (to be added)
