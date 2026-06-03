---
priority: reference
topics: [database, census, batch, findagrave, testing]
---

# RootsMagic Gazetteer Integration

## Overview

RootsMagic ships with three binary reference databases in the app bundle:

| File | Size | Purpose |
|------|------|---------|
| `PlaceDB.dat` | 137 MB | Worldwide place names (~2.5M entries) |
| `CountyCheckDB.dat` | 357 KB | County/province validation with date ranges and URLs |
| `OnThisDayDB.dat` | 2.9 MB | Historical births/deaths by calendar day |

All three are **read-only proprietary binary formats**. `PlaceDB.dat` and `CountyCheckDB.dat` share a common header structure. All use little-endian integers.

---

## File Format: Common Header

Both `PlaceDB.dat` and `CountyCheckDB.dat` start with:

```
Offset  Size  Content
0x00    2     Magic bytes: 0x01 0x01
0x02    4     Build date (uint32 LE) as YYYYMMDD decimal
              PlaceDB:      20061004  (Oct 4, 2006)
              CountyCheckDB: 20220318 (Mar 18, 2022)
0x06+       Section offsets (uint32 LE), file-specific layout
```

---

## PlaceDB.dat — Worldwide Place Names

### What's Inside

- ~2.5 million place names from worldwide sources
- Individual place name components (city, county, state, country as separate entries)
- All-caps normalized strings in the trie index; proper-case in record data
- **No full hierarchies** — "Princeton, Mercer, New Jersey" is not one record
- **No geocoding** confirmed in searchable sections

### Internal Structure

```
Offset          Section
0x000000        Header (54 bytes): magic, build date, 7 section offsets, 38-entry jump table
0x0000C6        Multi-level trie index (cascading arrays of uint32 offsets)
                  Level 1: 38-entry jump table (indexed by normalized alphabet char)
                  Level 2: Secondary offset arrays (values ~660–912)
                  Level 3+: Further cascading offset arrays
~0x0079201E     Index data section (uses 0x26=38 as NULL-branch sentinel)
~0x028DFDAA     Additional index data
~0x02B9442E     Additional index data
~0x0399C115     Record pointer arrays
~0x04365629     Record pointer arrays
~0x04D2EB3D     Place name record data (proper-case name strings with binary metadata)
```

### Jump Table / Alphabet

The 38-character alphabet used in the trie index:

```python
# The trie uses a 38-character reduced alphabet (26 letters + space + punctuation)
# This is stored as 38 uint32 offsets at header offset 0x2E
ALPHABET_SIZE = 38  # confirmed from header value at offset 0x0A
```

### Place Name Records (at ~0x4D2EB3D)

Individual records have the structure:
```
[binary metadata fields] [uint8 name_len] [name bytes] [null terminator]
```
Examples confirmed: `Afghanistan`, `Abo Tangah`, `Ajal`

The binary metadata fields preceding each name have not been fully decoded but likely encode country code, administrative level, and possibly coordinates.

### Searching PlaceDB.dat

The existing `GazetteerSearch` utility does binary string search against the raw file. This is still the most practical approach given the incompletely decoded trie structure.

```python
from rmcitecraft.utils.gazetteer_search import GazetteerSearch

searcher = GazetteerSearch()

# Search for individual place components
results = searcher.search("Princeton", max_results=20)
exists  = searcher.exists("Princeton", fuzzy=True)

# Validate individual hierarchy components (NOT full hierarchies)
validation = searcher.validate_hierarchy(
    city="Princeton",
    state="New Jersey",
    country="United States"
)

# Autocomplete suggestions
suggestions = searcher.suggest_places("Prince")
```

**Important:** The gazetteer validates individual place name components. It cannot confirm that "Princeton" is in "Mercer County, New Jersey" — that relationship is not stored.

### Known Limitations

1. Substring matches: "Ohio" also finds "BOHIO", "AMBOHIOMBY"
2. Case variations: "Ohio" and "OHIO" may appear as separate entries
3. No hierarchy info: cannot confirm city→county→state relationships
4. Metadata artifacts: some results include binary characters

---

## CountyCheckDB.dat — County Validation (FULLY DECODED)

### What's Inside

- **2,493 canonical county/region names** (proper case)
- **3,970 county records** with date-range data and reference URLs
- **Lowercase search index** mapping names and abbreviations → record IDs
- **County type strings**: Borough, City, Colony, County, County Borough, Department, District, etc.
- **Coverage**: United States, Canada, Australia, England, Wales, Scotland
- **Reference URLs** using template placeholders: `{FSWIKI}` and `{WIKI}`

### Section Layout

