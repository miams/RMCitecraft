---
priority: reference
topics: [database, census, citation, testing, ui]
---

# Punctuation and Abbreviation Corrections

**Date**: 2025-10-25
**Reference**: Mills, Elizabeth Shown. *Evidence Explained: Citing History Sources from Artifacts to Cyberspace: 4th Edition*.

---

## Issues Identified

### 1. State Abbreviations Using Postal Codes

**Problem**: Short footnotes were using 2-letter postal codes (PA, OH, etc.) instead of traditional abbreviations.

**User Feedback**:
> "On the short footnote, you should abbreviate the state, but you need to use official abbreviation, not the postal code abbreviation. A lookup table of states abbreviations should be used."

**Examples**:
- ❌ Wrong: `PA` (postal code)
- ✅ Correct: `Pa.` (traditional abbreviation)
- ❌ Wrong: `OH` (postal code)
- ✅ Correct: `Ohio` (no abbreviation - some states not abbreviated)

### 2. Punctuation Outside Quotation Marks in Bibliography

**Problem**: Period was placed outside the closing quotation mark.

**User Feedback**:
> "Also, in the bibliography, punctuation goes inside a closing quotation mark."

**Example**:
- ❌ Wrong: `"1930 United States Federal Census". <i>FamilySearch</i>`
- ✅ Correct: `"1930 United States Federal Census." <i>FamilySearch</i>`

---

## Corrections Applied

### Fix 1: Traditional State Abbreviations

**File**: `src/rmcitecraft/config/constants.py`

Replaced postal code table with traditional Evidence Explained abbreviations:

```python
# US State abbreviations (traditional style for Evidence Explained citations)
# Reference: Mills, Elizabeth Shown. Evidence Explained, 4th Edition.
# Note: These are NOT postal codes (PA → Pa., OH → Ohio, etc.)
STATE_ABBREVIATIONS: Dict[str, str] = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    "Connecticut": "Conn.",
    "Delaware": "Del.",
    "Florida": "Fla.",
    "Georgia": "Ga.",
    "Hawaii": "Hawaii",
    "Idaho": "Idaho",
    "Illinois": "Ill.",
    "Indiana": "Ind.",
    "Iowa": "Iowa",
    "Kansas": "Kans.",
    "Kentucky": "Ky.",
    "Louisiana": "La.",
    "Maine": "Maine",
    "Maryland": "Md.",
    "Massachusetts": "Mass.",
    "Michigan": "Mich.",
    "Minnesota": "Minn.",
    "Mississippi": "Miss.",
    "Missouri": "Mo.",
    "Montana": "Mont.",
    "Nebraska": "Nebr.",
    "Nevada": "Nev.",
    "New Hampshire": "N.H.",
    "New Jersey": "N.J.",
    "New Mexico": "N.Mex.",
    "New York": "N.Y.",
    "North Carolina": "N.C.",
    "North Dakota": "N.Dak.",
    "Ohio": "Ohio",
    "Oklahoma": "Okla.",
    "Oregon": "Oreg.",
    "Pennsylvania": "Pa.",
    "Rhode Island": "R.I.",
    "South Carolina": "S.C.",
    "South Dakota": "S.Dak.",
    "Tennessee": "Tenn.",
    "Texas": "Tex.",
    "Utah": "Utah",
    "Vermont": "Vt.",
    "Virginia": "Va.",
    "Washington": "Wash.",
    "West Virginia": "W.Va.",
    "Wisconsin": "Wis.",
    "Wyoming": "Wyo.",
    # Historical territories and districts
    "District of Columbia": "D.C.",
    "Dakota Territory": "Dakota Terr.",
    "Indian Territory": "Indian Terr.",
    "Nebraska Territory": "Nebr. Terr.",
    "New Mexico Territory": "N.Mex. Terr.",
    "Oklahoma Territory": "Okla. Terr.",
    "Washington Territory": "Wash. Terr.",
}
```

**Key Patterns**:
- Most states: Add period after abbreviation (`Calif.`, `Colo.`, `Conn.`)
- Multi-word states: Use initials with periods (`N.Y.`, `N.H.`, `W.Va.`)
- Some states NOT abbreviated: `Alaska`, `Hawaii`, `Idaho`, `Iowa`, `Maine`, `Ohio`, `Utah`
- Territories: Full word "Territory" abbreviated as "Terr."

