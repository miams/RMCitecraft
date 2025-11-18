# RootsMagic Gazetteer Integration

## Overview

RootsMagic ships with a worldwide gazetteer database containing 5.3+ million place names.

- **File**: `/Applications/RootsMagic 11.app/Contents/MacOS/PlaceDB.dat`
- **Size**: 137 MB
- **Format**: Proprietary binary (custom indexed format)
- **Date**: October 4, 2006 (static reference data)
- **Read-only**: Yes

## File Format

The PlaceDB.dat file uses a proprietary binary format (not SQLite, not dBase, not Berkeley DB).

**Structure:**
- Binary index/header (first ~7.5 MB)
- Place name records with metadata
- Each record: `[length_byte][place_name_string][metadata_bytes]`

**Limitations:**
- Cannot fully parse the binary structure
- Cannot extract hierarchical relationships programmatically
- Can search for place name strings using binary search

## RootsMagic Gazetteer Functionality (Confirmed)

**MAJOR DISCOVERY**: RootsMagic's Gazetteer uses a **hybrid search system**, not just PlaceDB.dat!

### Three-Tier System

1. **User's PlaceTable** (from your .rmtree database)
   - Full hierarchies you've already entered
   - Searched first (highest priority)
   - Score: 10000 for exact matches
   - Example: "Phoenix, Maricopa, Arizona, United States"

2. **PlaceDB.dat** (worldwide gazetteer)
   - 2.5M individual place components
   - Supplements user data with worldwide suggestions
   - Score: 5000-9000 for matches
   - Example: "Phoenix", "Maricopa", "Arizona" (separate components)

3. **CountyCheckDB.dat** (historical validation - 357 KB)
   - US counties, states, territories over time
   - International provinces
   - Validates jurisdictional changes (e.g., "Arizona Territory" → "Arizona" in 1912)
   - 3,245 county records with temporal data

### Search Behavior

**With comma** ("Phoenix,az"):
- Tokenizes on comma, searches hierarchical components
- Prioritizes user's existing places
- Result: "Phoenix, Maricopa, Arizona, United States" (score: 10000)

**Without comma** ("Phoenix az"):
- Full-text fuzzy search across entire strings
- May return unrelated matches (e.g., "Fengxi, Zhejiang, China")

### What PlaceDB.dat Actually Contains

- ✓ **Individual place components** - "Phoenix", "Maricopa", "Arizona"
- ✓ **Fuzzy matching support** - Via search algorithm
- ✓ **International coverage** - Worldwide place names
- ✗ **No full hierarchies** - Those come from user's PlaceTable
- ✗ **No geocoding** - No coordinates stored
- ✗ **No hierarchy links** - Cannot extract parent/child relationships

## Usage in RMCitecraft

### Gazetteer Search Utility

```python
from rmcitecraft.utils.gazetteer_search import GazetteerSearch

# Initialize
searcher = GazetteerSearch()

# Search for places
results = searcher.search("Princeton", max_results=20)
# Returns: ['PRINCETON TOWNSHIP', 'Princeton', 'Princeton Junction', ...]

# Check if place exists
exists = searcher.exists("Princeton", fuzzy=True)
# Returns: True

# Validate hierarchy components (NOT full hierarchy)
validation = searcher.validate_hierarchy(
    city="Princeton",
    state="New Jersey",
    country="United States"
)
# Returns: {'city': True, 'state': True, 'country': True, ...}

# Get suggestions for autocomplete
suggestions = searcher.suggest_places("Prince")
# Returns: ['PRINCETON TOWNSHIP', 'Princeton', ...]
```

**Note:** The gazetteer validates individual place name components, not full hierarchies like "Princeton, Mercer, New Jersey, United States".

### Integration with Place Approval Dialog

The gazetteer can be used to:

1. **Validate Find a Grave locations** before adding to database
2. **Suggest corrections** for misspelled or non-standard place names
3. **Provide autocomplete** when user manually enters places
4. **Verify place hierarchies** (city, county, state, country)

### Known Places in Gazetteer

**US States:**
- ✓ All 50 US states (e.g., "Ohio", "Texas", "New Jersey", "California")
- ✓ "United States" country name

**Counties:**
- ✓ Major US counties (e.g., "Mercer", "Noble", "Milam", "Baltimore")
- ⚠️ Some counties may not be present as standalone entries