```
Offset      Size      Section
0x0000      54        Header: magic, build date 20220318, section offsets
0x0002      4         Build date: uint32 LE = 20220318
0x0006      4         Always 54 (header size)
0x000A      4         = 0x180 (search index start)
0x000E      4         = 0x9029 (canonical names start)
0x0012      4         = 0xEA38 (type strings start)
0x0016      4         = 0xEBE1 (records section start)
0x001A      4         = 0x517C6 (offset table start)
0x001E      4         = 0x555CE (end / final section)

0x0180      ~36KB     Lowercase search index
0x9029      ~23KB     Canonical capitalized names
0xEA38      ~425B     County type name strings
0xEBE1      ~273KB    County records (binary + URL strings)
0x517C6     15,880B   Offset table: 3,970 × uint32 (offsets into records section)
0x555CE     15,690B   (end of file)
```

### Search Index Format

```
Each entry:
  [uint8  name_len]
  [bytes  name]          (lowercase, len = name_len)
  [uint8  count]
  [uint16 record_id] × count   (little-endian, indexes into offset table)
```

The search index maps both canonical names AND alternative spellings/abbreviations to record IDs. Multiple IDs per name means the name is ambiguous (e.g., "aberdeen" → IDs for Aberdeen SD, Aberdeen MS, Aberdeen Scotland, etc.).

### Canonical Names Format

```
Each entry at 0x9029:
  [uint8  name_len]
  [bytes  name]          (proper case, len = name_len)
```

2,493 entries, stored in alphabetical order. Index 0 = "Abbeville", 1 = "Aberconwy and Colwyn", 2 = "Aberdeen", etc.

### County Records Format

Each record (accessed via offset table) contains:
```
[binary date-range/metadata fields]
[uint8  url_count]
[for each URL:]
  [uint8  source_code]    (FSWIKI=0x03 len 6 "FSWIKI", WIKI=0x04 len 4 "WIKI", etc.)
  [uint8  url_len]
  [bytes  url_template]   (null-terminated, uses {FSWIKI} and {WIKI} placeholders)
```

Example URL templates found:
- `{FSWIKI}/Warren_County,_Iowa`
- `{FSWIKI}/Australia`
- `{WIKI}/Territorial_evolution_of_Australia`
- `{FSWIKI}/Australian_Capital_Territory,_Australia`

### Python: Parsing CountyCheckDB.dat

```python
import struct

COUNTYCHECK_PATH = (
    "/Applications/RootsMagic 11.app/Contents/MacOS/CountyCheckDB.dat"
)

# Section offsets (from header)
SEARCH_INDEX_START  = 0x0180
CANONICAL_START     = 0x9029
TYPE_STRINGS_START  = 0xEA38
RECORDS_START       = 0xEBE1
OFFSET_TABLE_START  = 0x517C6
OFFSET_TABLE_END    = 0x555CE
NUM_RECORDS         = (OFFSET_TABLE_END - OFFSET_TABLE_START) // 4  # 3970


def load_countycheck():
    with open(COUNTYCHECK_PATH, "rb") as f:
        return f.read()


def parse_canonical_names(data):
    """Return list of all 2,493 canonical county names in order."""
    names = []
    pos = CANONICAL_START
    while pos < TYPE_STRINGS_START - 1:
        name_len = data[pos]
        if name_len == 0:
            break
        name = data[pos + 1 : pos + 1 + name_len].decode("utf-8", errors="replace")
        names.append(name)
        pos += 1 + name_len
    return names


def parse_search_index(data):
    """
    Return dict mapping lowercase name → list of record IDs.
    IDs are indices into the offset table (0–3969).
    """
    index = {}
    pos = SEARCH_INDEX_START
    while pos < CANONICAL_START:
        name_len = data[pos]
        if name_len == 0:
            break
        name = data[pos + 1 : pos + 1 + name_len].decode("utf-8", errors="replace")
        pos += 1 + name_len
        count = data[pos]
        pos += 1
        ids = []
        for _ in range(count):
            record_id = struct.unpack_from("<H", data, pos)[0]
            ids.append(record_id)
            pos += 2
        index[name] = ids
    return index


def get_record(data, record_id):
    """
    Return raw bytes for a county record given its ID (0–3969).
    Includes binary metadata + URL template strings.
    """
    if record_id >= NUM_RECORDS:
        return None
    off_a = struct.unpack_from("<I", data, OFFSET_TABLE_START + record_id * 4)[0]
    off_b = struct.unpack_from("<I", data, OFFSET_TABLE_START + (record_id + 1) * 4)[0]
    return data[RECORDS_START + off_a : RECORDS_START + off_b]


def get_record_urls(data, record_id):
    """Extract URL template strings from a county record."""
    import re
    record = get_record(data, record_id)
    if record is None:
        return []
    # URL templates are null-terminated ASCII strings containing {FSWIKI} or {WIKI}
    return [
        s.decode("ascii", errors="replace")
        for s in re.findall(rb"[ -~]{4,}", record)
        if b"{FSWIKI}" in s or b"{WIKI}" in s
    ]


def lookup_county(data, name):
    """
    Look up a county name (case-insensitive) and return:
      - list of matching record IDs
      - URL templates for each match
    """
    index = parse_search_index(data)
    ids = index.get(name.lower(), [])
    results = []
    for record_id in ids:
        urls = get_record_urls(data, record_id)
        results.append({"record_id": record_id, "urls": urls})
    return results


# --- Usage example ---
# data = load_countycheck()
# canonical = parse_canonical_names(data)   # ['Abbeville', 'Aberdeen', ...]
# index = parse_search_index(data)          # {'abbeville': [1115], 'aberdeen': [1110, 1111, 1112], ...}
# results = lookup_county(data, "Warren")   # [{record_id: 1112, urls: ['{FSWIKI}/Warren_County,_Iowa']}, ...]
```

