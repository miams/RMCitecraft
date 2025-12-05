---
priority: reference
topics: [database, census, citation, batch, findagrave]
---

# CountyCheckDB.dat - Historical Place Validation

**RootsMagic's historical jurisdictional database for temporal place validation**

---

## Overview

- **File**: `/Applications/RootsMagic 11.app/Contents/MacOS/CountyCheckDB.dat`
- **Size**: 357 KB (365,336 bytes)
- **Format**: Paradox-like database (same as PlaceDB.dat)
- **Created**: March 19, 2022
- **Copyright**: © 2011 RootsMagic, Inc.

## Purpose

Validates that a place or jurisdiction existed at a specific point in time, accounting for:
- County boundary changes
- Territorial transitions to statehood
- County creations/mergers/splits
- Jurisdictional renames

## Contents

**Header description** (from file):
> "The CountyCheck database covers counties, states, and provinces..."

**Data sources referenced:**
- FamilySearch Wiki: `https://www.familysearch.org/learn/wiki/en`
- Newberry Historical County Boundaries: `http://historical-county.newberry.org/website`
- Wikipedia: `http://en.wikipedia.org/wiki`

**Records:**
- ~54 main jurisdictions (US states, territories, international provinces)
- 3,245 county entries
- Temporal data for jurisdictional changes

## Examples of Historical Transitions

### Statehood Transitions

**Arizona:**
- Before 1912: "Arizona Territory"
- After Feb 14, 1912: "Arizona"

**North Dakota / South Dakota:**
- Before 1889: "Dakota Territory"
- After Nov 2, 1889: "North Dakota" and "South Dakota" (split)

**Oklahoma:**
- Before 1907: "Oklahoma Territory" and "Indian Territory"
- After Nov 16, 1907: "Oklahoma"

### County Changes

**Maricopa County, Arizona:**
- Created: 1871 (as part of Arizona Territory)
- Parent: Yavapai County
- Statehood transition: 1912 (Arizona Territory → Arizona)

## Importance for Census Citations

Census citations must use **historically accurate place names** for the census year:

**Correct:**
- 1900 census: "Phoenix, Maricopa, Arizona Territory"
- 1880 census: "Bismarck, Burleigh, Dakota Territory"

**Incorrect:**
- 1900 census: ~~"Phoenix, Maricopa, Arizona"~~ (statehood not until 1912)
- 1880 census: ~~"Bismarck, Burleigh, North Dakota"~~ (didn't exist until 1889)

## File Structure

Same Paradox-like format as PlaceDB.dat:

```
Header:
  Offset 0x00-0x01: 257 (0x0101) - Version/record size
  Offset 0x02-0x03: 35,230 - Header size
  Offset 0x06-0x09: 54 - Record count (main jurisdictions)
```

Contains:
- Jurisdiction names (counties, states, territories, provinces)
- Parent jurisdictions
- Creation dates
- Dissolution dates (if applicable)
- Boundary change dates

## Current Status in RMCitecraft

**Not yet implemented** - PlaceDB.dat analysis and documentation complete.

### Future Enhancement Opportunities

1. **Historical Census Validation**
   - Validate place names against census year
   - Suggest correct territorial names for pre-statehood dates
   - Auto-correct "Arizona" → "Arizona Territory" for 1900 census

2. **Place Name Auto-Correction**
   - Detect modern state names in historical records
   - Offer correction: "Would you like to use 'Arizona Territory' for 1900?"

3. **Temporal Place Search**
   - Search CountyCheckDB.dat with date parameter
   - Return only jurisdictions that existed in specified year
   - Useful for citation templates by census year

4. **County Parent Lookup**
   - Identify parent counties for county formations
   - Useful for understanding jurisdictional splits

## Integration Approach

If implementing CountyCheckDB.dat validation:

1. **Parse similar to PlaceDB.dat** - Same Paradox format, use string search
2. **Build temporal index** - Map jurisdiction → date ranges
3. **Validate during citation creation** - Check year against jurisdiction dates
4. **Suggest corrections** - Offer historically accurate alternatives

## ROI Assessment

**Medium priority** for RMCitecraft:
- ✓ Improves citation accuracy (important for genealogy)
- ✓ Relatively small file (357 KB vs 137 MB for PlaceDB.dat)
- ⚠️ Requires parsing similar to PlaceDB.dat (same effort)
- ⚠️ Most users may not notice territorial vs state differences

**Recommendation:** Defer until after core features complete. Focus on Find a Grave batch processing first.

## References

- **Newberry Library**: Historical county boundary database (primary source)
- **FamilySearch Wiki**: Place name standardization guidelines
- **Evidence Explained**: Citation formatting standards for historical jurisdictions

---

**Document Version:** 1.0
**Last Updated:** 2025-11-17
**Status:** Analysis complete, implementation deferred