**Cities:**
- ✓ Major US cities and towns (e.g., "Princeton")
- ✓ Township variants (e.g., "Princeton Township")
- ✓ Historical places (e.g., "Princeton (historical)")

**International:**
- ✓ Worldwide place names from all countries
- ✓ Multiple languages and transliterations

## Search Limitations

1. **Substring matches**: Searching "Ohio" also finds "BOHIO", "AMBOHIOMBY"
2. **Metadata artifacts**: Some results include binary metadata characters
3. **Case variations**: Same place may appear as "Ohio" and "OHIO"
4. **No hierarchy info**: Cannot determine that "Princeton" is in "Mercer County"

## Recommendations

### For Place Validation

**Do:**
- Use fuzzy matching (default threshold: 0.90)
- Search for individual components (city, county, state separately)
- Normalize names before searching (remove "County", "Township", etc.)

**Don't:**
- Rely on exact matches only (too strict)
- Search for full hierarchical names (e.g., "Princeton, Mercer, New Jersey")
- Assume a missing place doesn't exist (may be formatting issue)

### For Place Approval Dialog

**Current workflow:**
1. User gets "Insufficient place match" notification
2. Dialog shows Find a Grave location and proposed new place
3. **Enhancement**: Add gazetteer validation indicator:
   - ✓ Green: Location components found in gazetteer
   - ⚠️ Yellow: Partial match or fuzzy match
   - ✗ Red: Not found in gazetteer (may need correction)

**Example:**
```
Find a Grave Location: Princeton, Mercer County, New Jersey, USA
Proposed Place: Princeton, Mercer, New Jersey, United States

Gazetteer Validation:
  ✓ Princeton         - Found (exact)
  ✓ Mercer            - Found (exact)
  ✓ New Jersey        - Found (exact)
  ✓ United States     - Found (exact)
```

## CountyCheckDB.dat

RootsMagic also ships with `CountyCheckDB.dat` (357 KB), likely containing US county validation data. This file uses the same proprietary format as PlaceDB.dat and could be searched similarly if needed.

## Future Enhancements

1. **Postal abbreviation support**: Add US state abbreviation lookup table
   - Map "NJ" → "New Jersey", "CA" → "California", etc.
   - Easy to implement (50-state lookup dictionary)
   - Matches RootsMagic behavior

2. **Enhanced fuzzy matching**: Improve similarity algorithm
   - Current: SequenceMatcher (ratio-based)
   - Consider: Soundex for phonetic matching
   - Handle common typos and abbreviations

3. **Create SQLite index**: Convert gazetteer to SQLite for faster queries
   - One-time conversion: PlaceDB.dat → places.db
   - Full-text search indexing
   - Faster than binary file search

4. **County-specific validation**: Use CountyCheckDB.dat for US county validation
   - Reverse-engineer CountyCheckDB.dat (357 KB, similar format)
   - May contain US-specific county data
   - Useful for census place validation

5. **Autocomplete in UI**: Integrate suggestions into place input fields
   - Real-time search as user types
   - Dropdown with top 10 matches
   - Reduce typos and standardize spelling

~~**Reverse-engineer hierarchy**~~: Not possible - hierarchy links not stored in file (confirmed via RootsMagic testing)

## Alternative Approaches

If gazetteer proves insufficient:

1. **GeoNames**: Use free GeoNames.org database (downloadable as tab-delimited files)
2. **Google Places API**: Geocoding and place validation (requires API key, costs money)
3. **User's PlaceTable**: Continue using fuzzy matching against user's own database
4. **Hybrid approach**: Validate against gazetteer + user's PlaceTable

## Code Location

- **Utility**: `/src/rmcitecraft/utils/gazetteer_search.py`
- **Test script**: `/scripts/test_gazetteer.py`
- **Documentation**: `/docs/GAZETTEER.md` (this file)

## Testing

Run the test script to verify gazetteer functionality:

```bash
uv run python scripts/test_gazetteer.py
```

Expected output:
- ✓ Searches for common US places
- ✓ Validates place hierarchies
- ✓ Provides place suggestions
- ✓ Confirms Find a Grave locations exist

## Summary

The RootsMagic gazetteer is a valuable resource for place validation and suggestions, despite its proprietary format. While we cannot fully parse the binary structure, we can effectively search for place names and integrate validation into the place approval workflow.

**Key takeaway**: Use gazetteer as a **supplementary validation tool**, not primary source. Continue relying on user's PlaceTable as the authoritative source, with gazetteer providing hints and validation.