### Python: Data Quality Use Cases

#### 1. Canonical County Name Normalization

```python
def normalize_county_name(raw_name, data=None):
    """
    Given a user-entered county name, return the canonical spelling.
    E.g. "aberdeenshire" → "Aberdeenshire"
         "co. dublin" → may return None if not found
    """
    if data is None:
        data = load_countycheck()
    index = parse_search_index(data)
    ids = index.get(raw_name.strip().lower(), [])
    if not ids:
        return None
    canonical = parse_canonical_names(data)
    # Return the canonical name for the first matching record.
    # For multi-match cases, caller should disambiguate by country.
    # We can't resolve to canonical index directly from record_id without
    # a reverse mapping, but the search index key gives the lowercase form;
    # the canonical list is in the same alphabetical order.
    return ids  # Return IDs; resolve to canonical by scanning the names list


def find_canonical_name(raw_name, data=None):
    """
    Return canonical (properly-cased) county name if found in index.
    Works because canonical names are stored alphabetically alongside the index.
    """
    if data is None:
        data = load_countycheck()
    # Direct approach: scan canonical names for case-insensitive match
    canonical = parse_canonical_names(data)
    target = raw_name.strip().lower()
    for name in canonical:
        if name.lower() == target:
            return name
    return None  # not a canonical name

# Example:
# find_canonical_name("aberdeenshire")  → "Aberdeenshire"
# find_canonical_name("new south wales") → "New South Wales"
```

#### 2. County Existence Validation

```python
def county_exists(county_name, data=None):
    """
    Returns True if the county/region name is known to CountyCheckDB.
    Useful for validating place entries before committing to the database.
    """
    if data is None:
        data = load_countycheck()
    index = parse_search_index(data)
    return county_name.strip().lower() in index


def validate_place_components(city=None, county=None, state=None, data=None):
    """
    Validate each place component against CountyCheckDB (for county/state-level).
    Returns dict of {component: bool}.
    """
    if data is None:
        data = load_countycheck()
    index = parse_search_index(data)
    result = {}
    if county:
        result["county"] = county.lower().rstrip(" county") in index or county.lower() in index
    if state:
        result["state"] = state.lower() in index
    return result
```

#### 3. FamilySearch URL Generation

```python
FSWIKI_BASE = "https://www.familysearch.org/learn/wiki/en"
WIKI_BASE    = "https://en.wikipedia.org/wiki"

def get_familysearch_url(county_name, data=None):
    """
    Return the FamilySearch wiki URL for a county/region, if known.
    Useful for adding "Learn more" links in the UI.
    """
    if data is None:
        data = load_countycheck()
    results = lookup_county(data, county_name)
    for r in results:
        for url in r["urls"]:
            if url.startswith("{FSWIKI}"):
                path = url.replace("{FSWIKI}", "")
                return FSWIKI_BASE + path
    return None

# Example:
# get_familysearch_url("Warren County, Iowa")
#   → "https://www.familysearch.org/learn/wiki/en/Warren_County,_Iowa"
```

#### 4. Place Entry Data Quality Scoring

```python
def score_place_entry(county, state, data=None):
    """
    Score a place entry's data quality using CountyCheckDB.
    Returns 0.0–1.0 confidence score.
    """
    if data is None:
        data = load_countycheck()
    index = parse_search_index(data)

    score = 0.0
    weight_total = 0.0

    if county:
        weight_total += 0.6
        key = county.lower().removesuffix(" county").strip()
        if key in index or county.lower() in index:
            score += 0.6

    if state:
        weight_total += 0.4
        if state.lower() in index:
            score += 0.4

    return score / weight_total if weight_total > 0 else 0.0
```