**Also updated**: `src/rmcitecraft/services/citation_formatter.py` (duplicate table)

### Fix 2: Punctuation Inside Quotation Marks

**Files**:
- `src/rmcitecraft/services/citation_formatter.py` (line 195)
- `src/rmcitecraft/parsers/citation_formatter.py` (line 132)

**Change**:
```python
# Before
f'"{extraction.year} United States Federal Census". '

# After
f'"{extraction.year} United States Federal Census." '
```

The period now appears **inside** the closing quotation mark per standard American English punctuation rules.

---

## Corrected Output Examples

### Short Footnote (State Abbreviation)
```
1930 U.S. census, Greene Co., Pa., pop. sch., Jefferson, E.D. 30-17, sheet 13-A, George B Iams.
```

**Key Elements**:
- ✅ `Pa.` not `PA`
- ✅ Period after state abbreviation
- ✅ Comma after `Pa.`

### Bibliography (Punctuation)
```
U.S. Pennsylvania. Greene County. 1930 U.S Census. Imaged. "1930 United States Federal Census." <i>FamilySearch</i> https://www.familysearch.org/ark:/61903/1:1:XH3Z-4J8 : 2020.
```

**Key Elements**:
- ✅ Period inside closing quotation mark: `Census."`
- ✅ Space between quotation mark and `<i>`

---

## State Abbreviation Reference Table

| State | Traditional Abbreviation | Postal Code (DON'T USE) |
|-------|-------------------------|------------------------|
| Alabama | Ala. | AL |
| Alaska | Alaska | AK |
| Arizona | Ariz. | AZ |
| California | Calif. | CA |
| Connecticut | Conn. | CT |
| Delaware | Del. | DE |
| Georgia | Ga. | GA |
| Hawaii | Hawaii | HI |
| Idaho | Idaho | ID |
| Illinois | Ill. | IL |
| Indiana | Ind. | IN |
| Iowa | Iowa | IA |
| Kansas | Kans. | KS |
| Kentucky | Ky. | KY |
| Louisiana | La. | LA |
| Maine | Maine | ME |
| Maryland | Md. | MD |
| Massachusetts | Mass. | MA |
| Michigan | Mich. | MI |
| Minnesota | Minn. | MN |
| Mississippi | Miss. | MS |
| Missouri | Mo. | MO |
| Montana | Mont. | MT |
| Nebraska | Nebr. | NE |
| Nevada | Nev. | NV |
| New Hampshire | N.H. | NH |
| New Jersey | N.J. | NJ |
| New Mexico | N.Mex. | NM |
| New York | N.Y. | NY |
| North Carolina | N.C. | NC |
| North Dakota | N.Dak. | ND |
| Ohio | Ohio | OH |
| Oklahoma | Okla. | OK |
| Oregon | Oreg. | OR |
| Pennsylvania | Pa. | PA |
| Rhode Island | R.I. | RI |
| South Carolina | S.C. | SC |
| South Dakota | S.Dak. | SD |
| Tennessee | Tenn. | TN |
| Texas | Tex. | TX |
| Utah | Utah | UT |
| Vermont | Vt. | VT |
| Virginia | Va. | VA |
| Washington | Wash. | WA |
| West Virginia | W.Va. | WV |
| Wisconsin | Wis. | WI |
| Wyoming | Wyo. | WY |

---

## Files Modified

1. **`src/rmcitecraft/config/constants.py`**
   - Lines 48-110: Replaced STATE_ABBREVIATIONS with traditional abbreviations
   - Added documentation comments citing Evidence Explained

2. **`src/rmcitecraft/services/citation_formatter.py`**
   - Lines 10-64: Updated STATE_ABBREVIATIONS table
   - Line 195: Moved period inside quotation mark

3. **`src/rmcitecraft/parsers/citation_formatter.py`**
   - Line 132: Moved period inside quotation mark

4. **`tests/test_george_iams_citation.py`**
   - Updated expected output to match corrected formats

---

## Testing

Run test to verify both corrections:

```bash
uv run python tests/test_george_iams_citation.py
```

Expected results:
- ✅ Short footnote uses `Pa.` not `PA`
- ✅ Bibliography has period inside quotation mark
- ✅ All three citation formats validated

---

**Last Updated**: 2025-10-25
**Status**: Both corrections applied and tested