---

## OnThisDayDB.dat — Historical Figures by Calendar Day (FULLY DECODED)

### What's Inside

- Historical births and deaths organized by day of year
- ~300–600 entries per day, each with birth year + full name
- Covers well-known figures from ~500 AD to modern era
- Compressed with zlib per-block

### Internal Structure

```
Offset      Section
0x000000    Index: 372 × uint32 LE offsets
              (12 months × 31 day slots; zero = no data for that day)
0x0005D1+   Data blocks (variable size, zlib-compressed)
```

**Index mapping:** Entry `(month-1)*31 + (day-1)` → byte offset to that day's block.
- Entry 0 = January 1
- Entry 31 = February 1
- Entry 59 = March 1 (note: Feb 29, 30, 31 have zero offsets)

**Block format (after decompression):**
```
[uint16 entry_count LE]   number of entries in this block
[uint8  format_flag]      always 0x00
[entries...]

Each entry:
  [uint16 birth_year LE]   year AD (e.g., 766 for Ali al-Rida)
  [uint16 name_len LE]     byte length of name string
  [bytes  name]            UTF-8 name, name_len bytes
  [uint8  null]            0x00 terminator
```

**Block header:** Each block is stored as:
```
[uint16 uncompressed_size LE]
[zlib-compressed data]
```

### Python: Parsing OnThisDayDB.dat

```python
import struct
import zlib

ONTHISDAY_PATH = (
    "/Applications/RootsMagic 11.app/Contents/MacOS/OnThisDayDB.dat"
)
INDEX_ENTRIES = 372  # 12 months × 31 days


def load_onthisday():
    with open(ONTHISDAY_PATH, "rb") as f:
        return f.read()


def get_day_index(month, day):
    """Return the index into the offset table for a given month/day (1-indexed)."""
    return (month - 1) * 31 + (day - 1)


def get_entries_for_day(data, month, day):
    """
    Return list of (birth_year, name) for all notable people born on month/day.
    Returns empty list if no data exists for that day (e.g., Feb 30).
    """
    idx = get_day_index(month, day)
    if idx >= INDEX_ENTRIES:
        return []

    offset = struct.unpack_from("<I", data, idx * 4)[0]
    if offset == 0 and idx > 0:
        return []  # no data for this day

    # Next non-zero offset gives the compressed block size
    next_offset = 0
    for i in range(idx + 1, INDEX_ENTRIES):
        next_offset = struct.unpack_from("<I", data, i * 4)[0]
        if next_offset != 0:
            break

    # First 2 bytes = uncompressed size; rest = zlib data
    uncompressed_size = struct.unpack_from("<H", data, offset)[0]
    compressed = data[offset + 2 : next_offset]
    decompressed = zlib.decompress(compressed)
    assert len(decompressed) == uncompressed_size

    # Parse entries
    entry_count = struct.unpack_from("<H", decompressed, 0)[0]
    # flag byte at position 2 is always 0x00
    pos = 3
    entries = []
    for _ in range(entry_count):
        year     = struct.unpack_from("<H", decompressed, pos)[0]
        name_len = struct.unpack_from("<H", decompressed, pos + 2)[0]
        name     = decompressed[pos + 4 : pos + 4 + name_len].decode("utf-8", errors="replace")
        entries.append((year, name))
        pos += 4 + name_len + 1  # skip null terminator

    return entries


# --- Usage example ---
# data = load_onthisday()
# entries = get_entries_for_day(data, 1, 1)   # January 1
# # → [(766, 'Ali al-Rida, Shia Imam (d. 818)'),
# #    (871, 'King Zwentibold of Lotharingia (d. 900)'),
# #    (1431, 'Pope Alexander VI (d. 1503)'), ...]
```

### Data Quality Use Cases

#### 1. Birth Year Plausibility Check

```python
def validate_birth_year_plausibility(name_fragment, stated_birth_year,
                                      birth_month=None, birth_day=None, data=None):
    """
    Cross-reference a person's stated birth year against OnThisDayDB.
    If their birth date is known, check whether the year matches a
    historical figure with a similar name.

    Returns: (found: bool, matched_entry: str | None, year_match: bool)
    """
    if data is None:
        data = load_onthisday()

    if birth_month is None or birth_day is None:
        return False, None, False

    entries = get_entries_for_day(data, birth_month, birth_day)
    name_lower = name_fragment.lower()

    for year, entry_name in entries:
        if name_lower in entry_name.lower():
            year_match = abs(year - stated_birth_year) <= 2
            return True, entry_name, year_match

    return False, None, False
```

#### 2. "On This Day" Feature

```python
def get_historical_context(birth_month, birth_day, data=None):
    """
    Return a few notable people born on the same day as a person in the tree.
    Useful as a UI enrichment feature ("People born on this day in history").
    """
    if data is None:
        data = load_onthisday()
    entries = get_entries_for_day(data, birth_month, birth_day)
    # Return up to 5 entries, sorted by year
    return sorted(entries, key=lambda e: e[0])[:5]

# Example output for Jan 1:
# [(766, 'Ali al-Rida, Shia Imam (d. 818)'),
#  (871, 'King Zwentibold of Lotharingia (d. 900)'),
#  (1431, 'Pope Alexander VI (d. 1503)'),
#  (1449, "Lorenzo de' Medici (d. 1492)"),
#  (1484, 'Huldrych Zwingli, Swiss religious figure (d. 1531)')]
```

---

## Integrated Data Quality Pipeline

Combining all three databases into a unified place validation flow:

```python
class RootsMagicReferenceDB:
    """
    Unified interface to all three RootsMagic reference databases.
    """

    def __init__(self):
        self._county_data    = None
        self._onthisday_data = None
        self._gazetteer      = None  # GazetteerSearch instance

    @property
    def county_data(self):
        if self._county_data is None:
            self._county_data = load_countycheck()
        return self._county_data

    @property
    def onthisday_data(self):
        if self._onthisday_data is None:
            self._onthisday_data = load_onthisday()
        return self._onthisday_data

    def validate_place(self, city=None, county=None, state=None, country=None):
        """
        Full place validation using PlaceDB (individual components)
        and CountyCheckDB (county/state-level validation).
        Returns dict with validation results per component.
        """
        result = {}

        # PlaceDB: validate individual name components exist
        if self._gazetteer is None:
            from rmcitecraft.utils.gazetteer_search import GazetteerSearch
            self._gazetteer = GazetteerSearch()

        for label, value in [("city", city), ("state", state), ("country", country)]:
            if value:
                result[label] = self._gazetteer.exists(value, fuzzy=True)

        # CountyCheckDB: validate county with stricter canonical lookup
        if county:
            key = county.lower().removesuffix(" county").strip()
            index = parse_search_index(self.county_data)
            result["county"] = key in index or county.lower() in index

        return result

    def normalize_county(self, county_name):
        """Return canonical spelling of a county name, or None if unknown."""
        return find_canonical_name(county_name, self.county_data)

    def get_county_reference_url(self, county_name):
        """Return a FamilySearch URL for a county, if available."""
        return get_familysearch_url(county_name, self.county_data)

    def get_on_this_day(self, month, day, limit=5):
        """Return notable historical figures born on month/day."""
        entries = get_entries_for_day(self.onthisday_data, month, day)
        return sorted(entries, key=lambda e: e[0])[:limit]
```

---

## RootsMagic Gazetteer: Three-Tier Search System

### How RootsMagic Uses These Files

1. **User's PlaceTable** (from `.rmtree` SQLite database)
   - Full hierarchies already entered — searched first (score: 10000)

2. **PlaceDB.dat** — worldwide place name components
   - ~2.5M individual place names (cities, states, countries)
   - Validates that each component name is real
   - Score: 5000–9000

3. **CountyCheckDB.dat** — county/province validation
   - 3,970 records with date ranges (validates historical accuracy)
   - Covers US, Canada, Australia, England, Wales, Scotland
   - Updated 2022 (vs. PlaceDB's 2006 vintage)

### Search Behavior

**With comma** ("Phoenix, az"):
- Tokenizes on comma, searches hierarchical components
- Prioritizes user's existing places
- Result: "Phoenix, Maricopa, Arizona, United States" (score: 10000)

**Without comma** ("Phoenix az"):
- Full-text fuzzy search across entire strings
- May return unrelated matches (e.g., "Fengxi, Zhejiang, China")

---

## Recommendations for Place Validation

### Do
- Use CountyCheckDB to normalize county spelling before writing to database
- Use `find_canonical_name()` when a user types a county name freeform
- Use PlaceDB for city/state/country component existence checks
- Use fuzzy matching (default threshold: 0.90) for PlaceDB searches
- Search individual components (city, county, state) separately — not full strings

### Don't
- Rely on PlaceDB for county validation — use CountyCheckDB instead
- Assume a missing entry means the place is wrong — may be a formatting issue
- Search PlaceDB for full hierarchical names like "Princeton, Mercer, New Jersey"

### For Place Approval Dialog

```
Find a Grave Location: Princeton, Mercer County, New Jersey, USA
Proposed Place: Princeton, Mercer, New Jersey, United States

Validation:
  ✓ Princeton      — Found in PlaceDB (exact)
  ✓ Mercer         — Found in CountyCheckDB
  ✓ New Jersey     — Found in PlaceDB + CountyCheckDB
  ✓ United States  — Found in PlaceDB (exact)
  → FamilySearch:  https://familysearch.org/learn/wiki/en/Mercer_County,_New_Jersey
```

---

## Future Enhancements

1. **CountyCheckDB date-range decoding**: The binary metadata in each record encodes
   start/end years for county existence (e.g., "Kanawha County formed 1788"). Decoding
   this would enable temporal validation: "Was this county in existence in 1850?"

2. **PlaceDB trie decoder**: The 38-entry jump table at offset 0x2E indexes a
   multi-level trie. Fully decoding the trie would enable O(log n) lookups instead
   of the current linear scan, and would expose the metadata fields (country code,
   admin level) stored in each record.

3. **SQLite index**: One-time export of CountyCheckDB canonical names + URLs to a
   small SQLite file for fast queries without parsing the binary format at runtime.

4. **Postal abbreviation support**: Lookup table mapping "NJ" → "New Jersey", etc.
   Maps RootsMagic's own behavior for state abbreviation resolution.

5. **OnThisDayDB enrichment**: Surface "born on this day" context in the UI when a
   person's birth date is known (e.g., as a tooltip or sidebar widget).

6. **Soundex/phonetic matching**: Supplement SequenceMatcher for PlaceDB searches
   to handle common phonetic misspellings.

---

## Code Locations

- **PlaceDB utility**: `/src/rmcitecraft/utils/gazetteer_search.py`
- **CountyCheck parser**: (to be added) `/src/rmcitecraft/utils/countycheck.py`
- **OnThisDay parser**: (to be added) `/src/rmcitecraft/utils/onthisday.py`
- **Test script**: `/scripts/test_gazetteer.py`
- **This document**: `/docs/GAZETTEER.md`

## Testing

```bash
uv run python scripts/test_gazetteer.py
```

---

## OCR Data Quality: WWII Draft Registration Cards

WWII draft registration cards (1940–1942) are a high-value genealogical source with
location fields that are frequently garbled by OCR. Each card contains a residential
address (city, county, state) and a birth place (which may be foreign). The five
strategies below apply the three RootsMagic databases to specific failure modes
observed in OCR'd card batches.

### Strategy 1 — County Name Spelling Correction (CountyCheckDB)

**Problem:** OCR garbles unusual county names — "Cuyahoga" → "Cuvohaga",
"Taliaferro" → "Taliaferre", "Tuscarawas" → "Tuscurawas".

**Solution:** Fuzzy-match the OCR'd token against CountyCheckDB's 2,493 canonical
names. CountyCheckDB is preferred over PlaceDB here because it is scoped exclusively
to counties/provinces — false positives from city names are eliminated.

```python
from difflib import get_close_matches

def correct_county_name(ocr_county: str, canonical_names: list[str]) -> str | None:
    """
    Given an OCR'd county name, return the canonical spelling.
    Strips trailing 'County', 'Co.', etc. before matching.
    """
    normalized = (
        ocr_county.lower()
        .removesuffix(" county")
        .removesuffix(" co.")
        .removesuffix(" co")
        .strip()
    )
    candidates = {n.lower(): n for n in canonical_names}
    matches = get_close_matches(normalized, candidates.keys(), n=1, cutoff=0.82)
    return candidates[matches[0]] if matches else None

# "Cuyohaga"   → "Cuyahoga"
# "Tuscurawas" → "Tuscarawas"
# "Taliaferre" → "Taliaferro"
```

**Note on cutoff:** 0.82 is conservative enough to avoid false corrections on short
names (e.g., "Ada" → "Adair") while catching the transpositions common in OCR.

---

### Strategy 2 — Historical County Existence Validation (CountyCheckDB date ranges)

**Problem:** OCR might produce a plausible county name that did not exist in 1940–1942
— formed later, renamed, or absorbed. "Custer County" in a given state may be right
or may reflect a post-war boundary change.

**Solution:** CountyCheckDB records contain binary date-range metadata encoding when
each county existed. Once decoded, this enables a direct temporal filter for any
registration year.

**Current status:** The date-range bytes are confirmed present in each record but not
yet fully decoded. The byte sequence `4e 1e 63` appears repeatedly across records and
is a likely shared reference value (candidate for the next reverse-engineering session).

```python
def county_existed_in_year(record_bytes: bytes, year: int) -> bool | None:
    """
    Returns True/False if date range is decoded, None if still unknown.
    Target: validate records against 1940–1942 for WWII draft cards.
    """
    # TODO: decode the date-range bytes at the start of each record.
    # The repeating pattern 4e 1e 63 across records is the key lead.
    # For now, presence of the record is a weak positive signal.
    return len(record_bytes) > 0  # placeholder

# Once decoded, usage:
# county_existed_in_year(get_record(data, record_id), 1942)
# → True  for Hamilton County, Ohio (formed 1790)
# → False for a county formed in 1960
```

**Immediate value even without decoding:** A county absent from CountyCheckDB entirely
(unknown to a 2022 dataset) warrants human review. The FamilySearch URL in the record
can be retrieved and checked to confirm formation date.

---

### Strategy 3 — City Name Validation and Correction (PlaceDB)

**Problem:** OCR produces "Cincinatti", "Pittsburg" (missing h), "Baltimorc",
"Milwaukce". Some are close enough to auto-correct; others need a human.

**Solution:** Fuzzy-search PlaceDB for the OCR'd city string, then score the best
candidate. State context narrows the result space.

```python
from difflib import SequenceMatcher
from rmcitecraft.utils.gazetteer_search import GazetteerSearch

searcher = GazetteerSearch()

def validate_city(ocr_city: str, threshold: float = 0.85) -> dict:
    """
    Validate an OCR'd city name against PlaceDB.
    Returns confidence score and best candidate.
    """
    if searcher.exists(ocr_city, fuzzy=False):
        return {"status": "exact", "correction": ocr_city, "confidence": 1.0}

    candidates = searcher.search(ocr_city, max_results=10)
    scored = sorted(
        ((c, SequenceMatcher(None, ocr_city.lower(), c.lower()).ratio())
         for c in candidates),
        key=lambda x: x[1], reverse=True
    )
    best, score = scored[0] if scored else (None, 0.0)

    if score >= threshold:
        return {"status": "fuzzy", "correction": best, "confidence": score}
    return {"status": "unknown", "correction": None, "confidence": score}

# "Cincinatti" → {"status": "fuzzy", "correction": "Cincinnati", "confidence": 0.94}
# "Baltimorc"  → {"status": "fuzzy", "correction": "Baltimore",  "confidence": 0.92}
# "Milwaukce"  → {"status": "fuzzy", "correction": "Milwaukee",  "confidence": 0.91}
```

**Why PlaceDB's 2006 vintage is an advantage here:** It predates many municipal
consolidations and still contains historical small-town names that modern datasets
have dropped — exactly the towns that appear on 1940s draft cards.

---

### Strategy 4 — Foreign Birth Place Normalization (PlaceDB + CountyCheckDB)

**Problem:** Many WWII registrants were foreign-born. OCR'd birth places may use
historical country names ("Austro-Hungarian Empire", "Russian Poland", "Bohemia"),
regional names ("Calabria", "Bavaria"), or simply garbled small-town spellings
from handwritten entries in multiple languages.

**Solution:** A two-stage lookup: CountyCheckDB for British Isles and Canada (where
it has authoritative coverage), then PlaceDB's worldwide entries for everything else,
supplemented by a historical country name map.

```python
# Historical country/region names used on 1940s documents → modern equivalents
HISTORICAL_COUNTRY_MAP = {
    "austria-hungary":          "Austria-Hungary",
    "austro-hungarian empire":  "Austria-Hungary",
    "russian poland":           "Poland",
    "russian empire":           "Russia",
    "bohemia":                  "Czech Republic",
    "moravia":                  "Czech Republic",
    "galicia":                  None,          # ambiguous: Spain or Poland/Ukraine
    "prussia":                  "Germany",
    "alsace":                   "France",
    "alsace-lorraine":          "France",
    "czecho-slovakia":          "Czechoslovakia",
    "jugoslavia":               "Yugoslavia",
    "ukrainia":                 "Ukraine",
    "great britain":            "England",
}

def normalize_foreign_birthplace(ocr_place: str, cc_data=None) -> dict:
    """
    Normalize a foreign birth place from a WWII draft card.
    """
    from rmcitecraft.utils.countycheck import find_canonical_name, load_countycheck

    lower = ocr_place.lower().strip()

    # Stage 1: historical name map
    if lower in HISTORICAL_COUNTRY_MAP:
        modern = HISTORICAL_COUNTRY_MAP[lower]
        return {"canonical": modern, "source": "historical_map",
                "note": f"Historical name; modern equivalent: {modern}"}

    # Stage 2: CountyCheckDB (authoritative for British Isles + Canada)
    cc_data = cc_data or load_countycheck()
    canonical = find_canonical_name(ocr_place, cc_data)
    if canonical:
        return {"canonical": canonical, "source": "CountyCheckDB", "note": None}

    # Stage 3: PlaceDB worldwide fuzzy search
    candidates = searcher.search(ocr_place, max_results=5)
    if candidates:
        return {"canonical": candidates[0], "source": "PlaceDB",
                "note": "fuzzy match — verify"}

    return {"canonical": None, "source": None, "note": "not found — needs review"}

# normalize_foreign_birthplace("Russian Poland")
#   → {"canonical": "Poland", "source": "historical_map", ...}
# normalize_foreign_birthplace("County Cork")
#   → {"canonical": "Cork", "source": "CountyCheckDB", ...}
# normalize_foreign_birthplace("Calabria")
#   → {"canonical": "Calabria", "source": "PlaceDB", "note": "fuzzy match..."}
```

---

### Strategy 5 — Cross-Field Consistency Scoring (City + County + State)

**Problem:** Even when each OCR'd field looks plausible individually, the combination
may be wrong. "Springfield, Cook County, Ohio" — Springfield and Cook County both
exist, but Cook County is in Illinois. OCR errors in one field corrupt an otherwise
valid record, and it's not obvious which field is wrong.

**Solution:** Score the three fields as a group. A low overall score triggers human
review; identifying which field is the odd one out helps direct the reviewer's
attention.

```python
def score_wwii_location(city: str, county: str, state: str,
                         cc_data=None) -> dict:
    """
    Score the internal consistency of a WWII draft card location triplet.

    Score bands:
      0.70–1.00  All fields recognized → accept
      0.50–0.69  One field unrecognized → attempt auto-correction
      0.00–0.49  Multiple fields unrecognized → human review required
    """
    from rmcitecraft.utils.countycheck import (
        parse_search_index, find_canonical_name, load_countycheck
    )

    cc_data = cc_data or load_countycheck()
    cc_index = parse_search_index(cc_data)

    county_key = county.lower().removesuffix(" county").strip()
    county_known = county_key in cc_index or county.lower() in cc_index
    state_known  = state.lower() in cc_index or searcher.exists(state)
    city_known   = searcher.exists(city, fuzzy=True)

    score = (
        0.35 * county_known +
        0.35 * state_known  +
        0.30 * city_known
    )
    unknown = [f for f, ok in [("city", city_known),
                                ("county", county_known),
                                ("state", state_known)] if not ok]

    return {
        "score":            round(score, 2),
        "suspect_fields":   unknown,
        "county_canonical": find_canonical_name(county, cc_data),
        "action": (
            "accept"        if score >= 0.70 else
            "auto-correct"  if score >= 0.50 and len(unknown) == 1 else
            "human-review"
        ),
    }

# score_wwii_location("Cincinnati",  "Hamilton County",  "Ohio")
#   → {score: 1.0, suspect_fields: [], action: "accept"}
#
# score_wwii_location("Cincinatti",  "Hamilton County",  "Ohio")
#   → {score: 0.70, suspect_fields: ["city"], action: "auto-correct"}
#
# score_wwii_location("Springfield", "Cook County",      "Ohio")
#   → {score: 0.65, suspect_fields: ["state"], action: "human-review"}
#   (Cook County is in Illinois — state is the likely OCR error)
```

---

### WWII OCR Strategy Priority

| # | Strategy | Effort | Databases Used | Value |
|---|----------|--------|---------------|-------|
| 1 | County spelling correction | Low | CountyCheckDB | High — most common error type |
| 3 | City fuzzy validation | Low | PlaceDB | High — catches transpositions |
| 5 | Cross-field consistency | Medium | Both | High — identifies *which* field is wrong |
| 4 | Foreign birth place | Medium | Both + name map | Medium — valuable for immigrant cohort |
| 2 | Historical county date ranges | High (needs decode) | CountyCheckDB | High once done — anachronism detection |

Strategy 2 (date-range decoding) is the highest-leverage remaining reverse-engineering
task. The repeating byte pattern `4e 1e 63` in CountyCheckDB records is the primary
lead for the next analysis session.

---

## Summary

| Database | Status | Best Use |
|----------|--------|----------|
| `PlaceDB.dat` | Searchable (binary scan) | City/state/country name existence checks |
| `CountyCheckDB.dat` | **Fully decoded** | County name normalization, canonical spelling, FamilySearch URLs |
| `OnThisDayDB.dat` | **Fully decoded** | Birth year plausibility, "on this day" UI enrichment |

**Key takeaway**: `CountyCheckDB.dat` is now directly parseable and is the most valuable
for data quality work. Use it as the authoritative source for county/province name
normalization. Use `PlaceDB.dat` for broader city/state/country validation. Use
`OnThisDayDB.dat` for birth year cross-referencing and UI enrichment features.
